from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.core.permissions import require_permission

from .models import Location, LocationEvent

FIELDS = ("name", "code", "kind", "description", "is_active")


@transaction.atomic
def save_location(*, actor, data, location_id=None, expected_version=None):
    actor = require_permission(
        actor, "locations.change_location" if location_id else "locations.add_location"
    )
    location = (
        Location.objects.select_for_update().get(pk=location_id) if location_id else Location()
    )
    if location_id and expected_version != location.version:
        raise ValidationError("Otra persona modificó esta ubicación. Recargue antes de guardar.")
    before = {field: getattr(location, field) for field in FIELDS} if location_id else {}
    for field in FIELDS:
        if field in data:
            setattr(location, field, data[field])
    location.clean()
    location.full_clean()
    changes = {
        field: {"antes": before.get(field), "después": getattr(location, field)}
        for field in FIELDS
        if before.get(field) != getattr(location, field)
    }
    if location_id and not changes:
        return location
    if location_id:
        location.version += 1
    try:
        with transaction.atomic():
            location.save()
    except IntegrityError as exc:
        raise ValidationError("Ya existe una ubicación con ese nombre o código.") from exc
    action = "Actualización" if location_id else "Creación"
    if location_id and "is_active" in changes:
        action = "Reactivación" if location.is_active else "Desactivación"
    LocationEvent.objects.create(actor=actor, location=location, action=action, changes=changes)
    return location
