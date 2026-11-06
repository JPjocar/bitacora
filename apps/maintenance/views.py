from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_safe
from django.views.decorators.vary import vary_on_headers

from apps.core.forms import add_validation_errors

from .forms import MaintenanceForm, TaskFormSet
from .models import Maintenance, MaintenanceRunDevice
from .services import MAX_TASKS, save_maintenance, template_data


@login_required
@permission_required("maintenance.view_maintenance", raise_exception=True)
@require_safe
@vary_on_headers("HX-Request")
def maintenance_list(request):
    query = request.GET.get("q", "").strip()[:120]
    kind = request.GET.get("kind", "")
    active = request.GET.get("active", "")
    records = Maintenance.objects.all()
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
    template = (
        "maintenance/_list.html"
        if request.htmx and not request.htmx.history_restore_request
        else "maintenance/list.html"
    )
    return render(
        request,
        template,
        {
            "page_obj": Paginator(records, 20).get_page(request.GET.get("page")),
            "q": query,
            "kind": kind,
            "active": active,
        },
    )


@login_required
@permission_required("maintenance.view_maintenance", raise_exception=True)
@require_safe
def maintenance_detail(request, pk):
    maintenance = get_object_or_404(Maintenance, pk=pk)
    run = maintenance.runs.first()
    participants = (
        MaintenanceRunDevice.objects.filter(run=run)
        .select_related("target__device", "target__device__location")
        .prefetch_related("tasks")
    )
    return render(
        request,
        "maintenance/detail.html",
        {
            "maintenance": maintenance,
            "run": run,
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
    return render(
        request,
        "maintenance/history.html",
        {
            "maintenance": maintenance,
            "events": Paginator(maintenance.events.select_related("actor"), 20).get_page(
                request.GET.get("page")
            ),
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
    if adding:
        try:
            count = int(data.get("tasks-TOTAL_FORMS", "0"))
        except ValueError:
            count = 0
        if 0 < count < MAX_TASKS:
            data["tasks-TOTAL_FORMS"] = str(count + 1)
            data[f"tasks-{count}-scope"] = "DISPOSITIVO"
            data[f"tasks-{count}-required"] = "on"
    form = MaintenanceForm(data, maintenance=maintenance, kind=kind)
    formset = TaskFormSet(data, initial=initial, prefix="tasks")
    if request.method == "POST" and not adding:
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
        },
    )
