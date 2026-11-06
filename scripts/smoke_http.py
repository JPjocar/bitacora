"""Read-only HTTP smoke check (except login/logout) against the running demo server."""

import argparse
import re
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--credentials-file", default=".local/demo-credentials.txt")
    options = parser.parse_args()
    raw = Path(options.credentials_file).read_bytes()
    encoding = "utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
    credentials = dict(
        line.split(": ", 1)
        for line in raw.decode(encoding).splitlines()
        if line.startswith("demo_")
    )
    for username, password in credentials.items():
        client = build_opener(HTTPCookieProcessor(CookieJar()))

        def request(path, data=None, headers=None, _client=client):
            req = Request(options.base_url + path, data=data, headers=headers or {})
            try:
                response = _client.open(req, timeout=10)
            except HTTPError as error:
                response = error
            return response.status, response.read().decode("utf-8"), response.geturl()

        status, login, _ = request("/cuentas/ingresar/")
        assert status == 200
        token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', login)[1]
        status, home, url = request(
            "/cuentas/ingresar/",
            urlencode(
                {
                    "username": username,
                    "password": password,
                    "csrfmiddlewaretoken": token,
                }
            ).encode(),
        )
        assert status == 200 and url == options.base_url + "/", (username, status, url)
        assert "Mi perfil" in home
        assert request("/cuentas/perfil/")[0] == 200
        expected_users = 200 if username == "demo_admin" else 403
        assert request("/cuentas/usuarios/")[0] == expected_users
        assert request("/cuentas/roles/")[0] == expected_users
        expected_locations = 403 if username == "demo_docente" else 200
        assert request("/ubicaciones/")[0] == expected_locations
        if expected_locations == 200:
            status, fragment, _ = request(
                "/ubicaciones/?q=DEMO-LAB", headers={"HX-Request": "true"}
            )
            assert status == 200 and 'id="results"' in fragment and "<!doctype" not in fragment
            assert "DEMO-LAB" in fragment
        if username == "demo_admin":
            for path in ["/ubicaciones/nueva/", "/cuentas/usuarios/nuevo/", "/cuentas/contrasena/"]:
                assert request(path)[0] == 200
        token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', home)[1]
        assert (
            request("/cuentas/salir/", urlencode({"csrfmiddlewaretoken": token}).encode())[0] == 200
        )
        print(f"HTTP correcto: {username}; login, perfil, permisos, filtros y logout.")
    for filename in ["bootstrap.min.css", "bootstrap.bundle.min.js", "htmx.min.js"]:
        assert request(f"/static/vendor/{filename}")[0] == 200
    print("HTTP correcto: recursos Bootstrap y HTMX locales.")


if __name__ == "__main__":
    main()
