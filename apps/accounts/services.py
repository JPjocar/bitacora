from django.contrib.auth import password_validation
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction

from apps.core.permissions import require_permission

from .models import User, UserEvent
from .roles import ADMINISTRATOR, ROLE_PERMISSIONS

USER_FIELDS = ("username", "first_name", "last_name", "email", "is_active")


def _role_lock():
    try:
        return Group.objects.select_for_update().get(name=ADMINISTRATOR)
    except Group.DoesNotExist as exc:
        raise ValidationError("Ejecute sync_roles antes de gestionar usuarios.") from exc


def _get_role(name):
    if name not in ROLE_PERMISSIONS:
        raise ValidationError({"role": "Seleccione un rol de negocio válido."})
    try:
        return Group.objects.get(name=name)
    except Group.DoesNotExist as exc:
        raise ValidationError("Ejecute sync_roles antes de gestionar usuarios.") from exc


@transaction.atomic
def save_user(*, actor, data, user_id=None, expected_version=None, password=None):
    admin_group = _role_lock()
    actor = require_permission(actor, "accounts.change_user" if user_id else "accounts.add_user")
    user = User.objects.select_for_update().get(pk=user_id) if user_id else User()
    if user.is_superuser:
        raise PermissionDenied("Los superusuarios se administran mediante comandos internos.")
    old_role = user.business_role if user.pk else None
    role = _get_role(data.get("role"))
    if old_role != role:
        require_permission(actor, "accounts.assign_role")
    if user_id and user.version != expected_version:
        raise ValidationError("Otro usuario modificó esta cuenta. Recargue antes de guardar.")
    before = {field: getattr(user, field) for field in USER_FIELDS} if user_id else {}
    before["role"] = old_role.name if old_role else None
    active = data.get("is_active", user.is_active)
    if not isinstance(active, bool):
        raise ValidationError({"is_active": "Indique un estado activo válido."})
    if user_id == actor.pk and (not active or role != old_role):
        raise ValidationError("No puede desactivar su propia cuenta ni cambiar su propio rol.")
    if (
        user_id
        and user.is_active
        and old_role == admin_group
        and (not active or role != admin_group)
        and not User.objects.filter(is_active=True, groups=admin_group).exclude(pk=user.pk).exists()
    ):
        raise ValidationError("Debe conservar al menos un administrador activo.")
    for field in USER_FIELDS:
        if field in data:
            setattr(user, field, data[field])
    user.username = User.normalize_username(user.username.strip())
    user.email = User.objects.normalize_email(user.email.strip())
    user.full_clean(exclude=["password"])
    if not user_id:
        if not password:
            raise ValidationError({"password1": "Indique una contraseña inicial."})
        password_validation.validate_password(password, user)
        user.set_password(password)
    after = {field: getattr(user, field) for field in USER_FIELDS}
    after["role"] = role.name
    changes = {
        field: {"antes": before.get(field), "después": value}
        for field, value in after.items()
        if before.get(field) != value
    }
    if user_id and not changes:
        return user
    if user_id:
        user.version += 1
    try:
        with transaction.atomic():
            user.save()
            user.groups.set([role])
    except IntegrityError as exc:
        raise ValidationError("El nombre de usuario ya está registrado.") from exc
    UserEvent.objects.create(
        actor=actor,
        subject=user,
        action="Actualización" if user_id else "Creación",
        changes=changes,
    )
    return user


@transaction.atomic
def reset_password(*, actor, user_id, password):
    _role_lock()
    actor = require_permission(actor, "accounts.change_user")
    user = User.objects.select_for_update().get(pk=user_id)
    if user.is_superuser or user.pk == actor.pk:
        raise PermissionDenied("Utilice el cambio de contraseña personal para su cuenta.")
    password_validation.validate_password(password, user)
    user.set_password(password)
    user.version += 1
    user.save(update_fields=["password", "version"])
    UserEvent.objects.create(actor=actor, subject=user, action="Restablecimiento de contraseña")
    return user


@transaction.atomic
def change_password(*, actor, old_password, password):
    _role_lock()
    user = User.objects.select_for_update().get(pk=actor.pk)
    if not user.is_active:
        raise PermissionDenied
    if not user.check_password(old_password):
        raise ValidationError({"old_password": "La contraseña actual no es correcta."})
    password_validation.validate_password(password, user)
    user.set_password(password)
    user.version += 1
    user.save(update_fields=["password", "version"])
    UserEvent.objects.create(actor=user, subject=user, action="Cambio de contraseña")
    return user
