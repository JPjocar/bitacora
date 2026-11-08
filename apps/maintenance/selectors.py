from dataclasses import dataclass
from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.db.models import Exists, OuterRef, Q, Subquery
from django.utils import timezone

from apps.assets.models import Device

from .dates import add_interval
from .models import MaintenanceRun, MaintenanceRunDevice, MaintenanceTarget

OPEN_STATES = [
    MaintenanceRun.State.PENDING,
    MaintenanceRun.State.ASSIGNED,
    MaintenanceRun.State.RUNNING,
]
SOON_DAYS = 7
TIMING_LABELS = {
    "overdue": "Vencido",
    "today": "Hoy",
    "soon": "Próximo (7 días)",
    "later": "Posterior",
}


def targets_with_last_completion(maintenance=None, *, active_only=True):
    completed = MaintenanceRunDevice.objects.filter(
        target_id=OuterRef("pk"), result=MaintenanceRunDevice.Result.COMPLETED
    ).order_by("-device_executed_on", "-run__number", "-pk")
    opened = MaintenanceRunDevice.objects.filter(
        target_id=OuterRef("pk"), run__state__in=OPEN_STATES
    )
    targets = MaintenanceTarget.objects.all()
    if maintenance is not None:
        targets = targets.filter(maintenance=maintenance)
    if active_only:
        targets = targets.filter(is_active=True)
    return targets.select_related("maintenance", "device__category", "device__location").annotate(
        last_completed_on=Subquery(completed.values("device_executed_on")[:1]),
        last_completed_run_id=Subquery(completed.values("run_id")[:1]),
        open_run_id=Subquery(opened.order_by("-run__number").values("run_id")[:1]),
    )


def due_for_target(maintenance, last_completed_on):
    if not maintenance.is_recurring:
        return maintenance.planned_date
    return add_interval(
        last_completed_on or maintenance.base_date,
        maintenance.interval_value,
        maintenance.interval_unit,
    )


def outstanding_targets(maintenance=None):
    """Live preventive obligations, including unfinished one-off work."""
    noncancelled = MaintenanceRunDevice.objects.filter(target_id=OuterRef("pk")).exclude(
        run__state=MaintenanceRun.State.CANCELLED
    )
    return (
        targets_with_last_completion(maintenance)
        .filter(maintenance__is_active=True, device__is_active=True)
        .exclude(device__status=Device.Status.WITHDRAWN)
        .filter(
            Q(maintenance__is_recurring=True)
            | (Q(last_completed_on=None) & Q(Exists(noncancelled)))
        )
    )


@dataclass
class TargetSchedule:
    target: MaintenanceTarget
    due_date: date
    timing: str
    selectable: bool
    proposed: bool

    @property
    def timing_label(self):
        return TIMING_LABELS[self.timing]


def schedule_row(target, *, today=None):
    today = today or timezone.localdate()
    soon = today + timedelta(days=SOON_DAYS)
    maintenance = target.maintenance
    due = due_for_target(maintenance, target.last_completed_on)
    timing = (
        "overdue"
        if due < today
        else "today"
        if due == today
        else "soon"
        if due <= soon
        else "later"
    )
    eligible = (
        maintenance.is_active
        and target.device.is_active
        and target.device.status != Device.Status.WITHDRAWN
        and target.open_run_id is None
    )
    return TargetSchedule(target, due, timing, eligible, eligible and due <= soon)


def target_schedule(maintenance, *, today=None):
    rows = []
    for target in targets_with_last_completion(maintenance):
        rows.append(schedule_row(target, today=today))
    return sorted(rows, key=lambda row: (row.due_date, row.target.device.code))


def has_pending_work(device_id):
    """Read-only integration: deactivating configuration does not close its execution."""
    return MaintenanceRunDevice.objects.filter(
        target__device_id=device_id,
        result="SIN_FINALIZAR",
        run__state__in=OPEN_STATES,
    ).exists()


def device_preventive_history(device_id):
    """Read-only history for the authorized device sheet, across all definitions/cycles."""
    return (
        MaintenanceRunDevice.objects.filter(target__device_id=device_id)
        .select_related("run__maintenance")
        .order_by("-run__created_at", "-run__number", "-pk")
    )


@dataclass
class MaintenanceSchedule:
    earliest_due: date | None = None
    overdue_count: int = 0
    equipment_count: int = 0
    calendar_error: bool = False


def list_schedules(maintenances, *, today=None):
    """Batch the current page, keeping unfinished work's original deadlines.

    Unfinished work stays visible even if its device/registration was archived.
    Other obligations use the live calendar, including omitted devices.
    Completed or cancelled one-off work has no next deadline.
    """
    today = today or timezone.localdate()
    summaries = {item.pk: MaintenanceSchedule() for item in maintenances}
    if not summaries:
        return summaries
    unfinished = MaintenanceRunDevice.objects.filter(
        run__maintenance_id__in=summaries,
        run__state__in=OPEN_STATES,
        result=MaintenanceRunDevice.Result.UNFINISHED,
    ).values_list("run__maintenance_id", "target_id", "due_date")
    open_targets = set()

    def include(maintenance_id, due):
        summary = summaries[maintenance_id]
        summary.equipment_count += 1
        summary.overdue_count += due < today
        if summary.earliest_due is None or due < summary.earliest_due:
            summary.earliest_due = due

    for maintenance_id, target_id, due in unfinished:
        open_targets.add(target_id)
        include(maintenance_id, due)
    for target in outstanding_targets().filter(maintenance_id__in=summaries):
        if target.pk in open_targets:
            continue
        try:
            include(
                target.maintenance_id, due_for_target(target.maintenance, target.last_completed_on)
            )
        except ValidationError:
            summaries[target.maintenance_id].calendar_error = True
    return summaries
