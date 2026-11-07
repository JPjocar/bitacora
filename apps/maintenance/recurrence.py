from django.core.exceptions import ValidationError
from django.db import transaction

from apps.assets.models import Category, Device
from apps.core.permissions import require_permission

from .models import Maintenance, MaintenanceEvent
from .selectors import OPEN_STATES, target_schedule
from .services import MAX_TARGETS, _validate_tasks, create_run_snapshot, template_data


@transaction.atomic
def create_next_run(
    *, actor, maintenance_id, expected_version, previous_run_id, target_ids, reason=""
):
    actor = require_permission(actor, "maintenance.create_next_run")
    maintenance = Maintenance.objects.select_for_update().get(pk=maintenance_id)
    if type(expected_version) is not int or maintenance.version != expected_version:
        raise ValidationError("La configuración cambió. Recargue y revise las fechas y tareas.")
    if not maintenance.is_recurring or not maintenance.is_active:
        raise ValidationError("Solo un mantenimiento periódico activo admite otra ejecución.")
    previous = maintenance.runs.select_for_update().first()
    if not previous or type(previous_run_id) is not int or previous.pk != previous_run_id:
        raise ValidationError(
            "Ya se creó otra ejecución o cambió el historial. Recargue antes de continuar."
        )
    if maintenance.runs.filter(state__in=OPEN_STATES).exists():
        raise ValidationError("Cierre la ejecución abierta antes de crear la siguiente.")
    if not isinstance(target_ids, (list, tuple)) or not 1 <= len(target_ids) <= MAX_TARGETS:
        raise ValidationError(f"Seleccione entre 1 y {MAX_TARGETS} equipos inscritos.")
    if any(type(pk) is not int or pk <= 0 for pk in target_ids) or len(set(target_ids)) != len(
        target_ids
    ):
        raise ValidationError("La selección de equipos no es válida o contiene duplicados.")
    targets = list(
        maintenance.targets.filter(pk__in=target_ids, is_active=True).order_by("device_id")
    )
    if len(targets) != len(target_ids):
        raise ValidationError("Algún equipo no pertenece a las inscripciones vigentes.")
    devices = {
        device.pk: device
        for device in Device.objects.select_for_update()
        .filter(pk__in=[target.device_id for target in targets])
        .order_by("pk")
    }
    categories = {
        category.pk: category
        for category in Category.objects.select_for_update(no_key=True)
        .filter(pk__in={device.category_id for device in devices.values()})
        .order_by("pk")
    }
    for target in targets:
        target.device = devices[target.device_id]
        if not target.device.is_active or target.device.status == Device.Status.WITHDRAWN:
            raise ValidationError(
                f"{target.device.code} está inactivo o retirado y no se puede incluir."
            )
    tasks = [
        task
        for task in template_data(maintenance)
        if task["category_id"] is None or task["category_id"] in categories
    ]
    _validate_tasks(tasks, list(devices.values()))
    schedules = {row.target.pk: row for row in target_schedule(maintenance)}
    if not isinstance(reason, str) or len(reason.strip()) > 300:
        raise ValidationError({"reason": "El motivo admite hasta 300 caracteres."})
    reason = reason.strip()
    if any(not schedules[target.pk].proposed for target in targets) and not reason:
        raise ValidationError(
            {"reason": "Justifique la inclusión anticipada de equipos no vencidos ni próximos."}
        )
    run = create_run_snapshot(
        maintenance=maintenance,
        number=previous.number + 1,
        targets=targets,
        due_dates={target.pk: schedules[target.pk].due_date for target in targets},
        categories=categories,
    )
    MaintenanceEvent.objects.create(
        maintenance=maintenance,
        run=run,
        actor=actor,
        action="RUN_CREATED",
        changes={
            "run_number": {"antes": previous.number, "después": run.number},
            "devices": {"antes": None, "después": [target.device.code for target in targets]},
            "due_dates": {
                "antes": None,
                "después": {
                    target.device.code: schedules[target.pk].due_date.isoformat()
                    for target in targets
                },
            },
            "reason": {"antes": None, "después": reason},
        },
    )
    return run
