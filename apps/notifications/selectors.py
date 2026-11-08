"""Context for existing and new notices, without mutating their event snapshots."""

from django.db.models import Prefetch
from django.utils.text import Truncator

from apps.maintenance.models import MaintenanceRunDevice


def with_context(notices):
    return notices.select_related(
        "event__run",
        "incident_event__incident__device__category",
        "incident_event__incident__device__location",
        "target__device__category",
        "target__device__location",
    ).prefetch_related(
        Prefetch(
            "event__run__participants",
            queryset=MaintenanceRunDevice.objects.select_related(
                "category", "target__device"
            ).order_by("pk"),
        )
    )


def describe_context(notice):
    if notice.incident_event_id:
        incident = notice.incident_event.incident
        device = incident.device
        return {
            "equipment": f"{device.category.get_kind_display()} · {device.code} · {device.name}",
            "location": device.location.name,
            "excerpt": Truncator(" ".join(incident.symptoms.split())).chars(160),
            "action": "Ver incidencia",
        }
    if notice.target_id:
        device = notice.target.device
        return {
            "equipment": f"{device.category.get_kind_display()} · {device.code} · {device.name}",
            "location": device.location.name,
            "excerpt": "",
            "action": "Ver vencimiento",
        }
    participants = list(notice.event.run.participants.all())
    categories = sorted({item.category.get_kind_display() for item in participants})
    types = ", ".join(categories[:3])
    if len(categories) > 3:
        types += f" y {len(categories) - 3} tipos más"
    devices = "; ".join(
        f"{item.target.device.code} · {item.device_name}" for item in participants[:2]
    )
    if len(participants) > 2:
        devices += f" y {len(participants) - 2} equipos más"
    count = len(participants)
    return {
        "equipment": f"{count} equipo{'s' if count != 1 else ''} · {types}",
        "location": "",
        "excerpt": Truncator(devices).chars(200),
        "action": "Ver mantenimiento",
    }
