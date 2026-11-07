import csv
import io

from django.http import HttpResponse
from django.utils import timezone

REPORT_LIMIT = 10000


def report_columns(section):
    return {
        "deadlines": ["Código", "Equipo", "Preventivo", "Vencimiento", "Situación"],
        "runs": ["Preventivo", "Ejecución", "Estado", "Creación", "Cierre"],
        "unconfigured": ["Código", "Equipo", "Tipo", "Ubicación", "Estado"],
        "devices": ["Código", "Equipo", "Tipo", "Ubicación", "Estado"],
        "omissions": ["Código", "Equipo", "Preventivo", "Último ciclo omitido", "Fecha de omisión"],
        "incidents": [
            "Reporte",
            "Código",
            "Equipo",
            "Síntomas",
            "Estado",
            "Resultado",
            "Reporte (Lima)",
            "Cierre (Lima)",
        ],
        "recurrent_incidents": ["Código", "Equipo", "Ubicación", "Reportes válidos en período"],
    }[section]


def _timestamp(value):
    return timezone.localtime(value).isoformat() if value else ""


def report_values(section, row):
    if section == "incidents":
        return [
            row.pk,
            row.device.code,
            row.device.name,
            row.symptoms,
            row.get_state_display(),
            row.get_outcome_display(),
            _timestamp(row.created_at),
            _timestamp(row.closed_at),
        ]
    if section == "recurrent_incidents":
        return [row.code, row.name, row.location.name, row.incident_count]
    if section == "deadlines":
        return [
            row.target.device.code,
            row.target.device.name,
            row.target.maintenance.name,
            row.due_date.isoformat(),
            row.timing_label,
        ]
    if section == "runs":
        return [
            row.maintenance.name,
            row.number,
            row.get_state_display(),
            _timestamp(row.created_at),
            _timestamp(row.completed_at or row.cancelled_at),
        ]
    if section == "omissions":
        return [
            row.device.code,
            row.device.name,
            row.maintenance.name,
            row.omitted_cycle,
            _timestamp(row.omitted_at),
        ]
    return [
        row.code,
        row.name,
        row.category.get_kind_display(),
        row.location.name,
        row.get_status_display(),
    ]


def safe_cell(value):
    text = str(value)
    # Spreadsheet programs interpret formulas even after leading whitespace/control characters.
    if text.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")) or text.startswith(
        ("\t", "\r", "\n")
    ):
        return "'" + text
    return text


def csv_response(section, rows):
    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter=";")
    writer.writerow(report_columns(section))
    for row in rows:
        writer.writerow([safe_cell(value) for value in report_values(section, row)])
    response = HttpResponse("\ufeff" + output.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="bitacora-{section}.csv"'
    response["X-Content-Type-Options"] = "nosniff"
    return response
