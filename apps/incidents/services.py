"""The incident owns corrective work. No preventive state or physical status is inferred."""

import hashlib
import json
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.assets.models import Device
from apps.assets.selectors import visible_devices
from apps.core.permissions import require_permission

from .models import Incident, IncidentEvent


def _text(value, field, limit, *, required=True):
    if not isinstance(value, str) or len(value.strip()) > limit or (required and not value.strip()):
        raise ValidationError({field: f"Indique un texto válido de hasta {limit} caracteres."})
    return value.strip()


def _replayed(key, signature, actor):
    existing = Incident.objects.filter(creation_key=key).first()
    if existing:
        if existing.reporter_id != actor.pk:
            raise PermissionDenied
        if existing.creation_signature != signature:
            raise ValidationError(
                "El formulario ya registró otro reporte. Abra uno nuevo si corresponde."
            )
    return existing


@transaction.atomic
def report_incident(*, actor, device_id, symptoms, creation_key):
    actor = require_permission(actor, "incidents.add_incident")
    symptoms = _text(symptoms, "symptoms", 3000)
    if type(device_id) is not int or device_id < 1:
        raise ValidationError("Seleccione un equipo existente.")
    try:
        key = UUID(str(creation_key))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValidationError("El formulario no es válido. Abra de nuevo el reporte.") from exc
    signature = hashlib.sha256(
        json.dumps([actor.pk, device_id, symptoms], ensure_ascii=False).encode()
    ).hexdigest()
    if existing := _replayed(key, signature, actor):
        return existing
    try:
        device = visible_devices(actor).select_for_update(of=("self",)).get(pk=device_id)
    except Device.DoesNotExist as exc:
        raise ValidationError("Equipo no disponible para registrar una incidencia.") from exc
    if not device.is_active or device.status == Device.Status.WITHDRAWN:
        raise ValidationError("No se registran nuevos reportes en equipos archivados o retirados.")
    incident = Incident(
        device=device,
        reporter=actor,
        symptoms=symptoms,
        creation_key=key,
        creation_signature=signature,
    )
    incident.full_clean(validate_unique=False)
    try:
        with transaction.atomic():
            incident.save()
    except IntegrityError:
        if existing := _replayed(key, signature, actor):
            return existing
        raise
    _event(incident, actor, "INC_CREATED", {"symptoms": {"antes": None, "después": symptoms}})
    return incident


def _locked(incident_id, expected_version):
    incident = Incident.objects.select_for_update().get(pk=incident_id)
    if type(expected_version) is not int or incident.version != expected_version:
        raise ValidationError("La incidencia cambió. Recargue antes de confirmar la operación.")
    if incident.state == Incident.State.CLOSED:
        raise ValidationError("La incidencia está cerrada. Su resultado e historial se conservan.")
    return incident


def _control(actor, incident, reason):
    reason = _text(reason, "reason", 300, required=False)
    if actor.has_perm("incidents.attend_incident") and incident.responsible_id == actor.pk:
        return reason
    if not actor.has_perm("incidents.override_incident"):
        raise PermissionDenied("Esta operación corresponde al técnico responsable.")
    if not reason:
        raise ValidationError({"reason": "Justifique la intervención administrativa."})
    return reason


def _event(incident, actor, action, changes):
    changes["incident_version"] = {
        "antes": None if action == "INC_CREATED" else incident.version - 1,
        "después": incident.version,
    }
    event = IncidentEvent.objects.create(
        incident=incident, actor=actor, action=action, changes=changes
    )
    from apps.notifications.services import handle_incident_event

    handle_incident_event(event)
    return incident


def _save(incident, **values):
    for name, value in values.items():
        setattr(incident, name, value)
    incident.version += 1
    incident.full_clean(validate_unique=False)
    incident.save(update_fields=[*values, "version"])


@transaction.atomic
def take_incident(*, actor, incident_id, expected_version):
    actor = require_permission(actor, "incidents.take_incident")
    require_permission(actor, "incidents.view_incident")
    incident = _locked(incident_id, expected_version)
    if incident.state != Incident.State.PENDING:
        raise ValidationError("Otra persona ya tomó esta incidencia.")
    _save(incident, responsible=actor, state=Incident.State.ATTENDING)
    return _event(
        incident,
        actor,
        "INC_TAKEN",
        {
            "responsible_id": {"antes": None, "después": actor.pk},
            "state": {"antes": Incident.State.PENDING, "después": incident.state},
        },
    )


@transaction.atomic
def add_note(*, actor, incident_id, expected_version, note, reason=""):
    actor = require_permission(actor, "incidents.view_incident")
    incident = _locked(incident_id, expected_version)
    reason = _control(actor, incident, reason)
    if incident.state != Incident.State.ATTENDING:
        raise ValidationError("Tome la incidencia antes de registrar trabajo correctivo.")
    note = _text(note, "note", 3000)
    _save(incident)
    return _event(
        incident,
        actor,
        "INC_NOTE",
        {
            "note": {"antes": None, "después": note},
            "reason": {"antes": None, "después": reason},
        },
    )


@transaction.atomic
def release_incident(*, actor, incident_id, expected_version, reason, summary):
    actor = require_permission(actor, "incidents.view_incident")
    incident = _locked(incident_id, expected_version)
    reason = _control(actor, incident, reason)
    reason = _text(reason, "reason", 300)
    summary = _text(summary, "summary", 1000)
    if incident.state != Incident.State.ATTENDING:
        raise ValidationError("Solo se libera una incidencia que está en atención.")
    previous = incident.responsible_id
    _save(incident, state=Incident.State.PENDING, responsible=None)
    return _event(
        incident,
        actor,
        "INC_RELEASED",
        {
            "state": {"antes": Incident.State.ATTENDING, "después": incident.state},
            "responsible_id": {"antes": previous, "después": None},
            "reason": {"antes": None, "después": reason},
            "summary": {"antes": None, "después": summary},
        },
    )


@transaction.atomic
def close_incident(*, actor, incident_id, expected_version, outcome, summary, reason=""):
    actor = require_permission(actor, "incidents.view_incident")
    incident = _locked(incident_id, expected_version)
    reason = _control(actor, incident, reason)
    summary = _text(summary, "summary", 3000)
    if outcome not in Incident.Outcome.values:
        raise ValidationError({"outcome": "Seleccione un resultado de cierre válido."})
    if incident.state == Incident.State.PENDING and outcome != Incident.Outcome.INVALID:
        raise ValidationError(
            "La incidencia debe estar en atención; "
            "solo puede descartar un reporte inválido pendiente."
        )
    if outcome == Incident.Outcome.UNREPAIRABLE:
        require_permission(actor, "incidents.close_unrepairable_incident")
        reason = _text(reason, "reason", 300)
    previous = incident.state
    _save(
        incident,
        state=Incident.State.CLOSED,
        outcome=outcome,
        closure_summary=summary,
        closed_at=timezone.now(),
        closed_by=actor,
    )
    return _event(
        incident,
        actor,
        "INC_CLOSED",
        {
            "state": {"antes": previous, "después": incident.state},
            "outcome": {"antes": None, "después": outcome},
            "summary": {"antes": None, "después": summary},
            "reason": {"antes": None, "después": reason},
        },
    )
