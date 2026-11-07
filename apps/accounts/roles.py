from django.contrib.auth.models import Group, Permission
from django.db import transaction

ADMINISTRATOR = "Administrador"
TECHNICIAN = "Técnico"
TEACHER = "Docente"
ROLE_PERMISSIONS = {
    ADMINISTRATOR: {
        "maintenance.create_next_run",
        "maintenance.add_maintenance",
        "maintenance.change_maintenance",
        "maintenance.view_maintenance",
        "maintenance.override_maintenance",
        "maintenance.backdate_maintenance",
        "accounts.view_user",
        "accounts.add_user",
        "accounts.change_user",
        "accounts.assign_role",
        "auth.view_group",
        "locations.view_location",
        "locations.add_location",
        "locations.change_location",
        "assets.view_category",
        "assets.add_category",
        "assets.change_category",
        "assets.view_device",
        "assets.add_device",
        "assets.print_device_label",
        "assets.change_device",
        "assets.update_device_operation",
        "assets.view_movement",
        "assets.add_movement",
    },
    TECHNICIAN: {
        "maintenance.create_next_run",
        "maintenance.take_maintenance",
        "maintenance.execute_maintenance",
        "maintenance.view_maintenance",
        "assets.print_device_label",
        "locations.view_location",
        "assets.view_device",
        "assets.view_category",
        "assets.update_device_operation",
        "assets.view_movement",
        "assets.add_movement",
    },
    TEACHER: {"assets.view_device_limited"},
}


@transaction.atomic
def sync_roles():
    """Explicit, idempotent provisioning. Never creates users or staff privileges."""
    for name, labels in ROLE_PERMISSIONS.items():
        group, _ = Group.objects.get_or_create(name=name)
        permissions = []
        for label in sorted(labels):
            app_label, codename = label.split(".")
            permissions.append(
                Permission.objects.get(content_type__app_label=app_label, codename=codename)
            )
        group.permissions.set(permissions)
