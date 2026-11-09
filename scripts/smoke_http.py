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
    parser.add_argument("--assets", action="store_true", help="Verifica también seed_assets_demo.")
    parser.add_argument(
        "--qr", action="store_true", help="Verifica también QR, etiquetas y escáner."
    )
    parser.add_argument("--maintenance", action="store_true", help="Verifica la demo preventiva.")
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

        def request(path, data=None, headers=None, binary=False, _client=client):
            req = Request(options.base_url + path, data=data, headers=headers or {})
            try:
                response = _client.open(req, timeout=10)
            except HTTPError as error:
                response = error
            body = response.read()
            return response.status, body if binary else body.decode("utf-8"), response.geturl()

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
        if options.assets or options.qr:
            status, listing, _ = request("/dispositivos/")
            assert status == 200 and "EQ-" in listing
            detail_path = re.search(r'href="(/dispositivos/[0-9a-f-]+/)"', listing)[1]
            status, detail, _ = request(detail_path)
            assert status == 200 and "Ubicación actual" in detail
            status, fragment, _ = request(
                "/dispositivos/?q=demostraci%C3%B3n", headers={"HX-Request": "true"}
            )
            assert status == 200 and 'id="results"' in fragment and "<!doctype" not in fragment
            expected_operations = 403 if username == "demo_docente" else 200
            assert request(detail_path + "trasladar/")[0] == expected_operations
            assert request(detail_path + "estado/")[0] == expected_operations
            assert request("/dispositivos/movimientos/")[0] == expected_operations
            assert request("/dispositivos/categorias/")[0] == expected_operations
            assert request("/dispositivos/nuevo/")[0] == expected_users
            if username == "demo_docente":
                assert "Datos ficticios" not in detail and "Historial de cambios" not in detail
            else:
                status, movements, _ = request("/dispositivos/movimientos/")
                movement_path = re.search(r'href="(/dispositivos/movimientos/[0-9]+/)"', movements)[
                    1
                ]
                assert request(movement_path)[0] == 200
            print(f"HTTP correcto: {username}; dispositivos, ficha, categorías y movimientos.")
            if options.qr:
                from io import BytesIO

                import zxingcpp
                from PIL import Image

                status, png, _ = request(detail_path + "qr.png", binary=True)
                assert status == 200 and png.startswith(b"\x89PNG")
                payload = zxingcpp.read_barcode(Image.open(BytesIO(png))).text
                assert payload.endswith(detail_path)
                status, scanner, _ = request("/dispositivos/escaner/")
                assert status == 200 and "Buscar manualmente" in scanner
                token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', scanner)[1]
                for query in (payload, re.search(r"EQ-[A-Z2-9]{8}", detail)[0].lower()):
                    status, _, url = request(
                        "/dispositivos/escaner/",
                        urlencode({"query": query, "csrfmiddlewaretoken": token}).encode(),
                    )
                    assert status == 200 and url == options.base_url + detail_path
                status, invalid, url = request(
                    "/dispositivos/escaner/",
                    urlencode(
                        {"query": "https://external.example/", "csrfmiddlewaretoken": token}
                    ).encode(),
                )
                assert status == 200 and "Código no reconocido" in invalid
                assert url == options.base_url + "/dispositivos/escaner/"
                identifier = detail_path.rstrip("/").rsplit("/", 1)[1]
                for data in (
                    None,
                    urlencode(
                        {"device": [identifier, identifier], "csrfmiddlewaretoken": token},
                        doseq=True,
                    ).encode(),
                ):
                    status, labels, _ = request(
                        "/dispositivos/etiquetas/?device=" + identifier, data=data
                    )
                    assert status == expected_operations
                    if status == 200:
                        assert labels.count('class="device-label"') == 1
                print(f"HTTP correcto: {username}; PNG decodificado, etiquetas y escáner seguro.")
        if options.maintenance:
            status, listing, _ = request("/mantenimientos/")
            assert status == (403 if username == "demo_docente" else 200)
            assert request("/mantenimientos/nuevo/")[0] == expected_users
            status, picker, _ = request(
                "/mantenimientos/equipos/selector/", headers={"HX-Request": "true"}
            )
            assert status == expected_users
            if username == "demo_admin":
                assert 1 <= picker.count("data-picker-device") <= 20
                code = re.search(r"EQ-[A-Z2-9]{8}", picker)[0]
                for selection in ({"mode": "scan", "query": code}, {"mode": "all", "q": code}):
                    status, cards, _ = request(
                        "/mantenimientos/equipos/selector/?" + urlencode(selection)
                    )
                    assert status == 200 and "data-picker-selection" in cards
                    assert cards.count("<template data-picker-card=") == 1 and code in cards
                status, rejected, _ = request(
                    "/mantenimientos/equipos/selector/?"
                    + urlencode({"mode": "scan", "query": "https://external.example/"})
                )
                assert status == 200 and "Código no reconocido" in rejected
                assert "data-picker-card=" not in rejected
            if username != "demo_docente":
                maintenance_path = re.search(r'href="(/mantenimientos/[0-9]+/)"', listing)[1]
                status, detail, _ = request(maintenance_path)
                assert status == 200 and "Trabajo preventivo" in detail
                assert "Tareas realizadas:" in detail
                assert request(maintenance_path + "historial/")[0] == 200
                assert request(maintenance_path + "editar/")[0] == expected_users
                status, fragment, _ = request(
                    "/mantenimientos/?q=demostraci%C3%B3n", headers={"HX-Request": "true"}
                )
                assert status == 200 and 'id="results"' in fragment and "<!doctype" not in fragment
            if username == "demo_admin":
                for mode, field in (("unique", "planned_date"), ("recurring", "base_date")):
                    status, form_html, _ = request("/mantenimientos/nuevo/?kind=" + mode)
                    assert status == 200 and f'name="{field}"' in form_html
                    assert 'id="device-grid"' in form_html and 'id="device-add"' in form_html
                    assert "data-device-card" not in form_html
            print(f"HTTP correcto: {username}; preventivos, configuración, permisos e historial.")
        token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', home)[1]
        assert (
            request("/cuentas/salir/", urlencode({"csrfmiddlewaretoken": token}).encode())[0] == 200
        )
        print(f"HTTP correcto: {username}; login, perfil, permisos, filtros y logout.")
    for filename in ["bootstrap.min.css", "bootstrap.bundle.min.js", "htmx.min.js"]:
        assert request(f"/static/vendor/{filename}")[0] == 200
    print("HTTP correcto: recursos Bootstrap y HTMX locales.")
    if options.maintenance:
        for path in ["js/device-picker.js", "css/maintenance.css"]:
            assert request(f"/static/{path}")[0] == 200
        print("HTTP correcto: selector paginado, selección filtrada, código y recursos locales.")
    if options.qr:
        for path in [
            "vendor/html5-qrcode.min.js",
            "js/qr-controller.js",
            "js/scanner.js",
            "js/labels.js",
            "css/labels.css",
        ]:
            assert request(f"/static/{path}")[0] == 200
        print("HTTP correcto: lector QR, control de cámara y estilos de impresión locales.")


if __name__ == "__main__":
    main()
