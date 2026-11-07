"""Local demo HTTP checks for inbox, ownership, dashboard and filtered reports."""

import argparse
import re
from pathlib import Path
from urllib.parse import urlsplit

from smoke_execution_http import DemoClient, Inputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--credentials-file", default=".local/demo-credentials.txt")
    parser.add_argument(
        "--confirm-demo", action="store_true", help="Permite marcar un aviso demo leído."
    )
    options = parser.parse_args()
    if not options.confirm_demo or urlsplit(options.base_url).hostname not in (
        "localhost",
        "127.0.0.1",
    ):
        parser.error("Requiere --confirm-demo y un servidor local con avisos demo generados.")
    raw = Path(options.credentials_file).read_bytes()
    encoding = "utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
    credentials = dict(
        line.split(": ", 1)
        for line in raw.decode(encoding).splitlines()
        if line.startswith("demo_")
    )
    own_read_path = None
    for username in ("demo_tecnico", "demo_admin", "demo_docente"):
        client = DemoClient(options.base_url)
        client.login(username, credentials[username])
        expected = 403 if username == "demo_docente" else 200
        for path in (
            "/avisos/",
            "/avisos/contador/",
            "/panel/",
            "/panel/exportar/",
            "/panel/imprimir/",
        ):
            assert client.request(path)[0] == expected, (username, path)
        if expected == 403:
            assert "notification-counter" not in client.request("/")[1]
            continue
        for section in ("deadlines", "runs", "unconfigured", "omissions", "devices"):
            status, html, _ = client.request("/panel/?section=" + section)
            assert status == 200 and 'id="dashboard-results"' in html
            status, csv, _ = client.request("/panel/exportar/?section=" + section)
            assert status == 200 and csv.startswith("\ufeff")
        status, inventory, _ = client.request("/panel/?section=devices")
        code = re.search(r"EQ-[A-Z2-9]{8}", inventory)[0]
        status, csv, _ = client.request("/panel/exportar/?section=devices&q=" + code)
        assert status == 200 and code in csv and len(csv.splitlines()) == 2
        assert client.request("/panel/exportar/?start=2026-12-31&end=2026-01-01")[0] == 400
        status, inbox, _ = client.request("/avisos/?state=all")
        assert status == 200
        token = Inputs(inbox).value("csrfmiddlewaretoken")
        path = re.search(r'action="(/avisos/\d+/abrir/)"', inbox)[1]
        assert client.request(path)[0] == 405
        assert client.request(path, {})[0] == 403
        if own_read_path:
            assert client.request(own_read_path, {"csrfmiddlewaretoken": token})[0] == 404
        own_read_path = path
        status, _, url = client.request(path, {"csrfmiddlewaretoken": token})
        assert status == 200 and "/mantenimientos/" in url
        print(f"HTTP correcto: {username}; panel, cinco reportes, avisos, lectura propia y CSRF.")
    print("HTTP correcto: docente sin acceso a avisos, panel ni reportes.")


if __name__ == "__main__":
    main()
