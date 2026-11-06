from datetime import date, datetime

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction

from apps.core.permissions import require_permission
from apps.locations.models import Location

from .models import Category, CategoryEvent, Device, DeviceEvent, Movement, generate_device_code
from .selectors import movement_warning

CATEGORY_FIELDS = ("name", "kind", "description", "is_active")
DEVICE_FIELDS = (
    "name",
    "category_id",
    "brand",
    "model",
    "serial_number",
    "status",
    "observations",
    "technical_details",
    "acquired_on",
    "commissioned_on",
    "is_active",
)
OPERATION_FIELDS = {"status", "observations"}


def _snapshot(instance, fields):
    data = {}
    for field in fields:
        value = getattr(instance, field)
        data[field] = value.isoformat() if isinstance(value, date | datetime) else value
    return data


def _changes(before, after):
    return {
        field: {"antes": before.get(field), "después": value}
        for field, value in after.items()
        if before.get(field) != value
    }


def _check_version(instance, expected_version):
    if instance.version != expected_version:
        raise ValidationError(
            "El registro cambió desde que abrió el formulario. "
            "Recargue y revise los datos actuales."
        )


@transaction.atomic
def save_category(*, actor, data, category_id=None, expected_version=None):
    actor = require_permission(
        actor, "assets.change_category" if category_id else "assets.add_category"
    )
    category = (
        Category.objects.select_for_update().get(pk=category_id) if category_id else Category()
    )
    if category_id:
        _check_version(category, expected_version)
    before = _snapshot(category, CATEGORY_FIELDS) if category_id else {}
    for field in CATEGORY_FIELDS:
        if field in data:
            setattr(category, field, data[field])
    category.clean()
    category.full_clean()
    changes = _changes(before, _snapshot(category, CATEGORY_FIELDS))
    if category_id and not changes:
        return category
    if category_id:
        category.version += 1
    try:
        with transaction.atomic():
            category.save()
    except IntegrityError as exc:
        raise ValidationError("Ya existe una categoría con ese nombre.") from exc
    CategoryEvent.objects.create(
        actor=actor,
        category=category,
        action="Actualización" if category_id else "Creación",
        changes=changes,
    )
    return category


@transaction.atomic
def save_device(*, actor, data, device_id=None, expected_version=None, reason=""):
    if device_id:
        actor = require_permission(actor, "assets.view_device")
        if not actor.has_perm("assets.change_device"):
            require_permission(actor, "assets.update_device_operation")
            if set(data) - OPERATION_FIELDS:
                raise PermissionDenied("Solo puede actualizar el estado y las observaciones.")
    else:
        actor = require_permission(actor, "assets.add_device")
    device = (
        Device.objects.select_for_update().get(pk=device_id)
        if device_id
        else Device(created_by=actor)
    )
    if device_id:
        _check_version(device, expected_version)
        if "location_id" in data and data["location_id"] != device.location_id:
            raise ValidationError("Utilice Registrar traslado para cambiar la ubicación.")
    before = _snapshot(device, DEVICE_FIELDS) if device_id else {}
    for field in DEVICE_FIELDS:
        if field in data:
            setattr(device, field, data[field])
    if not isinstance(device.is_active, bool):
        raise ValidationError({"is_active": "Indique un estado activo válido."})
    if not device_id:
        device.location_id = data.get("location_id")
    # Lock catalog entries so concurrent deactivation is serialized with assignment.
    try:
        category = Category.objects.select_for_update(no_key=True).get(pk=device.category_id)
    except (Category.DoesNotExist, ValueError, TypeError) as exc:
        raise ValidationError({"category": "Seleccione una categoría existente."}) from exc
    if not category.is_active and (not device_id or before["category_id"] != category.pk):
        raise ValidationError({"category": "La categoría seleccionada está inactiva."})
    if not device_id:
        try:
            location = Location.objects.select_for_update(no_key=True).get(pk=device.location_id)
        except (Location.DoesNotExist, ValueError, TypeError) as exc:
            raise ValidationError({"location": "Seleccione una ubicación existente."}) from exc
        if not location.is_active:
            raise ValidationError(
                {"location": "No puede registrar equipos en una ubicación inactiva."}
            )
    reason = reason.strip()
    if device_id and before["status"] != device.status and not reason:
        raise ValidationError({"reason": "Explique brevemente el cambio de estado."})
    if len(reason) > 300:
        raise ValidationError({"reason": "El motivo admite hasta 300 caracteres."})
    device.clean()
    device.full_clean(exclude=["code"])
    changes = _changes(before, _snapshot(device, DEVICE_FIELDS))
    if device_id and not changes:
        return device
    if device_id:
        device.version += 1
        device.save()
    else:
        for _ in range(8):
            device.code = generate_device_code()
            try:
                with transaction.atomic():
                    device.save(force_insert=True)
                break
            except IntegrityError:
                if not Device.objects.filter(code=device.code).exists():
                    raise
        else:
            raise ValidationError("No se pudo generar un código único. Intente nuevamente.")
        changes["location_id"] = {"antes": None, "después": device.location_id}
    if reason:
        changes["reason"] = {"antes": None, "después": reason}
    DeviceEvent.objects.create(
        actor=actor,
        device=device,
        action="Actualización" if device_id else "Creación",
        changes=changes,
    )
    return device


@transaction.atomic
def move_device(
    *,
    actor,
    device_id,
    destination_id,
    expected_version,
    reason,
    effective_at,
    notes="",
    confirm_warning=False,
):
    actor = require_permission(actor, "assets.add_movement")
    device = Device.objects.select_for_update().get(pk=device_id)
    _check_version(device, expected_version)
    try:
        # NO KEY UPDATE serializes deactivation while allowing FK checks from other
        # movements (e.g. two different devices swapping their locations).
        destination = Location.objects.select_for_update(no_key=True).get(pk=destination_id)
    except (Location.DoesNotExist, ValueError, TypeError) as exc:
        raise ValidationError({"destination": "Seleccione un destino existente."}) from exc
    if destination.pk == device.location_id:
        raise ValidationError(
            {"destination": "El destino debe ser distinto de la ubicación actual."}
        )
    if not destination.is_active:
        raise ValidationError({"destination": "El destino está inactivo."})
    if movement_warning(device) and confirm_warning is not True:
        raise ValidationError(
            {"confirm_warning": "Confirme que leyó la advertencia antes de registrar el traslado."}
        )
    movement = Movement(
        device=device,
        origin_id=device.location_id,
        destination=destination,
        actor=actor,
        reason=reason,
        notes=notes,
        effective_at=effective_at,
        device_version=device.version + 1,
    )
    movement.clean()
    movement.full_clean()
    latest = device.movements.order_by("-effective_at", "-pk").first()
    if latest and movement.effective_at < latest.effective_at:
        raise ValidationError(
            {"effective_at": "La fecha no puede ser anterior al último traslado registrado."}
        )
    movement.save()
    device.location = destination
    device.version += 1
    device.save(update_fields=["location", "version", "updated_at"])
    DeviceEvent.objects.create(
        actor=actor,
        device=device,
        action="Traslado",
        changes={
            "location_id": {"antes": movement.origin_id, "después": destination.pk},
            "movement_id": {"antes": None, "después": movement.pk},
        },
    )
    return movement
