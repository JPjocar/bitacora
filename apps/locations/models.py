from django.core.validators import RegexValidator
from django.db import models
from django.db.models.functions import Lower, Trim

from apps.core.models import AuditEvent, RetainedModel


class Location(RetainedModel):
    class Kind(models.TextChoices):
        LABORATORY = "LABORATORIO", "Laboratorio"
        STORAGE = "ALMACEN", "Almacén"
        MAINTENANCE = "MANTENIMIENTO", "Ambiente de mantenimiento"

    name = models.CharField("Nombre", max_length=120)
    code = models.CharField(
        "Código",
        max_length=24,
        blank=True,
        default="",
        validators=[
            RegexValidator(r"^[A-Za-z0-9_-]+$", "Use letras, números, guiones o guiones bajos.")
        ],
    )
    kind = models.CharField("Tipo", max_length=20, choices=Kind.choices)
    description = models.TextField("Descripción", max_length=2000, blank=True)
    is_active = models.BooleanField("Activo", default=True)
    version = models.PositiveIntegerField(default=1, editable=False)
    created_at = models.DateTimeField("Creación", auto_now_add=True)
    updated_at = models.DateTimeField("Última modificación", auto_now=True)

    class Meta:
        ordering = ["name", "pk"]
        verbose_name = "ubicación"
        verbose_name_plural = "ubicaciones"
        constraints = [
            models.UniqueConstraint(
                Lower(Trim("name")),
                name="locations_name_ci_unique",
                violation_error_message="Ya existe una ubicación con ese nombre.",
            ),
            models.UniqueConstraint(
                Lower(Trim("code")),
                condition=~models.Q(code=""),
                name="locations_code_ci_unique",
                violation_error_message="Ya existe una ubicación con ese código.",
            ),
            models.CheckConstraint(
                condition=~models.Q(name__regex=r"^\s*$"),
                name="locations_name_not_blank",
                violation_error_message="El nombre no puede estar vacío.",
            ),
            models.CheckConstraint(
                condition=models.Q(kind__in=["LABORATORIO", "ALMACEN", "MANTENIMIENTO"]),
                name="locations_valid_kind",
                violation_error_message="Seleccione un tipo de ambiente válido.",
            ),
        ]

    def clean(self):
        super().clean()
        self.name = self.name.strip()
        self.code = self.code.strip().upper()
        self.description = self.description.strip()

    def __str__(self):
        return self.name


class LocationEvent(AuditEvent):
    location = models.ForeignKey(Location, on_delete=models.PROTECT, related_name="events")

    class Meta(AuditEvent.Meta):
        verbose_name = "evento de ubicación"
        verbose_name_plural = "eventos de ubicación"
