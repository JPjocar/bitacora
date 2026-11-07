"""Verify the local HTTPS pilot, secure sessions, role gates and proxy login throttling."""

import argparse
import re
import ssl
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import (
    HTTPCookieProcessor,
    HTTPRedirectHandler,
    HTTPSHandler,
    Request,
    build_opener,
)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class PilotClient:
    def __init__(self, base, context):
        self.base = base
        self.cookies = CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.cookies), HTTPSHandler(context=context))

    def request(self, path, values=None, *, binary=False, **headers):
        if values is not None:
            headers.setdefault("Origin", self.base)
            headers.setdefault("Referer", self.base + path)
        request = Request(
            self.base + path,
            headers=headers,
            data=urlencode(values).encode() if values is not None else None,
        )
        try:
            response = self.opener.open(request, timeout=15)
        except HTTPError as error:
            response = error
        body = response.read()
        return response.status, body if binary else body.decode("utf8"), response.headers

    def login(self, username, password):
        status, html, _ = self.request("/cuentas/ingresar/")
        assert status == 200
        token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html)[1]
        status, html, _ = self.request(
            "/cuentas/ingresar/",
            {
                "username": username,
                "password": password,
                "csrfmiddlewaretoken": token,
            },
        )
        assert status == 200 and "Mi perfil" in html, (username, status)
        session = next(cookie for cookie in self.cookies if cookie.name == "sessionid")
        assert session.secure and session.has_nonstandard_attr("HttpOnly")
        assert next(cookie for cookie in self.cookies if cookie.name == "csrftoken").secure


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="https://localhost:8443")
    parser.add_argument("--http-url", default="http://localhost:8088")
    parser.add_argument("--ca-file", type=Path, required=True)
    parser.add_argument(
        "--credentials-file", type=Path, default=Path(".local/demo-credentials.txt")
    )
    parser.add_argument("--confirm-demo", action="store_true")
    options = parser.parse_args()
    if (
        not options.confirm_demo
        or urlsplit(options.base_url).hostname not in {"localhost", "127.0.0.1"}
        or urlsplit(options.base_url).scheme != "https"
    ):
        parser.error(
            "Use HTTPS local y --confirm-demo. Esta prueba genera intentos de login limitados."
        )
    context = ssl.create_default_context(cafile=str(options.ca_file))
    if (
        urlsplit(options.http_url).hostname not in {"localhost", "127.0.0.1"}
        or urlsplit(options.http_url).scheme != "http"
    ):
        parser.error("La comprobación de redirección debe apuntar a HTTP local.")
    try:
        build_opener(NoRedirect()).open(
            Request(options.http_url + "/", headers={"Host": "outside.invalid"}), timeout=15
        )
    except HTTPError as redirect:
        assert redirect.code == 308 and redirect.headers["Location"] == options.base_url + "/"
    else:
        raise AssertionError("Falta redirección HTTP a un origen HTTPS canónico.")
    anonymous = PilotClient(options.base_url, context)
    status, _, headers = anonymous.request("/cuentas/ingresar/")
    assert status == 200
    for key, fragment in {
        "Content-Security-Policy": "script-src 'self'",
        "Permissions-Policy": "camera=(self)",
        "X-Frame-Options": "DENY",
        "X-Content-Type-Options": "nosniff",
        "Strict-Transport-Security": "max-age=",
        "Cache-Control": "no-store",
    }.items():
        assert fragment in headers[key], key
    status, _, headers = anonymous.request("/panel/", **{"HX-Request": "true"})
    assert status == 200 and headers["HX-Redirect"].startswith("/cuentas/ingresar/")
    assert "no-store" in headers["Cache-Control"]
    assert anonymous.request("/.env")[0] == 404
    assert anonymous.request("/static/vendor/bootstrap.min.css")[0] == 200
    assert anonymous.request("/cuentas/ingresar/", Host="outside.invalid")[0] == 400
    raw = options.credentials_file.read_bytes()
    encoding = "utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
    credentials = dict(
        line.split(": ", 1)
        for line in raw.decode(encoding).splitlines()
        if line.startswith("demo_")
    )
    for username in ["demo_admin", "demo_tecnico", "demo_docente"]:
        client = PilotClient(options.base_url, context)
        client.login(username, credentials[username])
        for route, expected in [
            ("/dispositivos/", 200),
            ("/incidencias/", 200),
            ("/avisos/contador/", 200),
            ("/panel/", 403 if username == "demo_docente" else 200),
            ("/panel/exportar/", 403 if username == "demo_docente" else 200),
            ("/cuentas/usuarios/", 200 if username == "demo_admin" else 403),
        ]:
            assert client.request(route)[0] == expected, (username, route)
        assert client.request("/cuentas/salir/", {})[0] == 403
        # Decode the actual server PNG with an independent QR reader, also after Pillow updates.
        from io import BytesIO

        import zxingcpp
        from PIL import Image

        _, devices, _ = client.request("/dispositivos/")
        device_path = re.search(r'href="(/dispositivos/[0-9a-f-]+/)"', devices)[1]
        status, png, _ = client.request(device_path + "qr.png", binary=True)
        assert status == 200 and png.startswith(b"\x89PNG")
        assert (
            zxingcpp.read_barcode(Image.open(BytesIO(png))).text == options.base_url + device_path
        )
        if username == "demo_admin":
            status, html, _ = client.request(
                "/panel/",
                **{
                    "HX-Request": "true",
                    "HX-History-Restore-Request": "true",
                    "X-Forwarded-Proto": "http",
                    "Forwarded": "proto=http;host=outside.invalid",
                },
            )
            assert status == 200 and "<!doctype" in html
        print(f"HTTPS correcto: {username}; cookies seguras, permisos y CSRF.")
    status, html, _ = anonymous.request("/cuentas/ingresar/")
    token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html)[1]
    for attempt in range(15):
        status, _, headers = anonymous.request(
            "/cuentas/ingresar/",
            {
                "username": "pilot_nonexistent_account",
                "password": "synthetic-wrong-password",
                "csrfmiddlewaretoken": token,
            },
            **{"X-Forwarded-For": f"192.0.2.{attempt + 1}"},
        )
        assert status in {200, 429}, status
        if status == 429:
            assert headers["Retry-After"] == "60"
            print(
                "HTTPS correcto: proxy limita login con 429, aunque se falsifique X-Forwarded-For."
            )
            break
    else:
        raise AssertionError("El proxy no limitó los intentos de login.")


if __name__ == "__main__":
    main()
