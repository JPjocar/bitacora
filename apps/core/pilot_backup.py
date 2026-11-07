"""Offline recovery verification in a new temporary database, never in the source."""

import hashlib
import json
import os
import re
import shutil
import subprocess
import zipfile
from pathlib import Path, PurePosixPath
from uuid import uuid4

import psycopg
from django.conf import settings
from django.core.management.base import CommandError
from django.db import connection, transaction
from django.utils import timezone
from psycopg import sql


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def media_inventory(root):
    if root.is_symlink() or root.is_junction():
        raise CommandError("Media no puede ser un enlace simbólico.")
    files = {}
    if root.exists():
        for path in sorted(root.rglob("*")):
            if path.is_symlink() or path.is_junction():
                raise CommandError("No se respaldan enlaces simbólicos de media.")
            if path.is_file():
                files[path.relative_to(root).as_posix()] = digest(path)
    return files


def fingerprint(cursor, tables):
    result = {}
    cursor.execute("SET TIME ZONE 'UTC'")
    cursor.execute("SET datestyle TO ISO, YMD")
    for table in sorted(tables):
        cursor.execute(
            sql.SQL(
                'SELECT row_to_json(t)::text FROM {} t ORDER BY row_to_json(t)::text COLLATE "C"'
            ).format(sql.Identifier("public", table))
        )
        count, hashed = 0, hashlib.sha256()
        while rows := cursor.fetchmany(1000):
            for (row,) in rows:
                hashed.update(row.encode("utf8") + b"\n")
                count += 1
        result[table] = {"rows": count, "sha256": hashed.hexdigest()}
    return result


def pg_environment(database=None):
    config = settings.DATABASES["default"]
    environment = os.environ.copy()
    for key, field in [
        ("PGHOST", "HOST"),
        ("PGPORT", "PORT"),
        ("PGUSER", "USER"),
        ("PGPASSWORD", "PASSWORD"),
    ]:
        environment[key] = str(config[field])
    environment["PGDATABASE"] = database or str(config["NAME"])
    return environment


def pg_connection(database):
    config = settings.DATABASES["default"]
    return psycopg.connect(
        dbname=database,
        host=config["HOST"],
        port=config["PORT"],
        user=config["USER"],
        password=config["PASSWORD"],
        connect_timeout=5,
    )


def pg_tool(name, pg_bin):
    path = (
        Path(pg_bin) / (name + (".exe" if os.name == "nt" else ""))
        if pg_bin
        else shutil.which(name)
    )
    if not path or not Path(path).is_file():
        raise CommandError(
            "Indique --pg-bin con los clientes PostgreSQL de la versión del servidor."
        )
    return str(path)


def run_tool(name, arguments, *, pg_bin=None, database=None):
    completed = subprocess.run(
        [pg_tool(name, pg_bin), *map(str, arguments)],
        env=pg_environment(database),
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        # PostgreSQL error details may include data; do not echo them into application logs.
        raise CommandError(
            f"{name} falló (código {completed.returncode}). Revise versión, conexión y permisos."
        )


def create_backup(directory, *, pg_bin=None):
    directory = Path(directory).resolve()
    if directory.exists():
        raise CommandError("Use un directorio de backup nuevo; no se sobrescriben archivos.")
    media = Path(settings.MEDIA_ROOT).absolute()
    if not settings.MEDIA_ROOT or directory.is_relative_to(media.resolve()):
        raise CommandError("El backup debe estar fuera de MEDIA_ROOT.")
    directory.mkdir(parents=True, mode=0o700)
    database_file, media_file = directory / "database.dump", directory / "media.zip"
    # The dump and manifest use one exported MVCC snapshot, even with concurrent sessions.
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            cursor.execute("SELECT pg_export_snapshot()")
            snapshot = cursor.fetchone()[0]
            tables = connection.introspection.table_names(cursor)
            run_tool(
                "pg_dump",
                [
                    "--format=custom",
                    "--no-owner",
                    "--no-acl",
                    "--snapshot=" + snapshot,
                    "--file=" + str(database_file),
                ],
                pg_bin=pg_bin,
            )
            inventory = fingerprint(cursor, tables)
    files = media_inventory(media)
    with zipfile.ZipFile(media_file, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in files:
            archive.write(media / name, name)
    # Detect media changing while being copied. Current MVP has no upload feature.
    if files != media_inventory(media):
        raise CommandError(
            "Media cambió durante la copia. Detenga escrituras y repita en otro directorio."
        )
    manifest = {
        "format": 1,
        "created_at": timezone.now().isoformat(),
        "tables": inventory,
        "database_sha256": digest(database_file),
        "media_sha256": digest(media_file),
        "media_files": files,
    }
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf8")
    return manifest


def load_manifest(directory):
    try:
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf8"))
        if manifest["format"] != 1 or not manifest["tables"]:
            raise ValueError
        for name, field in [("database.dump", "database_sha256"), ("media.zip", "media_sha256")]:
            if digest(directory / name) != manifest[field]:
                raise ValueError
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise CommandError(
            "Backup incompleto o integridad SHA-256 incorrecta. No se restauró nada."
        ) from error
    return manifest


def restore_media(archive_path, output):
    output.mkdir(mode=0o700)
    with zipfile.ZipFile(archive_path) as archive:
        for entry in archive.infolist():
            relative = PurePosixPath(entry.filename)
            if (
                relative.is_absolute()
                or ".." in relative.parts
                or ":" in entry.filename
                or "\\" in entry.filename
            ):
                raise CommandError("El archivo media contiene una ruta no segura.")
            target = output.joinpath(*relative.parts).resolve()
            if not target.is_relative_to(output.resolve()):
                raise CommandError("Ruta de media fuera del destino.")
            if entry.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("xb") as stream:
                    stream.write(archive.read(entry))


def check_restored(cursor, tables):
    cursor.execute(
        "SELECT count(*) FROM pg_constraint "
        "WHERE connamespace='public'::regnamespace AND NOT convalidated"
    )
    if cursor.fetchone()[0]:
        raise CommandError("La restauración contiene restricciones sin validar.")
    cursor.execute(
        "SELECT table_name FROM information_schema.columns "
        "WHERE table_schema='public' AND column_name='id'"
    )
    for (table,) in cursor.fetchall():
        if table not in tables:
            continue
        cursor.execute(
            "SELECT n.nspname, c.relname FROM pg_class c "
            "JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE c.oid=pg_get_serial_sequence(%s,'id')::regclass",
            [table],
        )
        sequence = cursor.fetchone()
        if sequence:
            cursor.execute(
                sql.SQL("SELECT last_value,is_called FROM {}").format(sql.Identifier(*sequence))
            )
            last, called = cursor.fetchone()
            cursor.execute(
                sql.SQL("SELECT max(id) FROM {}").format(sql.Identifier("public", table))
            )
            maximum = cursor.fetchone()[0]
            if maximum is not None and (last < maximum or (last == maximum and not called)):
                raise CommandError("Una secuencia restaurada podría repetir identificadores.")


def verify_backup(directory, *, pg_bin=None):
    directory = Path(directory).resolve()
    manifest = load_manifest(directory)
    name = "bitacora_verify_" + uuid4().hex[:20]
    if (
        not re.fullmatch(r"bitacora_verify_[a-f0-9]{20}", name)
        or name == settings.DATABASES["default"]["NAME"]
    ):
        raise CommandError("Destino temporal inválido.")
    created = False
    with pg_connection("postgres") as admin:
        admin.autocommit = True
        try:
            admin.execute(
                sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(name))
            )
            created = True
            run_tool(
                "pg_restore",
                [
                    "--no-owner",
                    "--no-acl",
                    "--exit-on-error",
                    "--single-transaction",
                    "--dbname=" + name,
                    directory / "database.dump",
                ],
                pg_bin=pg_bin,
                database=name,
            )
            with pg_connection(name) as restored, restored.cursor() as cursor:
                cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")
                tables = [row[0] for row in cursor.fetchall()]
                if fingerprint(cursor, tables) != manifest["tables"]:
                    raise CommandError("Los datos restaurados difieren del snapshot del backup.")
                check_restored(cursor, tables)
            media_output = directory / ("verification-media-" + uuid4().hex)
            restore_media(directory / "media.zip", media_output)
            if media_inventory(media_output) != manifest["media_files"]:
                raise CommandError("Media restaurada difiere del backup.")
        finally:
            if created:
                # Only the random database created above can ever be dropped; no --clean/--create.
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))
    return manifest
