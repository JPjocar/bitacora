"""Operational services: maintenance -> run locks, version, owner and audit in one transaction."""

from datetime import date

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.core.permissions import require_permission

from .dates import add_interval
from .models import Maintenance, MaintenanceEvent, MaintenanceRun, MaintenanceRunDevice


def _text(value, *, limit=300, required=False):
    if not isinstance(value, str) or len(value.strip()) > limit or (required and not value.strip()):
        raise ValidationError(f"Indique un texto válido de hasta {limit} caracteres.")
    return value.strip()


def _locked_run(run_id, expected_version):
    parent_id = MaintenanceRun.objects.values_list("maintenance_id", flat=True).get(pk=run_id)
    maintenance = Maintenance.objects.select_for_update().get(pk=parent_id)
    run = MaintenanceRun.objects.select_for_update().get(pk=run_id)
    run.maintenance = maintenance
    if type(expected_version) is not int or run.version != expected_version:
        raise ValidationError(
            "La ejecución cambió. Recargue y revise los avances antes de guardar."
        )
    return run


def can_control(actor, run):
    return actor.has_perm("maintenance.override_maintenance") or (
        actor.has_perm("maintenance.execute_maintenance") and run.responsible_id == actor.pk
    )


def _control(actor, run, reason):
    reason = _text(reason)
    if actor.has_perm("maintenance.execute_maintenance") and run.responsible_id == actor.pk:
        return reason
    if not actor.has_perm("maintenance.override_maintenance"):
        raise PermissionDenied("Solo el técnico responsable puede realizar esta operación.")
    if not reason:
        raise ValidationError({"reason": "Explique el motivo de la intervención administrativa."})
    return reason


def _running(actor, run, reason):
    if run.state != MaintenanceRun.State.RUNNING:
        raise ValidationError(
            "Debe iniciar o reanudar el mantenimiento antes de registrar trabajo."
        )
    return _control(actor, run, reason)


def _participant(run, participant_id):
    participant = run.participants.select_for_update().get(pk=participant_id)
    if participant.result != MaintenanceRunDevice.Result.UNFINISHED:
        raise ValidationError("El equipo ya fue completado u omitido. Su resultado se conserva.")
    return participant


def _save(instance, **values):
    for key, value in values.items():
        setattr(instance, key, value)
    instance.save(update_fields=list(values))


def _record(run, actor, action, changes, reason=""):
    old_version = run.version
    _save(run, version=old_version + 1)
    changes["execution_version"] = {"antes": old_version, "después": run.version}
    if reason:
        changes["reason"] = {"antes": None, "después": reason}
    MaintenanceEvent.objects.create(
        maintenance=run.maintenance, run=run, actor=actor, action=action, changes=changes
    )
    return run


@transaction.atomic
def take_maintenance(*, actor, run_id, expected_version):
    actor = require_permission(actor, "maintenance.take_maintenance")
    run = _locked_run(run_id, expected_version)
    if run.state != MaintenanceRun.State.PENDING:
        raise ValidationError("Este mantenimiento ya fue tomado o está cerrado.")
    _save(run, state=MaintenanceRun.State.ASSIGNED, responsible=actor)
    return _record(
        run,
        actor,
        "TAKEN",
        {
            "responsible_id": {"antes": None, "después": actor.pk},
            "state": {"antes": MaintenanceRun.State.PENDING, "después": run.state},
        },
    )


@transaction.atomic
def start_maintenance(*, actor, run_id, expected_version, reason=""):
    actor = require_permission(actor, "maintenance.view_maintenance")
    run = _locked_run(run_id, expected_version)
    reason = _control(actor, run, reason)
    if run.state != MaintenanceRun.State.ASSIGNED:
        raise ValidationError("Tome el mantenimiento antes de iniciarlo o reanudarlo.")
    resumed = run.started_at is not None
    _save(run, state=MaintenanceRun.State.RUNNING, started_at=run.started_at or timezone.now())
    return _record(
        run,
        actor,
        "RESUMED" if resumed else "STARTED",
        {
            "state": {"antes": MaintenanceRun.State.ASSIGNED, "después": run.state},
            "started_at": {
                "antes": run.started_at.isoformat() if resumed else None,
                "después": run.started_at.isoformat(),
            },
        },
        reason,
    )


@transaction.atomic
def release_maintenance(*, actor, run_id, expected_version, reason):
    actor = require_permission(actor, "maintenance.view_maintenance")
    run = _locked_run(run_id, expected_version)
    reason = _text(reason, required=True)
    _control(actor, run, reason)
    if run.state not in (MaintenanceRun.State.ASSIGNED, MaintenanceRun.State.RUNNING):
        raise ValidationError("Solo se libera un mantenimiento asignado o en ejecución.")
    previous, responsible_id = run.state, run.responsible_id
    _save(run, state=MaintenanceRun.State.PENDING, responsible=None)
    return _record(
        run,
        actor,
        "RELEASED",
        {
            "state": {"antes": previous, "después": run.state},
            "responsible_id": {"antes": responsible_id, "después": None},
        },
        reason,
    )


@transaction.atomic
def save_progress(*, actor, run_id, expected_version, tasks, notes, participant_id=None, reason=""):
    actor = require_permission(actor, "maintenance.view_maintenance")
    run = _locked_run(run_id, expected_version)
    reason = _running(actor, run, reason)
    participant = _participant(run, participant_id) if participant_id is not None else None
    current = list(run.tasks.select_for_update().filter(participant=participant))
    notes = _text(notes, limit=3000)
    if (
        not isinstance(tasks, dict)
        or set(tasks) != {task.pk for task in current}
        or any(type(pk) is not int for pk in tasks)
    ):
        raise ValidationError(
            "La selección de tareas no corresponde a este equipo o mantenimiento."
        )
    changes, before, after = {}, [], []
    for task in current:
        value = tasks[task.pk]
        if (
            not isinstance(value, dict)
            or set(value) != {"completed", "observation"}
            or type(value["completed"]) is not bool
        ):
            raise ValidationError("El resultado de una tarea no es válido.")
        observation = _text(value["observation"], limit=500)
        if task.completed and not value["completed"] and not reason:
            raise ValidationError({"reason": "Explique por qué rectifica una tarea ya marcada."})
        if (task.completed, task.observation) != (value["completed"], observation):
            before.append(
                {
                    "task_id": task.pk,
                    "name": task.name,
                    "completed": task.completed,
                    "observation": task.observation,
                }
            )
            _save(
                task,
                completed=value["completed"],
                observation=observation,
                changed_by=actor,
                changed_at=timezone.now(),
            )
            after.append(
                {
                    "task_id": task.pk,
                    "name": task.name,
                    "completed": task.completed,
                    "observation": task.observation,
                }
            )
    context = participant or run
    if notes != context.notes:
        changes["notes"] = {"antes": context.notes, "después": notes}
        _save(context, notes=notes)
    if before:
        changes["tasks"] = {"antes": before, "después": after}
    if not changes:
        return run
    if participant:
        changes["participant_id"] = {"antes": None, "después": participant.pk}
    return _record(run, actor, "PROGRESS", changes, reason)


@transaction.atomic
def omit_device(*, actor, run_id, participant_id, expected_version, reason):
    actor = require_permission(actor, "maintenance.view_maintenance")
    run = _locked_run(run_id, expected_version)
    reason = _text(reason, required=True)
    _running(actor, run, reason)
    participant = _participant(run, participant_id)
    _save(
        participant,
        result=MaintenanceRunDevice.Result.OMITTED,
        finalized_at=timezone.now(),
        finalized_by=actor,
        omission_reason=reason,
    )
    return _record(
        run,
        actor,
        "DEVICE_OMITTED",
        {
            "participant_id": {"antes": None, "después": participant.pk},
            "result": {
                "antes": MaintenanceRunDevice.Result.UNFINISHED,
                "después": participant.result,
            },
        },
        reason,
    )


@transaction.atomic
def complete_device(
    *,
    actor,
    run_id,
    participant_id,
    expected_version,
    device_executed_on,
    verified,
    completion_summary,
    reason="",
):
    actor = require_permission(actor, "maintenance.view_maintenance")
    run = _locked_run(run_id, expected_version)
    reason = _running(actor, run, reason)
    participant = _participant(run, participant_id)
    if verified is not True:
        raise ValidationError({"verified": "Confirme la verificación final del equipo."})
    summary = _text(completion_summary, required=True)
    today = timezone.localdate()
    if type(device_executed_on) is not date or device_executed_on > today:
        raise ValidationError({"device_executed_on": "Indique una fecha real que no sea futura."})
    if device_executed_on < today:
        if not actor.has_perm("maintenance.backdate_maintenance"):
            raise PermissionDenied("La fecha anterior requiere autorización administrativa.")
        if not reason:
            raise ValidationError({"reason": "Justifique el registro de una fecha anterior."})
    missing = list(
        participant.tasks.filter(required=True, completed=False).values_list("name", flat=True)
    )
    if missing:
        raise ValidationError("Faltan tareas obligatorias del equipo: " + "; ".join(missing))
    maintenance = run.maintenance
    next_due = (
        add_interval(device_executed_on, maintenance.interval_value, maintenance.interval_unit)
        if maintenance.is_recurring
        else None
    )
    _save(
        participant,
        result=MaintenanceRunDevice.Result.COMPLETED,
        device_executed_on=device_executed_on,
        finalized_at=timezone.now(),
        finalized_by=actor,
        completion_summary=summary,
        next_due_date=next_due,
    )
    return _record(
        run,
        actor,
        "DEVICE_COMPLETED",
        {
            "participant_id": {"antes": None, "después": participant.pk},
            "device_executed_on": {"antes": None, "después": device_executed_on.isoformat()},
            "completion_summary": {"antes": None, "después": summary},
            "next_due_date": {"antes": None, "después": next_due.isoformat() if next_due else None},
        },
        reason,
    )


@transaction.atomic
def close_maintenance(*, actor, run_id, expected_version, reason=""):
    actor = require_permission(actor, "maintenance.view_maintenance")
    run = _locked_run(run_id, expected_version)
    reason = _running(actor, run, reason)
    participants = list(
        run.participants.select_for_update(of=("self",)).select_related("target__device")
    )
    unfinished = [
        item.target.device.code
        for item in participants
        if item.result == MaintenanceRunDevice.Result.UNFINISHED
    ]
    if unfinished:
        raise ValidationError("Quedan equipos sin finalizar: " + ", ".join(unfinished))
    if not any(item.result == MaintenanceRunDevice.Result.COMPLETED for item in participants):
        raise ValidationError(
            "No hay equipos completados. Si todos fueron omitidos, cancele con motivo."
        )
    missing = list(
        run.tasks.filter(participant__isnull=True, required=True, completed=False).values_list(
            "name", flat=True
        )
    )
    if missing:
        raise ValidationError("Faltan tareas generales obligatorias: " + "; ".join(missing))
    partial = any(item.result == MaintenanceRunDevice.Result.OMITTED for item in participants)
    _save(
        run,
        state=MaintenanceRun.State.PARTIAL if partial else MaintenanceRun.State.COMPLETED,
        completed_at=timezone.now(),
        closed_by=actor,
    )
    return _record(
        run,
        actor,
        "PARTIALLY_COMPLETED" if partial else "COMPLETED",
        {
            "state": {"antes": MaintenanceRun.State.RUNNING, "después": run.state},
            "completed_at": {"antes": None, "después": run.completed_at.isoformat()},
        },
        reason,
    )


@transaction.atomic
def cancel_maintenance(*, actor, run_id, expected_version, reason):
    actor = require_permission(actor, "maintenance.view_maintenance")
    run = _locked_run(run_id, expected_version)
    reason = _text(reason, required=True)
    _control(actor, run, reason)
    if not run.is_open:
        raise ValidationError("El mantenimiento ya está cerrado.")
    if run.participants.filter(result=MaintenanceRunDevice.Result.COMPLETED).exists():
        raise ValidationError(
            "Hay equipos completados. Conserve su trabajo y use cierre total o parcial."
        )
    previous = run.state
    _save(
        run,
        state=MaintenanceRun.State.CANCELLED,
        cancelled_at=timezone.now(),
        closed_by=actor,
        cancellation_reason=reason,
    )
    return _record(
        run,
        actor,
        "CANCELLED",
        {
            "state": {"antes": previous, "después": run.state},
            "cancelled_at": {"antes": None, "después": run.cancelled_at.isoformat()},
        },
        reason,
    )
