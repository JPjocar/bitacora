from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, OuterRef, Q, Subquery
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_safe
from django.views.decorators.vary import vary_on_headers

from apps.assets.qr import resolve_scan
from apps.core.forms import add_validation_errors
from apps.locations.models import Location

from .execution import can_control
from .forms import MaintenanceForm, TaskFormSet
from .models import Maintenance, MaintenanceRun, MaintenanceRunDevice
from .selectors import OPEN_STATES, eligible_devices, list_schedules
from .services import MAX_TARGETS, MAX_TASKS, save_maintenance, template_data


@login_required
@permission_required("maintenance.view_maintenance", raise_exception=True)
@require_safe
@vary_on_headers("HX-Request")
def maintenance_list(request):
    query = request.GET.get("q", "").strip()[:120]
    kind = request.GET.get("kind", "")
    active = request.GET.get("active", "")
    state = request.GET.get("state", "")
    latest = MaintenanceRun.objects.filter(maintenance_id=OuterRef("pk")).order_by("-number")
    records = Maintenance.objects.annotate(
        current_state=Subquery(latest.values("state")[:1]),
        current_number=Subquery(latest.values("number")[:1]),
        current_responsible=Subquery(latest.values("responsible__username")[:1]),
        responsible_first_name=Subquery(latest.values("responsible__first_name")[:1]),
        responsible_last_name=Subquery(latest.values("responsible__last_name")[:1]),
    )
    if query:
        records = records.filter(
            Q(name__icontains=query)
            | Q(targets__device__code__icontains=query)
            | Q(targets__device__name__icontains=query)
        ).distinct()
    if kind in ("unique", "recurring"):
        records = records.filter(is_recurring=kind == "recurring")
    if active in ("true", "false"):
        records = records.filter(is_active=active == "true")
    if state in MaintenanceRun.State.values:
        records = records.filter(current_state=state)
    page = Paginator(records, 20).get_page(request.GET.get("page"))
    schedules = list_schedules(page)
    for item in page:
        item.current_state_label = (
            MaintenanceRun.State(item.current_state).label
            if item.current_state
            else "Sin ejecución"
        )
        item.responsible_name = (
            " ".join(
                part for part in (item.responsible_first_name, item.responsible_last_name) if part
            ).strip()
            or item.current_responsible
        )
        item.work_is_open = item.current_state in OPEN_STATES
        item.schedule = schedules[item.pk]
    template = (
        "maintenance/_list.html"
        if request.htmx and not request.htmx.history_restore_request
        else "maintenance/list.html"
    )
    return render(
        request,
        template,
        {
            "page_obj": page,
            "q": query,
            "kind": kind,
            "active": active,
            "state": state,
            "states": MaintenanceRun.State.choices,
        },
    )


@login_required
@permission_required("maintenance.view_maintenance", raise_exception=True)
@require_safe
def maintenance_detail(request, pk, run_id=None):
    maintenance = get_object_or_404(Maintenance, pk=pk)
    runs = maintenance.runs.select_related("responsible", "closed_by")
    run = get_object_or_404(runs, pk=run_id) if run_id is not None else runs.first()
    participants = (
        MaintenanceRunDevice.objects.filter(run=run)
        .select_related("target__device", "target__device__location", "finalized_by")
        .prefetch_related("tasks")
        .annotate(
            task_count=Count("tasks"), done_count=Count("tasks", filter=Q(tasks__completed=True))
        )
        .order_by("due_date", "pk")
    )
    return render(
        request,
        "maintenance/detail.html",
        {
            "maintenance": maintenance,
            "run": run,
            "display_name": run.configuration.get("name", maintenance.name)
            if run_id
            else maintenance.name,
            "display_description": run.configuration.get("description", "")
            if run_id
            else maintenance.description,
            "historical": run_id is not None,
            "can_create_next": maintenance.is_recurring
            and maintenance.is_active
            and run is not None
            and not maintenance.runs.filter(
                state__in=[
                    MaintenanceRun.State.PENDING,
                    MaintenanceRun.State.ASSIGNED,
                    MaintenanceRun.State.RUNNING,
                ]
            ).exists()
            and request.user.has_perm("maintenance.create_next_run"),
            "can_take": run is not None
            and run.state == MaintenanceRun.State.PENDING
            and request.user.has_perm("maintenance.take_maintenance"),
            "can_control": run is not None and can_control(request.user, run),
            "participants": Paginator(participants, 20).get_page(request.GET.get("page")),
            "group_tasks": run.tasks.filter(participant__isnull=True) if run else [],
            "templates": maintenance.task_templates.filter(is_active=True).select_related(
                "category"
            ),
            "targets": maintenance.targets.filter(is_active=True).select_related("device"),
        },
    )


@login_required
@permission_required("maintenance.view_maintenance", raise_exception=True)
@require_safe
def maintenance_history(request, pk):
    maintenance = get_object_or_404(Maintenance, pk=pk)
    selected_run = None
    events = maintenance.events.select_related("actor")
    run_id = request.GET.get("run", "")
    if run_id:
        if not run_id.isdecimal() or len(run_id) > 19:
            raise Http404
        selected_run = get_object_or_404(maintenance.runs, pk=run_id)
        events = events.filter(run=selected_run)
    return render(
        request,
        "maintenance/history.html",
        {
            "maintenance": maintenance,
            "events": Paginator(events, 20).get_page(request.GET.get("page")),
            "selected_run": selected_run,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def maintenance_edit(request, pk=None):
    permission = "maintenance.change_maintenance" if pk else "maintenance.add_maintenance"
    if not request.user.has_perm(permission):
        raise PermissionDenied
    maintenance = get_object_or_404(Maintenance, pk=pk) if pk else None
    kind = request.GET.get("kind", "unique")
    if kind not in ("unique", "recurring"):
        kind = "unique"
    initial = (
        [
            {
                "name": task["name"],
                "scope": task["scope"],
                "required": task["required"],
                "category": task["category_id"],
            }
            for task in template_data(maintenance)
        ]
        if maintenance
        else []
    )
    data = request.POST.copy() if request.method == "POST" else None
    adding = data is not None and data.get("action") == "add_task"
    picking = data is not None and (data.get("action") == "add_device" or "remove_device" in data)
    picker_error = None
    if picking:
        selected = data.getlist("devices")
        if "remove_device" in data:
            data.setlist("devices", [value for value in selected if value != data["remove_device"]])
        else:
            try:
                device = resolve_scan(actor=request.user, value=data.get("device_query", "")[:2049])
                if (
                    not eligible_devices(maintenance, actor=request.user)
                    .filter(pk=device.pk)
                    .exists()
                ):
                    raise ValidationError("Equipo no disponible para este mantenimiento.")
                if str(device.pk) not in selected:
                    if len(selected) >= MAX_TARGETS:
                        raise ValidationError(f"Seleccione como máximo {MAX_TARGETS} equipos.")
                    data.setlist("devices", [str(device.pk), *selected])
            except ValidationError as error:
                picker_error = error
    if adding:
        try:
            count = int(data.get("tasks-TOTAL_FORMS", "0"))
        except ValueError:
            count = 0
        if 0 < count < MAX_TASKS:
            data["tasks-TOTAL_FORMS"] = str(count + 1)
            data[f"tasks-{count}-scope"] = "DISPOSITIVO"
            data[f"tasks-{count}-required"] = "on"
    form = MaintenanceForm(data, maintenance=maintenance, kind=kind, actor=request.user)
    if picker_error:
        form.add_error("devices", picker_error)
    formset = TaskFormSet(data, initial=initial, prefix="tasks")
    if request.method == "POST" and not adding and not picking:
        form_valid, tasks_valid = form.is_valid(), formset.is_valid()
        if form_valid and tasks_valid:
            tasks = [
                {
                    "name": task.cleaned_data["name"],
                    "scope": task.cleaned_data["scope"],
                    "required": task.cleaned_data["required"],
                    "category_id": task.cleaned_data["category"].pk
                    if task.cleaned_data["category"]
                    else None,
                }
                for task in formset.ordered_forms
            ]
            try:
                saved = save_maintenance(
                    actor=request.user,
                    data=form.service_data(),
                    device_ids=[device.pk for device in form.cleaned_data["devices"]],
                    tasks=tasks,
                    creation_key=form.cleaned_data.get("creation_key"),
                    maintenance_id=pk,
                    expected_version=form.cleaned_data.get("version"),
                    reason=form.cleaned_data.get("reason", ""),
                )
            except ValidationError as error:
                add_validation_errors(form, error)
            else:
                messages.success(
                    request,
                    "Configuración guardada. La ejecución conserva sus equipos y tareas originales."
                    if pk
                    else "Mantenimiento creado con su primera ejecución pendiente de atención.",
                )
                return redirect("maintenance:detail", pk=saved.pk)
    return render(
        request,
        "maintenance/form.html",
        {
            "form": form,
            "formset": formset,
            "maintenance": maintenance,
            "kind": form.initial["kind"],
            "picker_url": reverse("maintenance:device_picker_edit", args=[pk])
            if pk
            else reverse("maintenance:device_picker"),
            "picker_locations": Location.objects.order_by("name", "pk"),
        },
    )
