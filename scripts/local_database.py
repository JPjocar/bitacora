"""Create an isolated, loopback-only PostgreSQL cluster for development on Windows.

Uses existing PostgreSQL binaries; never modifies the installed system service.
Run with .venv/Scripts/python scripts/local_database.py start|stop.
"""

import argparse
import os
import secrets
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCAL = ROOT / ".local"
DATA = LOCAL / "postgres"


def run(*args):
    subprocess.run([str(arg) for arg in args], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["start", "stop"])
    parser.add_argument("--bin", default=r"C:\Program Files\PostgreSQL\18\bin")
    args = parser.parse_args()
    pg = Path(args.bin)
    if args.action == "stop":
        run(pg / "pg_ctl.exe", "-D", DATA, "-m", "fast", "stop")
        return
    LOCAL.mkdir(exist_ok=True)
    if not (DATA / "PG_VERSION").exists():
        if (ROOT / ".env").exists():
            raise SystemExit(
                "Ya existe .env. Configure su BD o preserve el archivo "
                "antes de iniciar un clúster nuevo."
            )
        password = secrets.token_urlsafe(32)
        password_file = LOCAL / "init-password.txt"
        password_file.write_text(password, encoding="utf-8")
        try:
            run(
                pg / "initdb.exe",
                "-D",
                DATA,
                "-U",
                "bitacora_local",
                "--encoding=UTF8",
                "--locale=C",
                "--auth=scram-sha-256",
                f"--pwfile={password_file}",
            )
        finally:
            password_file.unlink(missing_ok=True)
        with (DATA / "postgresql.conf").open("a", encoding="utf-8") as config:
            config.write("\nlisten_addresses = '127.0.0.1'\nport = 55432\n")
        (ROOT / ".env").write_text(
            f"DJANGO_SECRET_KEY={secrets.token_urlsafe(64)}\nDJANGO_DEBUG=true\n"
            "DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1\nPGDATABASE=bitacora\n"
            f"PGUSER=bitacora_local\nPGPASSWORD={password}\nPGHOST=127.0.0.1\nPGPORT=55432\n",
            encoding="utf-8",
        )
    if subprocess.run(
        [str(pg / "pg_ctl.exe"), "-D", str(DATA), "status"], capture_output=True
    ).returncode:
        run(pg / "pg_ctl.exe", "-D", DATA, "-l", LOCAL / "postgres.log", "-w", "start")
    values = dict(
        line.split("=", 1)
        for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines()
        if "=" in line
    )
    os.environ.update({key: value for key, value in values.items() if key.startswith("PG")})
    check = subprocess.run(
        [
            str(pg / "psql.exe"),
            "-d",
            "postgres",
            "-tAc",
            "SELECT 1 FROM pg_database WHERE datname='bitacora'",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    if check.stdout.strip() != "1":
        run(pg / "createdb.exe", "bitacora")
    print(
        "PostgreSQL local disponible en 127.0.0.1:55432. "
        "Variables guardadas en .env (ignorado por Git)."
    )


if __name__ == "__main__":
    main()
