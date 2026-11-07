from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.core.forms import add_validation_errors

from . import execution
from .execution_forms import ActionForm, CompletionForm, ProgressForm
from .models import MaintenanceRun

ACTIONS = {
    "tomar": ("Tomar mantenimiento", execution.take_maintenance),
    "iniciar": ("Iniciar mantenimiento", execution.start_maintenance),
    "liberar": ("Liberar mantenimiento", execution.release_maintenance),
    "cerrar": ("Cerrar mantenimiento", execution.close_maintenance),
    "cancelar": ("Cancelar mantenimiento", execution.cancel_maintenance),
    "completar": ("Completar equipo", execution.complete_device),
    "omitir": ("Omitir de esta ejecución", execution.omit_device),
    "avances": ("Registrar avance", execution.save_progress),
}


@login_required
@permission_required("maintenance.view_maintenance", raise_exception=True)
@require_http_methods(["GET", "POST"])
def run_action(request, run_id, action, participant_id=None):
    if action not in ACTIONS or (participant_id is None and action in ("completar", "omitir")):
        raise Http404
    run = get_object_or_404(
        MaintenanceRun.objects.select_related("maintenance", "responsible"), pk=run_id
    )
    participant = (
        get_object_or_404(run.participants.select_related("target__device"), pk=participant_id)
        if participant_id is not None
        else None
    )
    if action == "tomar":
        if not request.user.has_perm("maintenance.take_maintenance"):
            raise PermissionDenied
    elif not execution.can_control(request.user, run):
        raise PermissionDenied("Esta operación corresponde al técnico responsable.")
    title, service = ACTIONS[action]
    if action == "iniciar" and run.started_at:
        title = "Reanudar mantenimiento"
    data = request.POST if request.method == "POST" else None
    kwargs = {"run": run, "actor": request.user, "action": action}
    tasks = None
    if action == "avances":
        tasks = list(run.tasks.filter(participant=participant))
        form = ProgressForm(data, tasks=tasks, notes=(participant or run).notes, **kwargs)
    else:
        form = (CompletionForm if action == "completar" else ActionForm)(data, **kwargs)
    if request.method == "POST" and form.is_valid():
        values = {
            "actor": request.user,
            "run_id": run.pk,
            "expected_version": form.cleaned_data["version"],
        }
        if action != "tomar":
            values["reason"] = form.cleaned_data.get("reason", "")
        if participant:
            values["participant_id"] = participant.pk
        if action == "completar":
            values.update(
                {
                    key: form.cleaned_data[key]
                    for key in ("device_executed_on", "verified", "completion_summary")
                }
            )
        elif action == "avances":
            values.update(tasks=form.task_data(), notes=form.cleaned_data["notes"])
        try:
            service(**values)
        except ValidationError as error:
            add_validation_errors(form, error)
        else:
            messages.success(
                request, "Operación registrada. El historial y los avances se conservaron."
            )
            return redirect("maintenance:detail", pk=run.maintenance_id)
    return render(
        request,
        "maintenance/action.html",
        {
            "run": run,
            "maintenance": run.maintenance,
            "participant": participant,
            "form": form,
            "title": title,
            "action": action,
            "progress": tasks is not None,
        },
    )
