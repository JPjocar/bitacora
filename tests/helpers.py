from django.contrib.auth.models import Group

from apps.accounts.models import User
from apps.accounts.roles import ADMINISTRATOR, TEACHER, TECHNICIAN, sync_roles

PASSWORD = "Prueba-Segura-5831!"


def create_user(username, role=None, **kwargs):
    user = User.objects.create_user(username=username, password=PASSWORD, **kwargs)
    if role:
        user.groups.add(Group.objects.get(name=role))
    return user


def setup_users(cls):
    sync_roles()
    cls.admin = create_user("administrador", ADMINISTRATOR)
    cls.technician = create_user("tecnico", TECHNICIAN)
    cls.teacher = create_user("docente", TEACHER)


def user_data(user, **overrides):
    data = {
        field: getattr(user, field)
        for field in ("username", "first_name", "last_name", "email", "is_active")
    }
    data["role"] = user.business_role.name
    data.update(overrides)
    return data
