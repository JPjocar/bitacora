from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class RetainedQuerySet(models.QuerySet):
    def delete(self):
        raise ValidationError("Este registro conserva historial. Utilice la desactivación.")


class RetainedModel(models.Model):
    objects = RetainedQuerySet.as_manager()

    class Meta:
        abstract = True

    def delete(self, *args, **kwargs):
        raise ValidationError("Este registro conserva historial. Utilice la desactivación.")


class AuditQuerySet(RetainedQuerySet):
    def update(self, **kwargs):
        raise ValidationError("El historial no se puede modificar.")

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError("El historial no se puede modificar.")


class AuditEvent(RetainedModel):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField("Fecha", auto_now_add=True)
    action = models.CharField("Acción", max_length=40)
    changes = models.JSONField("Cambios", default=dict)
    objects = AuditQuerySet.as_manager()

    class Meta:
        abstract = True
        ordering = ["-created_at", "-pk"]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("El historial no se puede modificar.")
        return super().save(*args, **kwargs)
