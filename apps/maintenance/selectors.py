from dataclasses import dataclass
from datetime import date, timedelta

from django.db.models import OuterRef, Subquery
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


def targets_with_last_completion(maintenance, *, active_only=True):
    completed = MaintenanceRunDevice.objects.filter(
        target_id=OuterRef("pk"), result=MaintenanceRunDevice.Result.COMPLETED
    ).order_by("-device_executed_on", "-run__number", "-pk")
    opened = MaintenanceRunDevice.objects.filter(
        target_id=OuterRef("pk"), run__state__in=OPEN_STATES
    )
    targets = MaintenanceTarget.objects.filter(maintenance=maintenance)
    if active_only:
        targets = targets.filter(is_active=True)
    return targets.select_related("device__category", "device__location").annotate(
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


def target_schedule(maintenance, *, today=None):
    today = today or timezone.localdate()
    soon = today + timedelta(days=SOON_DAYS)
    rows = []
    for target in targets_with_last_completion(maintenance):
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
        rows.append(TargetSchedule(target, due, timing, eligible, eligible and due <= soon))
    return sorted(rows, key=lambda row: (row.due_date, row.target.device.code))


def has_pending_work(device_id):
    """Read-only integration: deactivating configuration does not close its execution."""
    return MaintenanceRunDevice.objects.filter(
        target__device_id=device_id,
        result="SIN_FINALIZAR",
        run__state__in=OPEN_STATES,
    ).exists()
