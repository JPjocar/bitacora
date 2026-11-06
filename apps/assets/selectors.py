from django.core.exceptions import PermissionDenied

from .models import Device


def movement_warning(device):
    from apps.maintenance.selectors import has_pending_work

    warnings = [device.movement_warning] if device.movement_warning else []
    if has_pending_work(device.pk):
        warnings.append(
            "El equipo tiene mantenimiento preventivo pendiente. "
            "Trasladarlo no completa ni omite sus tareas."
        )
    return " ".join(warnings)


def visible_devices(user):
    devices = Device.objects.select_related("category", "location")
    if user.has_perm("assets.view_device"):
        return devices
    if user.has_perm("assets.view_device_limited"):
        return devices.filter(is_active=True).exclude(status=Device.Status.WITHDRAWN)
    raise PermissionDenied
