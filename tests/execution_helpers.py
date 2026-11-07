from django.utils import timezone

from apps.maintenance.execution import save_progress, start_maintenance, take_maintenance
from apps.maintenance.models import MaintenanceRun

from .maintenance_helpers import create_maintenance, maintenance_data, task_data


def make_run(test, *, devices=None, recurring=False, tasks=None, base_date=None):
    data = maintenance_data(planned_date=None if recurring else timezone.localdate())
    if recurring:
        data.update(
            is_recurring=True,
            base_date=base_date or timezone.localdate(),
            interval_value=2,
            interval_unit="MESES",
        )
    return create_maintenance(
        test,
        data=data,
        device_ids=[device.pk for device in (devices or [test.device])],
        tasks=tasks
        or [
            task_data(),
            task_data(name="Comprobación opcional", required=False),
            task_data(name="Preparar materiales", scope="GRUPAL"),
        ],
    ).runs.get()


def operate(service, test, run, **kwargs):
    run.refresh_from_db()
    return service(
        **{"actor": test.technician, "run_id": run.pk, "expected_version": run.version, **kwargs}
    )


def start_run(test, run):
    operate(take_maintenance, test, run)
    return operate(start_maintenance, test, run)


def progress(test, run, participant=None, *, completed=True, **kwargs):
    context = participant or run
    tasks = {
        task.pk: {"completed": completed, "observation": task.observation}
        for task in run.tasks.filter(participant=participant)
    }
    return operate(
        save_progress,
        test,
        run,
        **{
            "tasks": tasks,
            "notes": context.notes,
            "participant_id": participant.pk if participant else None,
            **kwargs,
        },
    )


def current_version(run):
    return MaintenanceRun.objects.values_list("version", flat=True).get(pk=run.pk)
