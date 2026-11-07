import hashlib
import json
from datetime import date
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.assets.models import Category, Device
from apps.core.permissions import require_permission

from .models import (
    Maintenance,
    MaintenanceEvent,
    MaintenanceRun,
    MaintenanceRunDevice,
    MaintenanceTarget,
    MaintenanceTaskResult,
    MaintenanceTaskTemplate,
)
from .selectors import due_for_target, targets_with_last_completion

FIELDS = (
    "name",
    "description",
    "is_recurring",
    "base_date",
    "interval_value",
    "interval_unit",
    "planned_date",
    "is_active",
)
TASK_FIELDS = ("name", "scope", "category_id", "required")
MAX_TARGETS = 200
MAX_TASKS = 50


def configuration(maintenance):
    return {
        field: value.isoformat()
        if isinstance(value := getattr(maintenance, field), date)
        else value
        for field in FIELDS
    }


def template_data(maintenance):
    return list(maintenance.task_templates.filter(is_active=True).values(*TASK_FIELDS))


def _validate_tasks(tasks, devices):
    if not isinstance(tasks, list) or not 1 <= len(tasks) <= MAX_TASKS:
        raise ValidationError(f"Configure entre 1 y {MAX_TASKS} tareas.")
    categories = {device.category_id for device in devices}
    normalized, seen = [], set()
    for item in tasks:
        if not isinstance(item, dict) or set(item) - set(TASK_FIELDS):
            raise ValidationError("La configuración de tareas no es válida.")
        task = {"scope": "DISPOSITIVO", "category_id": None, "required": True, **item}
        if not isinstance(task.get("name"), str) or type(task["required"]) is not bool:
            raise ValidationError("Indique el nombre y si la tarea es obligatoria.")
        task["name"] = task["name"].strip()
        category = task["category_id"]
        if category is not None and (type(category) is not int or category not in categories):
            raise ValidationError(
                "La categoría de cada tarea debe estar representada en los equipos seleccionados."
            )
        if task["scope"] == "GRUPAL" and category is not None:
            raise ValidationError("Las tareas generales no se restringen por categoría.")
        MaintenanceTaskTemplate(**task, order=len(normalized) + 1).full_clean(
            exclude=["maintenance", "category"], validate_constraints=False
        )
        key = (task["name"].casefold(), task["scope"], category)
        if key in seen:
            raise ValidationError("Hay tareas duplicadas en el mismo ámbito y categoría.")
        seen.add(key)
        normalized.append(task)
    for device in devices:
        if not any(
            task["scope"] == "DISPOSITIVO" and task["category_id"] in (None, device.category_id)
            for task in normalized
        ):
            raise ValidationError(
                f"Configure al menos una tarea individual aplicable a {device.code}."
            )
    return normalized


def _replayed(key, signature, actor):
    existing = Maintenance.objects.filter(creation_key=key).first()
    if existing:
        if existing.creation_signature != signature or existing.created_by_id != actor.pk:
            raise ValidationError(
                "Este formulario ya se utilizó. Abra uno nuevo para crear otro mantenimiento."
            )
        return existing
    return None


@transaction.atomic
def save_maintenance(
    *,
    actor,
    data,
    device_ids,
    tasks,
    creation_key=None,
    maintenance_id=None,
    expected_version=None,
    reason="",
):
    actor = require_permission(
        actor, "maintenance.change_maintenance" if maintenance_id else "maintenance.add_maintenance"
    )
    maintenance = (
        Maintenance.objects.select_for_update().get(pk=maintenance_id)
        if maintenance_id
        else Maintenance(created_by=actor)
    )
    if maintenance_id and (
        type(expected_version) is not int or maintenance.version != expected_version
    ):
        raise ValidationError(
            "Otra persona modificó este mantenimiento. Recargue antes de guardar."
        )
    if not isinstance(data, dict) or set(data) - set(FIELDS):
        raise ValidationError("La configuración contiene campos no permitidos.")
    before = configuration(maintenance) if maintenance_id else {}
    old_tasks = template_data(maintenance) if maintenance_id else []
    old_ids = (
        set(maintenance.targets.filter(is_active=True).values_list("device_id", flat=True))
        if maintenance_id
        else set()
    )
    for field, value in data.items():
        if field in ("name", "description") and not isinstance(value, str):
            raise ValidationError("El nombre y la descripción deben ser textos válidos.")
        if field in ("is_recurring", "is_active") and type(value) is not bool:
            raise ValidationError(
                "Indique un valor válido para el tipo y estado del mantenimiento."
            )
        if field in ("base_date", "planned_date") and value is not None and type(value) is not date:
            raise ValidationError("Indique fechas civiles válidas.")
        if field == "interval_value" and value is not None and type(value) is not int:
            raise ValidationError("El intervalo debe ser un entero positivo.")
        setattr(maintenance, field, value)
    if maintenance_id and maintenance.is_recurring != before["is_recurring"]:
        raise ValidationError("No se puede cambiar entre único y periódico después de crearlo.")
    if (
        maintenance_id
        and not maintenance.is_recurring
        and str(maintenance.planned_date) != before["planned_date"]
    ):
        raise ValidationError(
            "La fecha prevista del mantenimiento único se conserva; no se admite reprogramación."
        )
    maintenance.full_clean(exclude=["creation_key", "creation_signature"], validate_unique=False)
    if not isinstance(device_ids, (list, tuple)) or not 1 <= len(device_ids) <= MAX_TARGETS:
        raise ValidationError(f"Seleccione entre 1 y {MAX_TARGETS} equipos.")
    if any(type(pk) is not int or pk <= 0 for pk in device_ids) or len(set(device_ids)) != len(
        device_ids
    ):
        raise ValidationError("La selección contiene equipos inválidos o repetidos.")
    # Same order as asset editing: device first, then category. Do not lock joined rows.
    devices = list(Device.objects.select_for_update().filter(pk__in=device_ids).order_by("pk"))
    if len(devices) != len(device_ids):
        raise ValidationError("Algún equipo seleccionado ya no está disponible.")
    categories = {
        category.pk: category
        for category in Category.objects.select_for_update(no_key=True)
        .filter(pk__in={device.category_id for device in devices})
        .order_by("pk")
    }
    tasks = _validate_tasks(tasks, devices)
    if maintenance_id:
        for target in targets_with_last_completion(maintenance, active_only=False).filter(
            device_id__in=device_ids
        ):
            due_for_target(maintenance, target.last_completed_on)
    after = configuration(maintenance)
    signature = hashlib.sha256(
        json.dumps(
            {"configuration": after, "devices": sorted(device_ids), "tasks": tasks},
            sort_keys=True,
            ensure_ascii=False,
        ).encode()
    ).hexdigest()
    if not maintenance_id:
        try:
            maintenance.creation_key = UUID(str(creation_key))
        except (ValueError, AttributeError, TypeError) as error:
            raise ValidationError(
                "El formulario de creación no es válido. Abra uno nuevo."
            ) from error
        if existing := _replayed(maintenance.creation_key, signature, actor):
            return existing
        maintenance.creation_signature = signature
    for device in devices:
        if device.pk not in old_ids and (
            not device.is_active or device.status == Device.Status.WITHDRAWN
        ):
            raise ValidationError(
                f"No se puede inscribir {device.code}: está inactivo o retirado "
                "del control operativo."
            )
    changes = {
        field: {"antes": before.get(field), "después": value}
        for field, value in after.items()
        if before.get(field) != value
    }
    if old_ids != set(device_ids):
        changes["devices"] = {"antes": sorted(old_ids), "después": sorted(device_ids)}
    if old_tasks != tasks:
        changes["tasks"] = {"antes": old_tasks, "después": tasks}
    if maintenance_id and not changes:
        return maintenance
    if maintenance_id:
        if not isinstance(reason, str) or not reason.strip() or len(reason.strip()) > 300:
            raise ValidationError({"reason": "Explique el cambio en un máximo de 300 caracteres."})
        changes["reason"] = {"antes": None, "después": reason.strip()}
        maintenance.version += 1
    try:
        with transaction.atomic():
            maintenance.save()
    except IntegrityError:
        if not maintenance_id and (
            existing := _replayed(maintenance.creation_key, signature, actor)
        ):
            return existing
        raise
    maintenance.targets.exclude(device_id__in=device_ids).update(is_active=False)
    for device in devices:
        target, _ = MaintenanceTarget.objects.get_or_create(maintenance=maintenance, device=device)
        if not target.is_active:
            target.is_active = True
            target.save(update_fields=["is_active"])
    if old_tasks != tasks:
        maintenance.task_templates.filter(is_active=True).update(is_active=False)
        for order, task in enumerate(tasks, start=1):
            MaintenanceTaskTemplate.objects.create(maintenance=maintenance, order=order, **task)
    run = None
    if not maintenance_id:
        targets = list(maintenance.targets.select_related("device").order_by("device_id"))
        run = create_run_snapshot(
            maintenance=maintenance,
            number=1,
            targets=targets,
            due_dates={target.pk: maintenance.initial_due_date for target in targets},
            categories=categories,
        )
    event = MaintenanceEvent.objects.create(
        maintenance=maintenance,
        run=run,
        actor=actor,
        action="Creación" if not maintenance_id else "Configuración actualizada",
        changes=changes,
    )
    from apps.notifications.services import handle_maintenance_event

    handle_maintenance_event(event)
    return maintenance


def create_run_snapshot(*, maintenance, number, targets, due_dates, categories):
    """Caller validates and holds the maintenance/device/category locks."""
    run = MaintenanceRun.objects.create(
        maintenance=maintenance,
        number=number,
        configuration={**configuration(maintenance), "version": maintenance.version},
    )
    templates = list(maintenance.task_templates.filter(is_active=True))
    task_copies = []
    for target in targets:
        device = target.device
        participant = MaintenanceRunDevice.objects.create(
            run=run,
            target=target,
            device_name=device.name,
            category_id=device.category_id,
            category_name=categories[device.category_id].name,
            due_date=due_dates[target.pk],
        )
        for template in templates:
            if template.scope == "DISPOSITIVO" and template.category_id in (
                None,
                device.category_id,
            ):
                task_copies.append(_copy_task(run, template, participant))
    for template in templates:
        if template.scope == "GRUPAL":
            task_copies.append(_copy_task(run, template))
    MaintenanceTaskResult.objects.bulk_create(task_copies, batch_size=500)
    return run


def _copy_task(run, template, participant=None):
    return MaintenanceTaskResult(
        run=run,
        participant=participant,
        template=template,
        name=template.name,
        order=template.order,
        required=template.required,
        scope=template.scope,
    )
