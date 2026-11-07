import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator
from django.db import models
from django.urls import reverse

from apps.core.models import AuditEvent, AuditQuerySet, RetainedModel


class Incident(RetainedModel):
    class State(models.TextChoices):
        PENDING = "PENDIENTE_ATENCION", "Pendiente de atención"
        ATTENDING = "EN_ATENCION", "En atención"
        CLOSED = "CERRADA", "Cerrada"

    class Outcome(models.TextChoices):
        SOLVED = "SOLUCIONADA", "Solucionada"
        UNREPAIRABLE = "NO_REPARABLE", "No reparable"
        INVALID = "INVALIDA_DUPLICADA", "Inválida o duplicada"

    device = models.ForeignKey("assets.Device", on_delete=models.PROTECT, related_name="incidents")
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reported_incidents"
    )
    symptoms = models.TextField(
        "Síntomas observados", max_length=3000, validators=[MaxLengthValidator(3000)]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    state = models.CharField(max_length=20, choices=State.choices, default=State.PENDING)
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="assigned_incidents",
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    outcome = models.CharField(max_length=20, choices=Outcome.choices, blank=True)
    closure_summary = models.TextField(
        max_length=3000, blank=True, validators=[MaxLengthValidator(3000)]
    )
    creation_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    creation_signature = models.CharField(max_length=64, editable=False)
    version = models.PositiveIntegerField(default=1, editable=False)
    objects = AuditQuerySet.as_manager()
    OPERATION_FIELDS = frozenset(
        {"state", "responsible", "closed_at", "closed_by", "outcome", "closure_summary", "version"}
    )

    class Meta:
        ordering = ["-created_at", "-pk"]
        default_permissions = ("add", "view")
        permissions = [
            ("view_own_incident", "Consultar sus propias incidencias"),
            ("take_incident", "Tomar incidencias como técnico"),
            ("attend_incident", "Atender sus incidencias asignadas"),
            ("override_incident", "Intervenir en incidencias con justificación administrativa"),
            (
                "close_unrepairable_incident",
                "Declarar una incidencia no reparable con justificación",
            ),
        ]
        indexes = [
            models.Index(fields=["state", "-created_at"]),
            models.Index(fields=["device", "-created_at"]),
            models.Index(fields=["reporter", "-created_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(version__gte=1), name="incident_positive_version"
            ),
            models.CheckConstraint(condition=~models.Q(symptoms=""), name="incident_has_symptoms"),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        state="PENDIENTE_ATENCION",
                        responsible__isnull=True,
                        closed_at=None,
                        closed_by=None,
                        outcome="",
                        closure_summary="",
                    )
                    | models.Q(
                        state="EN_ATENCION",
                        responsible__isnull=False,
                        closed_at=None,
                        closed_by=None,
                        outcome="",
                        closure_summary="",
                    )
                    | (
                        models.Q(
                            state="CERRADA",
                            closed_at__isnull=False,
                            closed_by__isnull=False,
                            outcome__in=["SOLUCIONADA", "NO_REPARABLE", "INVALIDA_DUPLICADA"],
                        )
                        & ~models.Q(closure_summary="")
                    )
                ),
                name="incident_coherent_state",
            ),
            models.CheckConstraint(
                condition=models.Q(closed_at=None)
                | models.Q(closed_at__gte=models.F("created_at")),
                name="incident_closes_after_report",
            ),
        ]

    def save(self, *args, **kwargs):
        fields = kwargs.get("update_fields")
        if not self._state.adding and (not fields or not set(fields) <= self.OPERATION_FIELDS):
            raise ValidationError(
                "El reporte original se conserva; utilice una acción de atención."
            )
        return super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("incidents:detail", args=[self.pk])


class IncidentEvent(AuditEvent):
    incident = models.ForeignKey(Incident, on_delete=models.PROTECT, related_name="events")
