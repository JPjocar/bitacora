"""Exercise synthetic preventive work by HTTP against the local development server."""

import argparse
import re
from html.parser import HTMLParser
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener
from uuid import uuid4


class Inputs(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.fields = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == "input":
            self.fields.append(dict(attrs))

    def value(self, name):
        return next(field.get("value", "") for field in self.fields if field.get("name") == name)


class DemoClient:
    def __init__(self, base):
        self.base = base
        self.client = build_opener(HTTPCookieProcessor(CookieJar()))

    def request(self, path, data=None):
        request = Request(
            self.base + path,
            data=urlencode(data, doseq=True).encode() if data is not None else None,
            headers={"Origin": self.base, "Referer": self.base + path}
            if data is not None and urlsplit(self.base).scheme == "https"
            else {},
        )
        try:
            response = self.client.open(request, timeout=15)
        except HTTPError as error:
            response = error
        return response.status, response.read().decode("utf-8"), response.geturl()

    def login(self, username, password):
        status, html, _ = self.request("/cuentas/ingresar/")
        assert status == 200
        status, _, url = self.request(
            "/cuentas/ingresar/",
            {
                "username": username,
                "password": password,
                "csrfmiddlewaretoken": Inputs(html).value("csrfmiddlewaretoken"),
            },
        )
        assert status == 200 and url == self.base + "/"

    def action(self, path, **values):
        status, html, _ = self.request(path)
        assert status == 200, (path, status)
        inputs = Inputs(html)
        status, detail, url = self.request(
            path,
            {
                "csrfmiddlewaretoken": inputs.value("csrfmiddlewaretoken"),
                "version": inputs.value("version"),
                **values,
            },
        )
        assert status == 200 and re.fullmatch(
            re.escape(self.base) + r"/mantenimientos/\d+/", url
        ), (path, status, url)
        return detail


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--credentials-file", default=".local/demo-credentials.txt")
    parser.add_argument("--confirm-demo", action="store_true")
    parser.add_argument(
        "--recurrence",
        action="store_true",
        help="Crea también un segundo ciclo periódico y verifica su historial.",
    )
    options = parser.parse_args()
    if not options.confirm_demo or urlsplit(options.base_url).hostname not in (
        "localhost",
        "127.0.0.1",
    ):
        parser.error(
            "Requiere --confirm-demo y un servidor local. Se crea un preventivo sintético."
        )
    raw = Path(options.credentials_file).read_bytes()
    encoding = "utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
    credentials = dict(
        line.split(": ", 1)
        for line in raw.decode(encoding).splitlines()
        if line.startswith("demo_")
    )
    admin, technician, teacher = [DemoClient(options.base_url) for _ in range(3)]
    for client, username in (
        (admin, "demo_admin"),
        (technician, "demo_tecnico"),
        (teacher, "demo_docente"),
    ):
        client.login(username, credentials[username])
    kind = "recurring" if options.recurrence else "unique"
    status, html, _ = admin.request("/mantenimientos/nuevo/?kind=" + kind)
    assert status == 200
    fields = Inputs(html)
    date_fields = (
        {"base_date": fields.value("base_date"), "interval_value": 2, "interval_unit": "MESES"}
        if options.recurrence
        else {"planned_date": fields.value("planned_date")}
    )
    devices = [field["value"] for field in fields.fields if field.get("name") == "devices"][:2]
    assert len(devices) == 2, "Requiere seed_assets_demo con dos equipos activos."
    name = "Verificación HTTP preventiva " + uuid4().hex[:8]
    status, detail, url = admin.request(
        "/mantenimientos/nuevo/",
        {
            "csrfmiddlewaretoken": fields.value("csrfmiddlewaretoken"),
            "creation_key": fields.value("creation_key"),
            "kind": kind,
            "name": name,
            **date_fields,
            "devices": devices,
            "tasks-TOTAL_FORMS": 2,
            "tasks-INITIAL_FORMS": 0,
            "tasks-0-name": "Revisar conexiones",
            "tasks-0-scope": "DISPOSITIVO",
            "tasks-0-required": "on",
            "tasks-0-ORDER": 1,
            "tasks-1-name": "Preparar materiales",
            "tasks-1-scope": "GRUPAL",
            "tasks-1-required": "on",
            "tasks-1-ORDER": 2,
        },
    )
    assert status == 200 and name in detail and "Pendiente de atención" in detail
    maintenance_path = url.removeprefix(options.base_url)
    run_id = re.search(r"/mantenimientos/ejecuciones/(\d+)/", detail)[1]
    base = f"/mantenimientos/ejecuciones/{run_id}/"
    assert admin.request(base + "tomar/")[0] == 403
    assert teacher.request(base + "tomar/")[0] == 403
    technician.action(base + "tomar/")
    detail = technician.action(base + "iniciar/")
    participants = list(dict.fromkeys(re.findall(r"/equipos/(\d+)/avances/", detail)))
    assert len(participants) == 2
    first, second = participants
    path = base + f"equipos/{first}/avances/"
    _, html, _ = technician.request(path)
    task_fields = {
        field["name"]: "on"
        for field in Inputs(html).fields
        if field.get("name", "").startswith("task_")
    }
    technician.action(path, notes="Conexiones verificadas antes de liberar", **task_fields)
    technician.action(
        base + "liberar/", reason="Conexiones revisadas; se libera por cambio de turno"
    )
    detail = technician.action(base + "tomar/")
    assert "Reanudar mantenimiento" in detail
    technician.action(base + "iniciar/")
    technician.action(
        base + f"equipos/{first}/completar/",
        verified="on",
        completion_summary="Equipo verificado; conexiones correctas",
    )
    technician.action(
        base + f"equipos/{second}/omitir/", reason="No disponible para verificación sintética"
    )
    _, html, _ = technician.request(base + "avances/")
    group_fields = {
        field["name"]: "on"
        for field in Inputs(html).fields
        if field.get("name", "").startswith("task_")
    }
    technician.action(base + "avances/", notes="Materiales retirados", **group_fields)
    detail = technician.action(base + "cerrar/")
    assert "Completado parcialmente" in detail
    assert "Conexiones verificadas antes de liberar" in detail
    assert "Equipo verificado; conexiones correctas" in detail
    assert "No disponible para verificación sintética" in detail
    status, history, _ = admin.request(maintenance_path + "historial/")
    assert status == 200
    for action in (
        "Mantenimiento tomado",
        "Trabajo iniciado",
        "Responsable liberado",
        "Trabajo reanudado",
        "Equipo completado",
        "Equipo omitido",
        "Mantenimiento completado parcialmente",
    ):
        assert action in history, action
    assert teacher.request(maintenance_path)[0] == 403
    print(
        "HTTP correcto: creación, permisos, toma, inicio, avances, liberación, "
        "reanudación, completado, omisión, cierre parcial e historial."
    )
    print("Registro sintético conservado: " + maintenance_path)
    if options.recurrence:
        status, calendar, _ = technician.request(maintenance_path + "vencimientos/")
        assert status == 200 and "Sin ejecución completada" in calendar
        assert teacher.request(maintenance_path + "vencimientos/")[0] == 403
        next_path = maintenance_path + "siguiente/"
        status, html, _ = technician.request(next_path)
        assert status == 200
        fields = Inputs(html)
        selection = [field["value"] for field in fields.fields if field.get("name") == "targets"]
        assert len(selection) == 2
        data = {
            "csrfmiddlewaretoken": fields.value("csrfmiddlewaretoken"),
            "version": fields.value("version"),
            "previous_run_id": fields.value("previous_run_id"),
            "targets": selection,
            "reason": "Revisión anticipada sintética de segundo ciclo",
        }
        status, current, url = technician.request(next_path, data)
        assert status == 200 and "Consulta de la ejecución 2" in current
        assert "Pendiente de atención" in current
        assert current.count("Tareas realizadas: 0 / 1") == 2
        assert "Conexiones verificadas antes de liberar" not in current
        new_id = re.search(r"/ejecuciones/(\d+)/", url)[1]
        assert new_id != run_id
        status, historic, _ = technician.request(maintenance_path + f"ejecuciones/{run_id}/")
        assert status == 200 and "Completado parcialmente" in historic
        assert "Conexiones verificadas antes de liberar" in historic
        status, _, replay_url = technician.request(next_path, data)
        assert status == 200 and replay_url == options.base_url + next_path
        status, history, _ = technician.request(maintenance_path + "ejecuciones/")
        assert status == 200
        assert len(re.findall(r'href="/mantenimientos/\d+/ejecuciones/\d+/"', history)) == 2
        status, events, _ = technician.request(maintenance_path + "historial/?run=" + new_id)
        assert status == 200 and "Siguiente ejecución creada" in events
        assert "Equipo completado" not in events
        print(
            "HTTP correcto: calendario individual, segunda ejecución con tareas limpias, "
            "reenvío rechazado e historial anterior conservado."
        )


if __name__ == "__main__":
    main()
