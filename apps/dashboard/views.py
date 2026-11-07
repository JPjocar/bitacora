from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponseBadRequest
from django.shortcuts import render
from django.views.decorators.http import require_safe

from apps.core.permissions import require_permission

from .forms import SECTIONS, DashboardFilters
from .reports import REPORT_LIMIT, csv_response, report_columns, report_values
from .selectors import dashboard_data


def _access(actor):
    actor = require_permission(actor, "assets.view_device")
    return require_permission(actor, "maintenance.view_maintenance")


@login_required
@require_safe
def panel(request):
    _access(request.user)
    form = DashboardFilters(request.GET)
    context = {"form": form}
    if form.is_valid():
        context.update(dashboard_data(form.cleaned_data))
        context["page_obj"] = Paginator(context.pop("rows"), 20).get_page(request.GET.get("page"))
        context["section_label"] = dict(SECTIONS)[context["section"]]
    template = "dashboard/results.html" if request.htmx else "dashboard/panel.html"
    return render(request, template, context)


@login_required
@require_safe
def report(request, output):
    _access(request.user)
    form = DashboardFilters(request.GET)
    if not form.is_valid():
        return render(request, "dashboard/panel.html", {"form": form}, status=400)
    data = dashboard_data(form.cleaned_data)
    if output == "csv" and data["invalid_targets"]:
        return HttpResponseBadRequest(
            "Hay fechas preventivas inválidas. Revise las advertencias del panel antes de exportar."
        )
    rows = data.pop("rows")
    count = len(rows) if isinstance(rows, list) else rows.count()
    if count > REPORT_LIMIT:
        return HttpResponseBadRequest("El reporte supera 10 000 filas. Reduzca los filtros.")
    if output == "csv":
        return csv_response(data["section"], rows)
    data.update(
        {
            "columns": report_columns(data["section"]),
            "values": [report_values(data["section"], row) for row in rows],
            "section_label": dict(SECTIONS)[data["section"]],
            "form": form,
        }
    )
    applied = []
    for name, value in form.cleaned_data.items():
        if not value or name == "section":
            continue
        field = form.fields[name]
        if getattr(field, "choices", None) is not None and name != "location":
            value = dict(field.choices).get(value, value)
        if name == "location":
            value = value.name
        applied.append((field.label, value))
    data["applied_filters"] = applied
    return render(request, "dashboard/print.html", data)
