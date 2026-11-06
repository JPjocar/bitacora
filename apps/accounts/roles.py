from django.contrib.auth.models import Group, Permission
from django.db import transaction

ADMINISTRATOR = "Administrador"
TECHNICIAN = "Técnico"
TEACHER = "Docente"
ROLE_PERMISSIONS = {
    ADMINISTRATOR: {
        "accounts.view_user",
        "accounts.add_user",
        "accounts.change_user",
        "accounts.assign_role",
        "auth.view_group",
        "locations.view_location",
        "locations.add_location",
        "locations.change_location",
    },
    TECHNICIAN: {"locations.view_location"},
    TEACHER: set(),
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
