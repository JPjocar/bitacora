from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_safe

from apps.assets.models import Device
from apps.assets.selectors import visible_devices
from apps.core.forms import add_validation_errors
from apps.core.permissions import require_permission

from . import services
from .forms import ActionForm, IncidentFilters, ReportForm
from .selectors import can_control, visible_incidents

ACTIONS = {
    "tomar": ("Tomar incidencia", services.take_incident),
    "nota": ("Registrar nota técnica", services.add_note),
    "liberar": ("Liberar incidencia", services.release_incident),
    "cerrar": ("Cerrar incidencia", services.close_incident),
}


@login_required
@require_safe
def incident_list(request):
    incidents = visible_incidents(request.user)
    form = IncidentFilters(
        request.GET,
        visible_reports=None if request.user.has_perm("incidents.view_incident") else incidents,
    )
    if form.is_valid():
        filters = form.cleaned_data
        if filters["q"]:
            query = filters["q"]
            incidents = incidents.filter(
                Q(device__code__icontains=query)
                | Q(device__name__icontains=query)
                | Q(symptoms__icontains=query)
            )
        for field, lookup in [
            ("state", "state"),
            ("outcome", "outcome"),
            ("location", "device__location"),
            ("kind", "device__category__kind"),
            ("start", "created_at__date__gte"),
            ("end", "created_at__date__lte"),
        ]:
            if filters[field]:
                incidents = incidents.filter(**{lookup: filters[field]})
    else:
        incidents = incidents.none()
    context = {"form": form, "page_obj": Paginator(incidents, 20).get_page(request.GET.get("page"))}
    partial = request.htmx and not request.htmx.history_restore_request
    return render(request, "incidents/results.html" if partial else "incidents/list.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def report(request, public_id):
    require_permission(request.user, "incidents.add_incident")
    device = get_object_or_404(visible_devices(request.user), public_id=public_id)
    if not device.is_active or device.status == Device.Status.WITHDRAWN:
        raise PermissionDenied("El equipo está archivado o retirado. Su historial se conserva.")
    form = ReportForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            incident = services.report_incident(
                actor=request.user, device_id=device.pk, **form.cleaned_data
            )
        except ValidationError as error:
            add_validation_errors(form, error)
        else:
            messages.success(
                request, "Incidencia registrada. Se avisó a técnicos y administradores."
            )
            return redirect(incident)
    return render(request, "incidents/report.html", {"form": form, "device": device})


@login_required
@require_safe
def detail(request, pk):
    incident = get_object_or_404(visible_incidents(request.user), pk=pk)
    full = request.user.has_perm("incidents.view_incident")
    events = incident.events.select_related("actor")
    if not full:
        events = events.exclude(action="INC_NOTE")
    # An archived asset can still have a report the teacher is entitled to follow.
    device_visible = (
        request.user.has_perm("assets.view_device")
        or request.user.has_perm("assets.view_device_limited")
    ) and visible_devices(request.user).filter(pk=incident.device_id).exists()
    return render(
        request,
        "incidents/detail.html",
        {
            "incident": incident,
            "full_access": full,
            "device_visible": device_visible,
            "can_control": full and can_control(request.user, incident),
            "events": Paginator(events, 20).get_page(request.GET.get("page")),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def action(request, pk, action):
    if action not in ACTIONS:
        raise Http404
    actor = require_permission(request.user, "incidents.view_incident")
    incident = get_object_or_404(visible_incidents(actor), pk=pk)
    if action == "tomar":
        require_permission(actor, "incidents.take_incident")
    elif not can_control(actor, incident):
        raise PermissionDenied
    form = ActionForm(
        request.POST if request.method == "POST" else None,
        incident=incident,
        action=action,
        actor=actor,
    )
    if request.method == "POST" and form.is_valid():
        values = dict(form.cleaned_data)
        values["expected_version"] = values.pop("version")
        try:
            ACTIONS[action][1](actor=actor, incident_id=incident.pk, **values)
        except ValidationError as error:
            add_validation_errors(form, error)
        else:
            messages.success(request, "Operación registrada. El historial se conservó.")
            return redirect(incident)
    return render(
        request,
        "incidents/action.html",
        {
            "form": form,
            "incident": incident,
            "title": ACTIONS[action][0],
            "action": action,
        },
    )
