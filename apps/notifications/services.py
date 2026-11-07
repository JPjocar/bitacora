"""Explicit transactional integration; no signals, external delivery or GET writes."""

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.roles import ADMINISTRATOR, TECHNICIAN
from apps.core.permissions import require_permission
from apps.maintenance.models import Maintenance, MaintenanceRun
from apps.maintenance.selectors import outstanding_targets, schedule_row

from .models import Notification


def require_access(actor):
    actor = require_permission(actor, "notifications.view_notification")
    if not any(
        actor.has_perm(permission)
        for permission in [
            "maintenance.view_maintenance",
            "incidents.view_incident",
            "incidents.view_own_incident",
        ]
    ):
        raise PermissionDenied
    return actor


def recipients(permission="maintenance.view_maintenance"):
    users = get_user_model().objects.filter(
        is_active=True, groups__name__in=[ADMINISTRATOR, TECHNICIAN]
    )
    for app, code in [permission.split("."), ("notifications", "view_notification")]:
        users = users.filter(
            Q(is_superuser=True)
            | Q(user_permissions__content_type__app_label=app, user_permissions__codename=code)
            | Q(
                groups__permissions__content_type__app_label=app, groups__permissions__codename=code
            )
        )
    return list(users.distinct().order_by("pk"))


def accessible_notices(actor):
    actor = require_access(actor)
    sources = Q(pk__in=[])
    if actor.has_perm("maintenance.view_maintenance"):
        sources |= Q(incident_event=None)
    if actor.has_perm("incidents.view_incident"):
        sources |= Q(incident_event__isnull=False)
    elif actor.has_perm("incidents.view_own_incident"):
        sources |= Q(incident_event__incident__reporter_id=actor.pk)
    return Notification.objects.filter(sources, recipient=actor)


def handle_incident_event(event):
    """Explicit call from the incident service while its parent lock is held."""
    from apps.incidents.models import Incident

    incident = event.incident
    if event.action in {"INC_CREATED", "INC_RELEASED", "INC_TAKEN", "INC_CLOSED"}:
        Notification.objects.filter(
            incident_event__incident=incident,
            kind__in=["INC_NEW", "INC_RELEASED"],
            resolved_at=None,
        ).update(resolved_at=timezone.now())
    if event.action in {"INC_CREATED", "INC_RELEASED"} and incident.state == Incident.State.PENDING:
        kind = "INC_RELEASED" if event.action == "INC_RELEASED" else "INC_NEW"
        return _deliver(
            recipients("incidents.view_incident"),
            f"incident-event:{event.pk}",
            kind=kind,
            incident_event=event,
            title=Notification.Kind(kind).label,
            description=(
                f"{incident.device.code} · Incidencia #{incident.pk}. Disponible para tomar."
            ),
        )
    if event.action == "INC_CLOSED":
        reporter = get_user_model().objects.get(pk=incident.reporter_id)
        if (
            reporter.is_active
            and reporter.has_perm("notifications.view_notification")
            and (
                reporter.has_perm("incidents.view_incident")
                or reporter.has_perm("incidents.view_own_incident")
            )
        ):
            return _deliver(
                [reporter],
                f"incident-event:{event.pk}",
                kind="INC_CLOSED",
                incident_event=event,
                title="Incidencia cerrada",
                description=(
                    f"{incident.device.code} · Incidencia #{incident.pk}: "
                    f"{incident.get_outcome_display()}."
                ),
            )
    return 0


def _deliver(users, key, **values):
    created = 0
    for user in users:
        notice, new = Notification.objects.get_or_create(
            recipient=user, event_key=key, defaults=values
        )
        created += new
        if notice.resolved_at:
            Notification.objects.filter(pk=notice.pk).update(resolved_at=None)
    return created


def handle_maintenance_event(event):
    """Called while the caller holds the maintenance lock, in its transaction."""
    if not event.run_id:
        return
    run = event.run
    available = event.action in {"Creación", "RUN_CREATED", "RELEASED"}
    if available or run.state != MaintenanceRun.State.PENDING:
        Notification.objects.filter(event__run_id=run.pk, resolved_at=None).update(
            resolved_at=timezone.now()
        )
    if available and run.state == MaintenanceRun.State.PENDING:
        kind = (
            Notification.Kind.RELEASED
            if event.action == "RELEASED"
            else Notification.Kind.AVAILABLE
        )
        return _deliver(
            recipients(),
            f"event:{event.pk}",
            kind=kind,
            event=event,
            title=Notification.Kind(kind).label,
            description=(
                f"{event.maintenance.name} · Ejecución {run.number}. Disponible para tomar."
            ),
        )
    return 0


@transaction.atomic
def generate_for_maintenance(maintenance_id, *, today=None):
    """Parent lock serializes concurrent commands and operational transitions."""
    maintenance = Maintenance.objects.select_for_update().get(pk=maintenance_id)
    users = recipients()
    count = 0
    # Only backfill the latest availability event of currently available runs.
    for run in maintenance.runs.filter(state=MaintenanceRun.State.PENDING):
        event = run.events.filter(action__in=["Creación", "RUN_CREATED", "RELEASED"]).first()
        if event:
            kind = (
                Notification.Kind.RELEASED
                if event.action == "RELEASED"
                else Notification.Kind.AVAILABLE
            )
            count += _deliver(
                users,
                f"event:{event.pk}",
                kind=kind,
                event=event,
                title=Notification.Kind(kind).label,
                description=f"{maintenance.name} · Ejecución {run.number}. Disponible para tomar.",
            )
    valid_keys = []
    if maintenance.is_active:
        targets = outstanding_targets(maintenance)
        for target in targets:
            row = schedule_row(target, today=today)
            kind = {"soon": "SOON", "today": "TODAY", "overdue": "OVERDUE"}.get(row.timing)
            if not kind:
                continue
            key = f"due:{target.pk}:{row.due_date.isoformat()}:{kind}"
            valid_keys.append(key)
            count += _deliver(
                users,
                key,
                kind=kind,
                target=target,
                due_on=row.due_date,
                title=Notification.Kind(kind).label,
                description=(
                    f"{target.device.code} · {maintenance.name}. Vence {row.due_date:%d/%m/%Y}."
                ),
            )
    Notification.objects.filter(target__maintenance=maintenance, resolved_at=None).exclude(
        event_key__in=valid_keys
    ).update(resolved_at=timezone.now())
    return count


@transaction.atomic
def mark_read(*, actor, notice_id=None):
    notices = accessible_notices(actor)
    if notice_id is not None:
        # Ownership is mandatory even for administrators.
        notice = notices.select_related("event", "target", "incident_event").get(pk=notice_id)
        notices.filter(pk=notice_id, read_at=None).update(read_at=timezone.now())
        return notice
    notices.filter(read_at=None, resolved_at=None).update(read_at=timezone.now())
