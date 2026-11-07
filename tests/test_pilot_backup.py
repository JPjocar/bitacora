import json
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

from apps.core.pilot_backup import (
    create_backup,
    digest,
    load_manifest,
    media_inventory,
    restore_media,
)
from scripts.configure_proxy import render


class PilotPreparationTests(SimpleTestCase):
    def test_backup_refuses_an_existing_directory_before_connecting(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(CommandError):
                create_backup(directory)

    def test_backup_refuses_to_archive_into_media(self):
        with tempfile.TemporaryDirectory() as directory:
            with override_settings(MEDIA_ROOT=directory), self.assertRaises(CommandError):
                create_backup(Path(directory) / "backup")

    def test_manifest_detects_corruption_before_any_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "database.dump").write_bytes(b"synthetic dump")
            (root / "media.zip").write_bytes(b"synthetic media")
            manifest = {
                "format": 1,
                "tables": {"test": {}},
                "database_sha256": digest(root / "database.dump"),
                "media_sha256": digest(root / "media.zip"),
            }
            (root / "manifest.json").write_text(json.dumps(manifest))
            self.assertEqual(load_manifest(root), manifest)
            (root / "database.dump").write_bytes(b"corrupted")
            with self.assertRaises(CommandError):
                load_manifest(root)

    def test_media_restore_reproduces_nested_binary_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            (source / "synthetic.bin").write_bytes(bytes(range(256)))
            with zipfile.ZipFile(root / "media.zip", "x") as archive:
                archive.write(source / "synthetic.bin", "subdir/synthetic.bin")
            restore_media(root / "media.zip", root / "output")
            self.assertEqual(
                digest(root / "output/subdir/synthetic.bin"), digest(source / "synthetic.bin")
            )
            self.assertEqual(len(media_inventory(root / "output")), 1)
            with patch("pathlib.Path.is_junction", return_value=True):
                with self.assertRaises(CommandError):
                    media_inventory(root / "output")

    def test_media_zip_cannot_escape_the_new_destination(self):
        for name in ["../outside", "/outside", "C:/outside", "dir\\..\\outside"]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                with zipfile.ZipFile(root / "media.zip", "x") as archive:
                    archive.writestr(name, "untrusted")
                with self.assertRaises(CommandError):
                    restore_media(root / "media.zip", root / "output")
                self.assertFalse((root / "outside").exists())

    def test_pilot_preflight_refuses_debug_before_any_database_query(self):
        with override_settings(DEBUG=True), self.assertRaises(CommandError):
            call_command("check_pilot")

    def test_proxy_template_rejects_host_and_config_injection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ["cert", "key", "mime"]:
                (root / name).write_text("synthetic")
            values = dict(
                host="localhost",
                bind="127.0.0.1",
                http_port=8088,
                https_port=8443,
                upstream_port=8081,
                certificate=root / "cert",
                key=root / "key",
                static_root=root,
                mime_types=root / "mime",
            )
            config = render(**values)
            self.assertIn("rate=5r/m", config)
            self.assertIn("listen 127.0.0.1:8443 ssl", config)
            self.assertNotIn("@@", config)
            for host in ["localhost; injected", "https://localhost", "$host"]:
                with self.assertRaises(ValueError):
                    render(**{**values, "host": host})
            with self.assertRaises(ValueError):
                render(**{**values, "upstream_port": 8443})
