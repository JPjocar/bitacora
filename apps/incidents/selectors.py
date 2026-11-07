from django.core.exceptions import PermissionDenied
from django.db.models import Count, OuterRef, Q, Subquery

from apps.core.permissions import require_permission

from .models import Incident


def visible_incidents(actor):
    # Reload also protects direct service/selector calls with a stale user object.
    permission = (
        "incidents.view_incident"
        if actor.has_perm("incidents.view_incident")
        else "incidents.view_own_incident"
    )
    actor = require_permission(actor, permission)
    incidents = Incident.objects.select_related(
        "device__location", "device__category", "reporter", "responsible", "closed_by"
    )
    if actor.has_perm("incidents.view_incident"):
        return incidents
    if actor.has_perm("incidents.view_own_incident"):
        return incidents.filter(reporter=actor)
    raise PermissionDenied


def can_control(actor, incident):
    return actor.has_perm("incidents.override_incident") or (
        actor.has_perm("incidents.attend_incident") and incident.responsible_id == actor.pk
    )


def dashboard_incidents(devices, filters):
    """Only called after checking full incident access in the dashboard view."""
    incidents = Incident.objects.filter(device_id__in=devices.order_by().values("pk"))
    if filters.get("incident_state"):
        incidents = incidents.filter(state=filters["incident_state"])
    closed = incidents.filter(state=Incident.State.CLOSED)
    repeated = Incident.objects.filter(device_id=OuterRef("pk")).exclude(
        outcome=Incident.Outcome.INVALID
    )
    if filters.get("incident_state"):
        repeated = repeated.filter(state=filters["incident_state"])
    for field, op in [("start", "gte"), ("end", "lte")]:
        if filters.get(field):
            closed = closed.filter(**{f"closed_at__date__{op}": filters[field]})
            repeated = repeated.filter(**{f"created_at__date__{op}": filters[field]})
    incidents = incidents.filter(~Q(state=Incident.State.CLOSED) | Q(pk__in=closed.values("pk")))
    counts = dict(incidents.order_by().values_list("state").annotate(total=Count("pk")))
    repeated_devices = (
        devices.annotate(
            incident_count=Subquery(
                repeated.order_by().values("device_id").annotate(n=Count("pk")).values("n")[:1]
            )
        )
        .filter(incident_count__gte=2)
        .order_by("-incident_count", "code")
    )
    return {
        "incident_counts": [
            {"label": label, "count": counts.get(state, 0)}
            for state, label in Incident.State.choices
        ],
        "repeated_incident_count": repeated_devices.count(),
        "incident_rows": incidents.select_related(
            "device__location", "device__category", "responsible", "reporter"
        ),
        "repeated_rows": repeated_devices,
    }
