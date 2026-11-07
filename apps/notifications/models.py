from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse

from apps.core.models import RetainedModel, RetainedQuerySet


class NotificationQuerySet(RetainedQuerySet):
    def update(self, **kwargs):
        if not kwargs or set(kwargs) - {"read_at", "resolved_at"}:
            raise ValidationError("Solo se puede cambiar la lectura o vigencia del aviso.")
        return super().update(**kwargs)

    def bulk_update(self, objs, fields, batch_size=None):
        if set(fields) - {"read_at", "resolved_at"}:
            raise ValidationError("El contenido del aviso se conserva.")
        return super().bulk_update(objs, fields, batch_size=batch_size)


class Notification(RetainedModel):
    class Kind(models.TextChoices):
        AVAILABLE = "AVAILABLE", "Mantenimiento disponible"
        RELEASED = "RELEASED", "Mantenimiento liberado"
        SOON = "SOON", "Preventivo próximo"
        TODAY = "TODAY", "Preventivo para hoy"
        OVERDUE = "OVERDUE", "Preventivo vencido"
        INCIDENT_NEW = "INC_NEW", "Nueva incidencia"
        INCIDENT_RELEASED = "INC_RELEASED", "Incidencia liberada"
        INCIDENT_CLOSED = "INC_CLOSED", "Incidencia cerrada"

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    kind = models.CharField(max_length=12, choices=Kind.choices)
    event = models.ForeignKey("maintenance.MaintenanceEvent", null=True, on_delete=models.PROTECT)
    incident_event = models.ForeignKey(
        "incidents.IncidentEvent", null=True, on_delete=models.PROTECT
    )
    target = models.ForeignKey("maintenance.MaintenanceTarget", null=True, on_delete=models.PROTECT)
    due_on = models.DateField(null=True)
    event_key = models.CharField(max_length=160)
    title = models.CharField(max_length=160)
    description = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True)
    resolved_at = models.DateTimeField(null=True)
    objects = NotificationQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at", "-pk"]
        default_permissions = ("view",)
        constraints = [
            models.UniqueConstraint(
                fields=["recipient", "event_key"], name="notice_recipient_event"
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        kind__in=["AVAILABLE", "RELEASED"],
                        event__isnull=False,
                        target__isnull=True,
                        due_on__isnull=True,
                        incident_event__isnull=True,
                    )
                    | models.Q(
                        kind__in=["SOON", "TODAY", "OVERDUE"],
                        event__isnull=True,
                        target__isnull=False,
                        due_on__isnull=False,
                        incident_event__isnull=True,
                    )
                    | models.Q(
                        kind__in=["INC_NEW", "INC_RELEASED", "INC_CLOSED"],
                        incident_event__isnull=False,
                        event__isnull=True,
                        target__isnull=True,
                        due_on__isnull=True,
                    )
                ),
                name="notice_source_matches_kind",
            ),
            models.CheckConstraint(condition=~models.Q(event_key=""), name="notice_key_not_empty"),
        ]
        indexes = [models.Index(fields=["recipient", "resolved_at", "read_at", "-created_at"])]

    def save(self, *args, **kwargs):
        if not self._state.adding and (
            not kwargs.get("update_fields")
            or set(kwargs["update_fields"]) - {"read_at", "resolved_at"}
        ):
            raise ValidationError("El contenido y destinatario del aviso se conservan.")
        return super().save(*args, **kwargs)

    def get_absolute_url(self):
        if self.incident_event_id:
            return reverse("incidents:detail", args=[self.incident_event.incident_id])
        if self.event_id:
            return reverse(
                "maintenance:run_detail", args=[self.event.maintenance_id, self.event.run_id]
            )
        return reverse("maintenance:due_dates", args=[self.target.maintenance_id])
