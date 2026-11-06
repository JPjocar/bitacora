from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.db.models.functions import Lower

from apps.core.models import AuditEvent, RetainedModel, RetainedQuerySet


class RetainedUserManager(UserManager.from_queryset(RetainedQuerySet)):
    pass


class User(AbstractUser, RetainedModel):
    version = models.PositiveIntegerField(default=1, editable=False)
    objects = RetainedUserManager()

    class Meta:
        ordering = ["username", "pk"]
        permissions = [("assign_role", "Puede asignar roles de negocio")]
        constraints = [
            models.UniqueConstraint(
                Lower("username"),
                name="accounts_username_ci_unique",
                violation_error_message=(
                    "Ya existe un usuario con ese nombre, "
                    "incluso con otra combinación de mayúsculas."
                ),
            )
        ]
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"

    @property
    def business_role(self):
        return self.groups.first()


class UserEvent(AuditEvent):
    subject = models.ForeignKey(User, on_delete=models.PROTECT, related_name="events")

    class Meta(AuditEvent.Meta):
        verbose_name = "evento de usuario"
        verbose_name_plural = "eventos de usuario"
