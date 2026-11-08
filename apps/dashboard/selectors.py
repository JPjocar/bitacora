"""Read-only operational projections. Dates refer to deadlines and closure, not hours worked."""

from django.core.exceptions import ValidationError
from django.db.models import Count, Exists, OuterRef, Q, Subquery
from django.utils import timezone

from apps.assets.models import Device
from apps.maintenance.models import MaintenanceRun, MaintenanceRunDevice, MaintenanceTarget
from apps.maintenance.selectors import OPEN_STATES, outstanding_targets, schedule_row


def device_scope(filters):
    devices = Device.objects.select_related("category", "location").all()
    if filters.get("q"):
        devices = devices.filter(Q(code__icontains=filters["q"]) | Q(name__icontains=filters["q"]))
    for field, lookup in [
        ("location", "location"),
        ("kind", "category__kind"),
        ("status", "status"),
    ]:
        if filters.get(field):
            devices = devices.filter(**{lookup: filters[field]})
    if filters.get("active"):
        devices = devices.filter(is_active=filters["active"] == "yes")
    return devices


def _period(query, field, filters):
    for name, op in [("start", "gte"), ("end", "lte")]:
        if filters.get(name):
            query = query.filter(**{f"{field}__{op}": filters[name]})
    return query


def _in_period(day, filters):
    return (not filters.get("start") or day >= filters["start"]) and (
        not filters.get("end") or day <= filters["end"]
    )


def dashboard_data(filters, *, today=None, include_incidents=False):
    today = today or timezone.localdate()
    devices = device_scope(filters)
    matching = devices.order_by().values("pk")
    eligible = devices.filter(is_active=True).exclude(status=Device.Status.WITHDRAWN)
    active_plan = MaintenanceTarget.objects.filter(
        device_id=OuterRef("pk"),
        is_active=True,
        maintenance__is_active=True,
        maintenance__is_recurring=True,
    )
    unconfigured = eligible.filter(~Exists(active_plan)).order_by("code")
    participants = MaintenanceRunDevice.objects.filter(
        run_id=OuterRef("pk"), target__device_id__in=matching
    )
    runs = MaintenanceRun.objects.filter(Exists(participants)).select_related(
        "maintenance", "responsible"
    )
    if filters.get("run_state"):
        runs = runs.filter(state=filters["run_state"])
    # Date filters only constrain closed executions. Open work stays visible.
    closed_in_period = (
        Q(state__in=OPEN_STATES)
        | Q(
            pk__in=_period(
                runs.filter(completed_at__isnull=False), "completed_at__date", filters
            ).values("pk")
        )
        | Q(
            pk__in=_period(
                runs.filter(cancelled_at__isnull=False), "cancelled_at__date", filters
            ).values("pk")
        )
    )
    runs = runs.filter(closed_in_period)
    run_counts = dict(runs.order_by().values_list("state").annotate(total=Count("pk")))
    targets = outstanding_targets().filter(device_id__in=matching)
    if filters.get("run_state"):
        state_participant = MaintenanceRunDevice.objects.filter(
            target_id=OuterRef("pk"), run__state=filters["run_state"]
        )
        targets = targets.filter(Exists(state_participant))
    deadlines, invalid = [], []
    for target in targets:
        try:
            row = schedule_row(target, today=today)
        except ValidationError:
            invalid.append(target)
            continue
        if _in_period(row.due_date, filters):
            deadlines.append(row)
    deadlines.sort(key=lambda row: (row.due_date, row.target.device.code, row.target.pk))
    omitted = MaintenanceRunDevice.objects.filter(
        target_id=OuterRef("pk"), result=MaintenanceRunDevice.Result.OMITTED
    ).order_by("-run__number")
    completed = MaintenanceRunDevice.objects.filter(
        target_id=OuterRef("pk"), result=MaintenanceRunDevice.Result.COMPLETED
    ).order_by("-run__number")
    # Workflow order, separate from the actual-date anchor used to calculate recurrence.
    omission_targets = targets.annotate(
        omitted_cycle=Subquery(omitted.values("run__number")[:1]),
        completed_cycle=Subquery(completed.values("run__number")[:1]),
        omitted_at=Subquery(omitted.values("finalized_at")[:1]),
    )
    omissions = [
        target
        for target in omission_targets
        if target.omitted_cycle is not None
        and (target.completed_cycle is None or target.omitted_cycle > target.completed_cycle)
        and _in_period(timezone.localdate(target.omitted_at), filters)
    ]
    datasets = {
        "deadlines": deadlines,
        "runs": runs.order_by("-created_at", "-pk"),
        "unconfigured": unconfigured,
        "omissions": omissions,
        "devices": devices.order_by("code"),
    }
    incident_data = {}
    if include_incidents:
        from apps.incidents.selectors import dashboard_incidents

        incident_data = dashboard_incidents(devices, filters)
        datasets["incidents"] = incident_data.pop("incident_rows")
        datasets["recurrent_incidents"] = incident_data.pop("repeated_rows")
    return {
        **incident_data,
        "inventory_count": devices.count(),
        "unconfigured_count": unconfigured.count(),
        "overdue_count": sum(row.timing == "overdue" for row in deadlines),
        "today_count": sum(row.timing == "today" for row in deadlines),
        "soon_count": sum(row.timing == "soon" for row in deadlines),
        "omission_count": len(omissions),
        "run_counts": [
            {"state": state, "label": label, "count": run_counts.get(state, 0)}
            for state, label in MaintenanceRun.State.choices
        ],
        "by_kind": devices.order_by().values("category__kind").annotate(total=Count("pk")),
        "by_location": devices.order_by().values("location__name").annotate(total=Count("pk")),
        "by_status": devices.order_by().values("status").annotate(total=Count("pk")),
        "invalid_targets": invalid,
        "rows": datasets[filters.get("section") or "deadlines"],
        "section": filters.get("section") or "deadlines",
        "as_of": today,
    }
