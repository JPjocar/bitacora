from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_safe
from django.views.decorators.vary import vary_on_headers

from apps.core.forms import add_validation_errors

from .models import Maintenance, MaintenanceRun
from .recurrence import create_next_run
from .recurrence_forms import NextRunForm
from .selectors import SOON_DAYS, TIMING_LABELS, target_schedule


@login_required
@permission_required("maintenance.view_maintenance", raise_exception=True)
@require_safe
@vary_on_headers("HX-Request")
def due_dates(request, pk):
    maintenance = get_object_or_404(Maintenance, pk=pk)
    query = request.GET.get("q", "").strip()[:120]
    timing = request.GET.get("timing", "")
    calendar_error = ""
    try:
        rows = target_schedule(maintenance) if maintenance.is_recurring else []
    except ValidationError as error:
        rows = []
        calendar_error = "Revise la configuración de fechas: " + " ".join(error.messages)
    if query:
        folded = query.casefold()
        rows = [
            row
            for row in rows
            if folded in row.target.device.code.casefold()
            or folded in row.target.device.name.casefold()
        ]
    if timing in TIMING_LABELS:
        rows = [row for row in rows if row.timing == timing]
    template = (
        "maintenance/_due_dates.html"
        if request.htmx and not request.htmx.history_restore_request
        else "maintenance/due_dates.html"
    )
    return render(
        request,
        template,
        {
            "maintenance": maintenance,
            "page_obj": Paginator(rows, 20).get_page(request.GET.get("page")),
            "q": query,
            "timing": timing,
            "timings": TIMING_LABELS.items(),
            "soon_days": SOON_DAYS,
            "calendar_error": calendar_error,
        },
    )


@login_required
@permission_required("maintenance.view_maintenance", raise_exception=True)
@require_safe
def executions(request, pk):
    maintenance = get_object_or_404(Maintenance, pk=pk)
    state = request.GET.get("state", "")
    runs = (
        maintenance.runs.select_related("responsible", "closed_by")
        .annotate(
            total_count=Count("participants"),
            completed_count=Count("participants", filter=Q(participants__result="COMPLETADO")),
            omitted_count=Count("participants", filter=Q(participants__result="OMITIDO")),
        )
        .order_by("-number")
    )
    if state in MaintenanceRun.State.values:
        runs = runs.filter(state=state)
    return render(
        request,
        "maintenance/executions.html",
        {
            "maintenance": maintenance,
            "page_obj": Paginator(runs, 20).get_page(request.GET.get("page")),
            "state": state,
            "states": MaintenanceRun.State.choices,
        },
    )


@login_required
@permission_required("maintenance.create_next_run", raise_exception=True)
@require_http_methods(["GET", "POST"])
def next_run(request, pk):
    maintenance = get_object_or_404(Maintenance, pk=pk)
    previous = maintenance.runs.first()
    try:
        schedules = target_schedule(maintenance) if maintenance.is_recurring else []
        calendar_error = ""
    except ValidationError as error:
        schedules = []
        calendar_error = "Revise la configuración de fechas: " + " ".join(error.messages)
    blocked = ""
    if not maintenance.is_recurring or not maintenance.is_active:
        blocked = "Solo un mantenimiento periódico activo permite una siguiente ejecución."
    elif previous is None or previous.is_open:
        blocked = "Cierre la ejecución actual antes de crear la siguiente."
    if calendar_error:
        blocked = calendar_error
    form = NextRunForm(
        request.POST if request.method == "POST" else None,
        maintenance=maintenance,
        previous_run=previous,
        schedules=schedules,
    )
    if request.method == "POST" and form.is_valid():
        try:
            run = create_next_run(
                actor=request.user,
                maintenance_id=maintenance.pk,
                expected_version=form.cleaned_data["version"],
                previous_run_id=form.cleaned_data["previous_run_id"],
                target_ids=[int(value) for value in form.cleaned_data["targets"]],
                reason=form.cleaned_data["reason"],
            )
        except ValidationError as error:
            add_validation_errors(form, error)
        else:
            messages.success(
                request,
                "Siguiente ejecución creada pendiente de atención, con tareas nuevas sin marcar.",
            )
            return redirect("maintenance:run_detail", pk=maintenance.pk, run_id=run.pk)
    return render(
        request,
        "maintenance/next_run.html",
        {
            "maintenance": maintenance,
            "form": form,
            "blocked": blocked,
            "schedules": schedules,
            "previous": previous,
        },
    )
