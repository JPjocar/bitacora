"""Explicit transactional integration; no signals, external delivery or GET writes."""

from django.contrib.auth import get_user_model
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
    return require_permission(actor, "maintenance.view_maintenance")


def recipients():
    users = get_user_model().objects.filter(
        is_active=True, groups__name__in=[ADMINISTRATOR, TECHNICIAN]
    )
    for app, code in [("maintenance", "view_maintenance"), ("notifications", "view_notification")]:
        users = users.filter(
            Q(is_superuser=True)
            | Q(user_permissions__content_type__app_label=app, user_permissions__codename=code)
            | Q(
                groups__permissions__content_type__app_label=app, groups__permissions__codename=code
            )
        )
    return list(users.distinct().order_by("pk"))


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
    actor = require_access(actor)
    notices = Notification.objects.filter(recipient=actor)
    if notice_id is not None:
        # Ownership is mandatory even for administrators.
        notice = notices.select_related("event", "target").get(pk=notice_id)
        notices.filter(pk=notice_id, read_at=None).update(read_at=timezone.now())
        return notice
    notices.filter(read_at=None, resolved_at=None).update(read_at=timezone.now())
