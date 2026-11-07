"""Run the checked WSGI pilot on loopback, behind an explicit trusted local TLS proxy."""

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file",
        type=Path,
        help="Archivo de entorno explícito; no se lee .env automáticamente.",
    )
    parser.add_argument("--port", type=int, default=8081)
    parser.add_argument(
        "--allow-demo", action="store_true", help="Solo para un piloto sintético controlado."
    )
    options = parser.parse_args()
    if not 1 <= options.port <= 65535:
        parser.error("Puerto inválido.")
    if options.env_file:
        for line in options.env_file.read_text(encoding="utf8").splitlines():
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key, value)
    sys.path.insert(0, str(ROOT))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()
    from django.core.management import call_command
    from django.core.wsgi import get_wsgi_application
    from waitress import serve

    call_command("check_pilot", allow_demo=options.allow_demo)
    serve(
        get_wsgi_application(),
        host="127.0.0.1",
        port=options.port,
        threads=4,
        trusted_proxy="127.0.0.1",
        trusted_proxy_count=1,
        trusted_proxy_headers={"x-forwarded-proto"},
        clear_untrusted_proxy_headers=True,
        max_request_body_size=2 * 1024 * 1024,
        ident="Bitacora",
    )


if __name__ == "__main__":
    main()
