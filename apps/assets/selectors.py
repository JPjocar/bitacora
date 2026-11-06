from django.core.exceptions import PermissionDenied

from .models import Device


def visible_devices(user):
    devices = Device.objects.select_related("category", "location")
    if user.has_perm("assets.view_device"):
        return devices
    if user.has_perm("assets.view_device_limited"):
        return devices.filter(is_active=True).exclude(status=Device.Status.WITHDRAWN)
    raise PermissionDenied
