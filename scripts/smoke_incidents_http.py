"""Exercise three corrective outcomes by HTTP using existing synthetic demo accounts."""

import argparse
import re
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from smoke_execution_http import DemoClient, Inputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--credentials-file", default=".local/demo-credentials.txt")
    parser.add_argument("--confirm-demo", action="store_true")
    options = parser.parse_args()
    if not options.confirm_demo or urlsplit(options.base_url).hostname not in (
        "localhost",
        "127.0.0.1",
    ):
        parser.error(
            "Requiere --confirm-demo y servidor local; crea y conserva tres reportes sintéticos."
        )
    raw = Path(options.credentials_file).read_bytes()
    encoding = "utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
    credentials = dict(
        line.split(": ", 1)
        for line in raw.decode(encoding).splitlines()
        if line.startswith("demo_")
    )
    admin, tech, teacher = [DemoClient(options.base_url) for _ in range(3)]
    for client, username in [
        (admin, "demo_admin"),
        (tech, "demo_tecnico"),
        (teacher, "demo_docente"),
    ]:
        client.login(username, credentials[username])

    status, devices, _ = teacher.request("/dispositivos/")
    assert status == 200
    device_path = re.search(r'href="(/dispositivos/[0-9a-f-]+/)"', devices)[1]
    status, sheet, _ = teacher.request(device_path)
    assert status == 200 and "Reportar incidencia" in sheet
    code = re.search(r"EQ-[A-Z2-9]{8}", sheet)[0]
    report_path = re.search(r'href="(/incidencias/reportar/[0-9a-f-]+/)"', sheet)[1]
    _, scanner, _ = teacher.request("/dispositivos/escaner/")
    status, _, url = teacher.request(
        "/dispositivos/escaner/",
        {
            "csrfmiddlewaretoken": Inputs(scanner).value("csrfmiddlewaretoken"),
            "query": code.lower(),
        },
    )
    assert status == 200 and url == options.base_url + device_path
    marker = uuid4().hex[:8]

    def create(client, symptoms):
        status, html, _ = client.request(report_path)
        assert status == 200
        inputs = Inputs(html)
        values = {
            "csrfmiddlewaretoken": inputs.value("csrfmiddlewaretoken"),
            "creation_key": inputs.value("creation_key"),
            "symptoms": symptoms,
        }
        status, detail, url = client.request(report_path, values)
        assert status == 200 and "Pendiente de atención" in detail
        incident_path = url.removeprefix(options.base_url)
        assert re.fullmatch(r"/incidencias/\d+/", incident_path)
        status, _, repeated_url = client.request(report_path, values)
        assert status == 200 and repeated_url == url
        return incident_path

    def action(client, path, name, **values):
        endpoint = path + name + "/"
        status, html, _ = client.request(endpoint)
        assert status == 200, (endpoint, status)
        inputs = Inputs(html)
        fields = {
            "csrfmiddlewaretoken": inputs.value("csrfmiddlewaretoken"),
            "version": inputs.value("version"),
            **values,
        }
        status, detail, url = client.request(endpoint, fields)
        assert status == 200 and url == options.base_url + path, (endpoint, status, url)
        return detail, fields

    solved = create(teacher, "Verificación HTTP de conexión " + marker)
    for client in [admin, tech]:
        status, inbox, _ = client.request("/avisos/")
        incident_number = solved.strip("/").split("/")[-1]
        assert status == 200 and f"Incidencia #{incident_number}. Disponible" in inbox
    assert teacher.request(solved + "tomar/")[0] == 403
    assert admin.request(solved + "tomar/")[0] == 403
    assert tech.request(solved + "tomar/", {})[0] == 403
    action(tech, solved, "tomar")
    private_note = "Comprobación interna reservada " + marker
    action(tech, solved, "nota", note=private_note)
    detail, _ = action(
        tech,
        solved,
        "liberar",
        reason="Continuará atención " + marker,
        summary="Prueba técnica parcial " + marker,
    )
    assert private_note in detail and "Pendiente de atención" in detail
    assert private_note not in teacher.request(solved)[1]
    assert "Incidencia liberada" in tech.request("/avisos/")[1]
    action(tech, solved, "tomar")
    public_summary = "Conectividad verificada satisfactoriamente " + marker
    detail, close_values = action(
        tech, solved, "cerrar", outcome="SOLUCIONADA", summary=public_summary
    )
    assert "Solucionada" in detail and public_summary in teacher.request(solved)[1]
    status, rejected, url = tech.request(solved + "cerrar/", close_values)
    assert status == 200 and url.endswith("/cerrar/") and "La incidencia cambió" in rejected
    status, inbox, _ = teacher.request("/avisos/")
    assert status == 200 and f"Incidencia #{incident_number}: Solucionada" in inbox
    article = next(
        block
        for block in re.findall(r"<article\b.*?</article>", inbox, re.S)
        if f"Incidencia #{incident_number}:" in block
    )
    read_path = re.search(r'action="(/avisos/\d+/abrir/)"', article)[1]
    status, _, url = teacher.request(
        read_path, {"csrfmiddlewaretoken": Inputs(article).value("csrfmiddlewaretoken")}
    )
    assert status == 200 and url == options.base_url + solved

    unrepairable = create(admin, "Verificación HTTP daño no reparable " + marker)
    assert teacher.request(unrepairable)[0] == 404
    action(tech, unrepairable, "tomar")
    assert 'value="NO_REPARABLE"' not in tech.request(unrepairable + "cerrar/")[1]
    detail, _ = action(
        admin,
        unrepairable,
        "cerrar",
        outcome="NO_REPARABLE",
        summary="Daño técnico verificado; falla persiste " + marker,
        reason="Imposibilidad técnica confirmada " + marker,
    )
    assert "No reparable" in detail
    invalid = create(tech, "Verificación HTTP reporte duplicado " + marker)
    detail, _ = action(
        admin,
        invalid,
        "cerrar",
        outcome="INVALIDA_DUPLICADA",
        summary="Reporte sintético duplicado " + marker,
        reason="Depuración del reporte " + marker,
    )
    assert "Inválida o duplicada" in detail
    for section in ["incidents", "recurrent_incidents"]:
        assert admin.request("/panel/?section=" + section)[0] == 200
        status, csv, _ = tech.request("/panel/exportar/?section=" + section)
        assert status == 200 and csv.startswith("\ufeff") and code in csv
        assert teacher.request("/panel/exportar/?section=" + section)[0] == 403
    assert "Historial preventivo del equipo" in admin.request(device_path)[1]
    assert "Historial preventivo del equipo" not in teacher.request(device_path)[1]
    print(
        f"HTTP correcto: {solved} solucionada, {unrepairable} no reparable, "
        f"{invalid} inválida/duplicada."
    )
    print(
        "Verificados: QR/código, reenvío, permisos, CSRF, liberación, notas privadas, "
        "aviso al reportante, ficha y reportes."
    )


if __name__ == "__main__":
    main()
