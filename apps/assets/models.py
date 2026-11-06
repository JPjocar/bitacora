import secrets
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator, RegexValidator
from django.db import models
from django.db.models.functions import Lower, Trim
from django.utils import timezone

from apps.core.models import AuditEvent, AuditQuerySet, RetainedModel, RetainedQuerySet

CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def generate_device_code():
    return "EQ-" + "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))


class Category(RetainedModel):
    class Kind(models.TextChoices):
        PC = "PC", "PC de escritorio"
        LAPTOP = "LAPTOP", "Laptop"
        ROUTER = "ROUTER", "Router"
        PRINTER = "IMPRESORA", "Impresora"
        MONITOR = "MONITOR", "Monitor"
        OTHER = "OTROS", "Otros"

    name = models.CharField("Nombre", max_length=80)
    kind = models.CharField("Tipo", max_length=12, choices=Kind.choices)
    description = models.TextField(
        "Descripción", max_length=1000, blank=True, validators=[MaxLengthValidator(1000)]
    )
    is_active = models.BooleanField("Activo", default=True)
    version = models.PositiveIntegerField(default=1, editable=False)

    class Meta:
        ordering = ["name", "pk"]
        verbose_name = "categoría"
        verbose_name_plural = "categorías"
        constraints = [
            models.UniqueConstraint(
                Lower(Trim("name")),
                name="assets_category_name_unique",
                violation_error_message="Ya existe una categoría con ese nombre.",
            ),
            models.CheckConstraint(
                condition=~models.Q(name__regex=r"^\s*$"), name="assets_category_name_required"
            ),
            models.CheckConstraint(
                condition=models.Q(
                    kind__in=["PC", "LAPTOP", "ROUTER", "IMPRESORA", "MONITOR", "OTROS"]
                ),
                name="assets_category_valid_kind",
            ),
        ]

    def clean(self):
        self.name = self.name.strip()
        self.description = self.description.strip()

    @property
    def technical_help(self):
        return {
            self.Kind.PC: "Opcional: procesador, memoria RAM, almacenamiento y sistema operativo.",
            self.Kind.LAPTOP: "Opcional: procesador, memoria, almacenamiento, pantalla y batería.",
            self.Kind.ROUTER: (
                "Opcional: puertos, estándares Wi-Fi y versión de firmware. "
                "No registre contraseñas."
            ),
            self.Kind.PRINTER: "Opcional: tecnología de impresión, conectividad y consumibles.",
            self.Kind.MONITOR: "Opcional: tamaño, resolución y conectores.",
        }.get(
            self.kind, "Describa las características relevantes de este dispositivo. Es opcional."
        )

    def __str__(self):
        return self.name


class DeviceQuerySet(RetainedQuerySet):
    def update(self, **kwargs):
        if {"code", "public_id"} & kwargs.keys():
            raise ValidationError("Los identificadores del dispositivo son inmutables.")
        return super().update(**kwargs)

    def bulk_update(self, objs, fields, batch_size=None):
        if {"code", "public_id"} & set(fields):
            raise ValidationError("Los identificadores del dispositivo son inmutables.")
        return super().bulk_update(objs, fields, batch_size=batch_size)


class Device(RetainedModel):
    class Status(models.TextChoices):
        OPERATIONAL = "OPERATIVO", "Operativo"
        OBSERVATIONS = "CON_OBSERVACIONES", "Con observaciones"
        OUT_OF_SERVICE = "FUERA_DE_SERVICIO", "Fuera de servicio"
        WITHDRAWN = "RETIRADO_DEL_CONTROL_OPERATIVO", "Retirado del control operativo"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    code = models.CharField(
        "Código",
        max_length=11,
        unique=True,
        editable=False,
        default=generate_device_code,
        validators=[RegexValidator(r"^EQ-[ABCDEFGHJKMNPQRSTUVWXYZ23456789]{8}$")],
    )
    name = models.CharField("Nombre", max_length=120)
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="devices", verbose_name="Categoría"
    )
    brand = models.CharField("Marca", max_length=80, blank=True)
    model = models.CharField("Modelo", max_length=120, blank=True)
    serial_number = models.CharField("Número de serie", max_length=120, blank=True)
    location = models.ForeignKey(
        "locations.Location",
        on_delete=models.PROTECT,
        related_name="devices",
        verbose_name="Ubicación actual",
    )
    status = models.CharField(
        "Estado operativo", max_length=32, choices=Status.choices, default=Status.OPERATIONAL
    )
    observations = models.TextField(
        "Observaciones", max_length=3000, blank=True, validators=[MaxLengthValidator(3000)]
    )
    technical_details = models.TextField(
        "Detalles técnicos", max_length=4000, blank=True, validators=[MaxLengthValidator(4000)]
    )
    acquired_on = models.DateField("Fecha de adquisición", null=True, blank=True)
    commissioned_on = models.DateField("Puesta en servicio", null=True, blank=True)
    is_active = models.BooleanField("Activo en el registro", default=True)
    version = models.PositiveIntegerField(default=1, editable=False)
    created_at = models.DateTimeField("Registro", auto_now_add=True)
    updated_at = models.DateTimeField("Última modificación", auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", editable=False
    )
    objects = DeviceQuerySet.as_manager()

    class Meta:
        ordering = ["name", "pk"]
        verbose_name = "dispositivo"
        verbose_name_plural = "dispositivos"
        permissions = [
            ("update_device_operation", "Puede actualizar estado y observaciones"),
            ("view_device_limited", "Puede consultar la ficha limitada de equipos"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(name__regex=r"^\s*$"), name="assets_device_name_required"
            ),
            models.CheckConstraint(
                condition=models.Q(
                    status__in=[
                        "OPERATIVO",
                        "CON_OBSERVACIONES",
                        "FUERA_DE_SERVICIO",
                        "RETIRADO_DEL_CONTROL_OPERATIVO",
                    ]
                ),
                name="assets_device_valid_status",
            ),
            models.CheckConstraint(
                condition=models.Q(code__regex=r"^EQ-[ABCDEFGHJKMNPQRSTUVWXYZ23456789]{8}$"),
                name="assets_device_valid_code",
            ),
            models.CheckConstraint(
                condition=models.Q(acquired_on__isnull=True)
                | models.Q(commissioned_on__isnull=True)
                | models.Q(commissioned_on__gte=models.F("acquired_on")),
                name="assets_device_dates_ordered",
                violation_error_message=(
                    "La puesta en servicio no puede ser anterior a la adquisición."
                ),
            ),
        ]

    def clean(self):
        for field in (
            "name",
            "brand",
            "model",
            "serial_number",
            "observations",
            "technical_details",
        ):
            setattr(self, field, getattr(self, field).strip())
        for field in ("acquired_on", "commissioned_on"):
            value = getattr(self, field)
            if value and value > timezone.localdate():
                raise ValidationError({field: "La fecha no puede estar en el futuro."})

    def save(self, *args, **kwargs):
        if not self._state.adding:
            previous = type(self).objects.values("code", "public_id").get(pk=self.pk)
            if self.code != previous["code"] or self.public_id != previous["public_id"]:
                raise ValidationError("Los identificadores del dispositivo son inmutables.")
        return super().save(*args, **kwargs)

    @property
    def movement_warning(self):
        if not self.is_active:
            return (
                "Este dispositivo está inactivo en el registro. El traslado conservará ese estado."
            )
        if self.status in (self.Status.OUT_OF_SERVICE, self.Status.WITHDRAWN):
            return (
                f"El equipo está {self.get_status_display().lower()}. "
                "Trasladarlo no implica repararlo."
            )
        return ""

    def __str__(self):
        return f"{self.code} · {self.name}"


class CategoryEvent(AuditEvent):
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="events")


class DeviceEvent(AuditEvent):
    device = models.ForeignKey(Device, on_delete=models.PROTECT, related_name="events")


class Movement(RetainedModel):
    device = models.ForeignKey(Device, on_delete=models.PROTECT, related_name="movements")
    origin = models.ForeignKey(
        "locations.Location", on_delete=models.PROTECT, related_name="outgoing_movements"
    )
    destination = models.ForeignKey(
        "locations.Location",
        on_delete=models.PROTECT,
        related_name="incoming_movements",
        verbose_name="Destino",
    )
    reason = models.CharField("Motivo", max_length=300)
    notes = models.TextField(
        "Observaciones del traslado",
        max_length=2000,
        blank=True,
        validators=[MaxLengthValidator(2000)],
    )
    effective_at = models.DateTimeField("Fecha y hora efectiva")
    recorded_at = models.DateTimeField("Fecha registrada", auto_now_add=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    device_version = models.PositiveIntegerField(editable=False)
    objects = AuditQuerySet.as_manager()

    class Meta:
        ordering = ["-recorded_at", "-pk"]
        verbose_name = "movimiento"
        verbose_name_plural = "movimientos"
        default_permissions = ("add", "view")
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(origin=models.F("destination")),
                name="assets_movement_different_locations",
            ),
            models.CheckConstraint(
                condition=~models.Q(reason__regex=r"^\s*$"), name="assets_movement_reason_required"
            ),
            models.UniqueConstraint(
                fields=["device", "device_version"], name="assets_movement_version_unique"
            ),
        ]

    def clean(self):
        self.reason = self.reason.strip()
        self.notes = self.notes.strip()
        if self.effective_at and (
            timezone.is_naive(self.effective_at) or self.effective_at > timezone.now()
        ):
            raise ValidationError(
                {"effective_at": "Indique una fecha con zona horaria que no sea futura."}
            )

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Los movimientos son históricos y no se pueden modificar.")
        return super().save(*args, **kwargs)
