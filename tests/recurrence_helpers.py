from datetime import date

from django.utils import timezone

from apps.maintenance.execution import (
    cancel_maintenance,
    close_maintenance,
    complete_device,
    omit_device,
)
from apps.maintenance.recurrence import create_next_run

from .execution_helpers import make_run, operate, progress, start_run


def recurring_run(test, devices=None, *, base_date=None):
    return make_run(test, devices=devices, recurring=True, base_date=base_date or date(2026, 10, 1))


def cancel_run(test, run):
    return operate(
        cancel_maintenance,
        test,
        run,
        actor=test.admin,
        reason="Prueba sintética sin trabajo completado",
    )


def finish_run(test, run, dates=None):
    start_run(test, run)
    dates = (
        dates
        if dates is not None
        else {
            item.target.device_id: timezone.localdate()
            for item in run.participants.select_related("target")
        }
    )
    for participant in run.participants.select_related("target"):
        if participant.target.device_id in dates:
            progress(test, run, participant)
            operate(
                complete_device,
                test,
                run,
                actor=test.admin,
                reason="Registro sintético autorizado",
                participant_id=participant.pk,
                device_executed_on=dates[participant.target.device_id],
                verified=True,
                completion_summary="Verificación sintética completada",
            )
        else:
            operate(
                omit_device,
                test,
                run,
                participant_id=participant.pk,
                reason="Equipo no disponible para la prueba",
            )
    if dates:
        progress(test, run)
        return operate(close_maintenance, test, run)
    return cancel_run(test, run)


def next_run(test, previous, *, target_ids=None, **kwargs):
    maintenance = previous.maintenance
    maintenance.refresh_from_db()
    return create_next_run(
        **{
            "actor": test.technician,
            "maintenance_id": maintenance.pk,
            "expected_version": maintenance.version,
            "previous_run_id": previous.pk,
            "target_ids": target_ids
            if target_ids is not None
            else list(maintenance.targets.filter(is_active=True).values_list("pk", flat=True)),
            "reason": "Selección anticipada para verificación sintética",
            **kwargs,
        }
    )
