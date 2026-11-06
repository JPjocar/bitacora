from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied


def require_permission(actor, permission):
    # Reload: service calls must not trust stale permission caches or active flags.
    if not actor or not actor.pk:
        raise PermissionDenied
    current = get_user_model().objects.get(pk=actor.pk)
    if not current.is_active or not current.has_perm(permission):
        raise PermissionDenied
    return current
