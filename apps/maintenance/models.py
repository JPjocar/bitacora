from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator, MinValueValidator
from django.db import models

from apps.core.models import AuditEvent, AuditQuerySet, RetainedModel

from .dates import add_interval


class Maintenance(RetainedModel):
    class Unit(models.TextChoices):
        DAYS = "DIAS", "Días"
        MONTHS = "MESES", "Meses calendario"

    name = models.CharField("Nombre", max_length=120)
    description = models.TextField(
        "Descripción", blank=True, max_length=3000, validators=[MaxLengthValidator(3000)]
    )
    is_recurring = models.BooleanField("Periódico", default=False)
    base_date = models.DateField("Fecha base", null=True, blank=True)
    interval_value = models.PositiveIntegerField(
        "Intervalo", null=True, blank=True, validators=[MinValueValidator(1)]
    )
    interval_unit = models.CharField("Unidad", max_length=5, blank=True, choices=Unit.choices)
    planned_date = models.DateField("Fecha prevista", null=True, blank=True)
    is_active = models.BooleanField("Activo", default=True)
    version = models.PositiveIntegerField(default=1, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    creation_key = models.UUIDField(unique=True, editable=False)
    creation_signature = models.CharField(max_length=64, editable=False)

    class Meta:
        ordering = ["-created_at", "-pk"]
        verbose_name = "mantenimiento"
        default_permissions = ("add", "change", "view")
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(name__regex=r"^\s*$"), name="maint_name_required"
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        is_recurring=True,
                        base_date__isnull=False,
                        planned_date__isnull=True,
                        interval_value__isnull=False,
                        interval_value__gt=0,
                        interval_unit__in=["DIAS", "MESES"],
                    )
                    | models.Q(
                        is_recurring=False,
                        base_date__isnull=True,
                        interval_value__isnull=True,
                        interval_unit="",
                        planned_date__isnull=False,
                    )
                ),
                name="maint_valid_schedule",
                violation_error_message="Las fechas no corresponden al tipo de mantenimiento.",
            ),
        ]

    def clean(self):
        self.name = self.name.strip()
        self.description = self.description.strip()
        if self.is_recurring:
            if (
                not self.base_date
                or self.planned_date
                or not self.interval_value
                or not self.interval_unit
            ):
                raise ValidationError(
                    "Un mantenimiento periódico requiere fecha base e intervalo, "
                    "sin fecha prevista."
                )
            add_interval(self.base_date, self.interval_value, self.interval_unit)
        elif (
            not self.planned_date
            or self.base_date
            or self.interval_value is not None
            or self.interval_unit
        ):
            raise ValidationError(
                "Un mantenimiento único requiere fecha prevista, sin base ni intervalo."
            )

    @property
    def initial_due_date(self):
        if self.is_recurring:
            return add_interval(self.base_date, self.interval_value, self.interval_unit)
        return self.planned_date

    def __str__(self):
        return self.name


class MaintenanceTarget(RetainedModel):
    maintenance = models.ForeignKey(Maintenance, on_delete=models.PROTECT, related_name="targets")
    device = models.ForeignKey(
        "assets.Device", on_delete=models.PROTECT, related_name="maintenance_targets"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(fields=["maintenance", "device"], name="maint_target_unique")
        ]


class MaintenanceTaskTemplate(RetainedModel):
    class Scope(models.TextChoices):
        DEVICE = "DISPOSITIVO", "Por dispositivo"
        GROUP = "GRUPAL", "General de la ejecución"

    maintenance = models.ForeignKey(
        Maintenance, on_delete=models.PROTECT, related_name="task_templates"
    )
    name = models.CharField("Tarea", max_length=180)
    order = models.PositiveIntegerField("Orden")
    required = models.BooleanField("Obligatoria", default=True)
    scope = models.CharField("Ámbito", max_length=11, choices=Scope.choices)
    category = models.ForeignKey("assets.Category", null=True, blank=True, on_delete=models.PROTECT)
    is_active = models.BooleanField(default=True)

    class Meta:
        default_permissions = ()
        ordering = ["order", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["maintenance", "order"],
                condition=models.Q(is_active=True),
                name="maint_task_active_order",
            ),
            models.CheckConstraint(
                condition=~models.Q(name__regex=r"^\s*$"), name="maint_task_name_required"
            ),
            models.CheckConstraint(
                condition=models.Q(scope="DISPOSITIVO")
                | models.Q(scope="GRUPAL", category__isnull=True),
                name="maint_task_scope_category",
            ),
        ]


class ConfigurationSnapshot(RetainedModel):
    """Configuration copies stay immutable; services save explicit operational columns."""

    objects = AuditQuerySet.as_manager()
    OPERATION_FIELDS = frozenset()

    class Meta:
        abstract = True
        default_permissions = ()

    def save(self, *args, **kwargs):
        fields = kwargs.get("update_fields")
        if not self._state.adding and (not fields or not set(fields) <= self.OPERATION_FIELDS):
            raise ValidationError("La copia de la ejecución no se modifica desde la configuración.")
        return super().save(*args, **kwargs)


class MaintenanceRun(ConfigurationSnapshot):
    class State(models.TextChoices):
        PENDING = "PENDIENTE_ATENCION", "Pendiente de atención"
        ASSIGNED = "ASIGNADO", "Asignado"
        RUNNING = "EN_EJECUCION", "En ejecución"
        COMPLETED = "COMPLETADO", "Completado"
        PARTIAL = "COMPLETADO_PARCIALMENTE", "Completado parcialmente"
        CANCELLED = "CANCELADO", "Cancelado"

    maintenance = models.ForeignKey(Maintenance, on_delete=models.PROTECT, related_name="runs")
    number = models.PositiveIntegerField(default=1)
    state = models.CharField(
        max_length=32, choices=State.choices, default=State.PENDING, editable=False
    )
    configuration = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="maintenance_runs",
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    cancellation_reason = models.CharField(max_length=300, blank=True)
    notes = models.TextField(blank=True, max_length=3000, validators=[MaxLengthValidator(3000)])
    version = models.PositiveIntegerField(default=1, editable=False)
    OPERATION_FIELDS = frozenset(
        {
            "state",
            "responsible",
            "started_at",
            "completed_at",
            "cancelled_at",
            "closed_by",
            "cancellation_reason",
            "notes",
            "version",
        }
    )

    @property
    def is_open(self):
        return self.state in (self.State.PENDING, self.State.ASSIGNED, self.State.RUNNING)

    class Meta(ConfigurationSnapshot.Meta):
        ordering = ["-number"]
        permissions = [
            ("take_maintenance", "Puede tomar mantenimiento como técnico"),
            ("execute_maintenance", "Puede ejecutar su mantenimiento asignado"),
            ("override_maintenance", "Puede intervenir con motivo sobre otro responsable"),
            ("backdate_maintenance", "Puede registrar fecha real anterior con motivo"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["maintenance", "number"], name="maint_run_number_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(number=1),
                name="maint_run_first_number",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        state__in=["PENDIENTE_ATENCION", "ASIGNADO", "EN_EJECUCION"],
                        completed_at__isnull=True,
                        cancelled_at__isnull=True,
                        closed_by__isnull=True,
                        cancellation_reason="",
                    )
                    & (
                        models.Q(state="PENDIENTE_ATENCION", responsible__isnull=True)
                        | models.Q(
                            state__in=["ASIGNADO", "EN_EJECUCION"], responsible__isnull=False
                        )
                    )
                    & (~models.Q(state="EN_EJECUCION") | models.Q(started_at__isnull=False))
                )
                | models.Q(
                    state__in=["COMPLETADO", "COMPLETADO_PARCIALMENTE"],
                    responsible__isnull=False,
                    started_at__isnull=False,
                    completed_at__isnull=False,
                    cancelled_at__isnull=True,
                    closed_by__isnull=False,
                    cancellation_reason="",
                )
                | (
                    models.Q(
                        state="CANCELADO",
                        completed_at__isnull=True,
                        cancelled_at__isnull=False,
                        closed_by__isnull=False,
                    )
                    & ~models.Q(cancellation_reason__regex=r"^\s*$")
                ),
                name="maint_run_consistent_state",
            ),
            models.CheckConstraint(
                condition=models.Q(completed_at__isnull=True)
                | models.Q(completed_at__gte=models.F("started_at")),
                name="maint_run_completion_after_start",
            ),
        ]


class MaintenanceRunDevice(ConfigurationSnapshot):
    class Result(models.TextChoices):
        UNFINISHED = "SIN_FINALIZAR", "Sin finalizar"
        COMPLETED = "COMPLETADO", "Completado"
        OMITTED = "OMITIDO", "Omitido"

    run = models.ForeignKey(MaintenanceRun, on_delete=models.PROTECT, related_name="participants")
    target = models.ForeignKey(
        MaintenanceTarget, on_delete=models.PROTECT, related_name="participations"
    )
    device_name = models.CharField(max_length=120)
    category = models.ForeignKey("assets.Category", on_delete=models.PROTECT)
    category_name = models.CharField(max_length=80)
    due_date = models.DateField("Vencimiento / fecha prevista", db_index=True)
    result = models.CharField(
        max_length=20, choices=Result.choices, default=Result.UNFINISHED, editable=False
    )
    device_executed_on = models.DateField(null=True, blank=True)
    finalized_at = models.DateTimeField(null=True, blank=True)
    finalized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    completion_summary = models.CharField(max_length=300, blank=True)
    omission_reason = models.CharField(max_length=300, blank=True)
    notes = models.TextField(blank=True, max_length=3000, validators=[MaxLengthValidator(3000)])
    next_due_date = models.DateField(null=True, blank=True)
    OPERATION_FIELDS = frozenset(
        {
            "result",
            "device_executed_on",
            "finalized_at",
            "finalized_by",
            "completion_summary",
            "omission_reason",
            "notes",
            "next_due_date",
        }
    )

    class Meta(ConfigurationSnapshot.Meta):
        ordering = ["due_date", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["run", "target"], name="maint_run_target_unique"),
            models.CheckConstraint(
                condition=models.Q(
                    result="SIN_FINALIZAR",
                    device_executed_on__isnull=True,
                    finalized_at__isnull=True,
                    finalized_by__isnull=True,
                    completion_summary="",
                    omission_reason="",
                    next_due_date__isnull=True,
                )
                | (
                    models.Q(
                        result="COMPLETADO",
                        device_executed_on__isnull=False,
                        finalized_at__isnull=False,
                        finalized_by__isnull=False,
                        omission_reason="",
                    )
                    & ~models.Q(completion_summary__regex=r"^\s*$")
                )
                | (
                    models.Q(
                        result="OMITIDO",
                        device_executed_on__isnull=True,
                        finalized_at__isnull=False,
                        finalized_by__isnull=False,
                        completion_summary="",
                        next_due_date__isnull=True,
                    )
                    & ~models.Q(omission_reason__regex=r"^\s*$")
                ),
                name="maint_participant_consistent_result",
            ),
            models.CheckConstraint(
                condition=models.Q(next_due_date__isnull=True)
                | models.Q(result="COMPLETADO", next_due_date__gt=models.F("device_executed_on")),
                name="maint_next_due_after_execution",
            ),
        ]

    def clean(self):
        if self.run_id and self.target_id and self.run.maintenance_id != self.target.maintenance_id:
            raise ValidationError("El equipo inscrito no pertenece a este mantenimiento.")


class MaintenanceTaskResult(ConfigurationSnapshot):
    run = models.ForeignKey(MaintenanceRun, on_delete=models.PROTECT, related_name="tasks")
    participant = models.ForeignKey(
        MaintenanceRunDevice, on_delete=models.PROTECT, related_name="tasks", null=True, blank=True
    )
    template = models.ForeignKey(MaintenanceTaskTemplate, on_delete=models.PROTECT)
    name = models.CharField(max_length=180)
    order = models.PositiveIntegerField()
    required = models.BooleanField(default=True)
    scope = models.CharField(max_length=11, choices=MaintenanceTaskTemplate.Scope.choices)
    completed = models.BooleanField(default=False, editable=False)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    changed_at = models.DateTimeField(null=True, blank=True)
    observation = models.CharField(max_length=500, blank=True)
    OPERATION_FIELDS = frozenset({"completed", "changed_by", "changed_at", "observation"})

    class Meta(ConfigurationSnapshot.Meta):
        ordering = ["order", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["run", "participant", "template"],
                nulls_distinct=False,
                name="maint_result_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    completed=False,
                    changed_by__isnull=True,
                    changed_at__isnull=True,
                    observation="",
                )
                | models.Q(changed_by__isnull=False, changed_at__isnull=False),
                name="maint_task_change_actor",
            ),
            models.CheckConstraint(
                condition=models.Q(scope="GRUPAL", participant__isnull=True)
                | models.Q(scope="DISPOSITIVO", participant__isnull=False),
                name="maint_result_scope",
            ),
        ]

    def clean(self):
        if self.participant_id and self.participant.run_id != self.run_id:
            raise ValidationError("La tarea y el equipo deben pertenecer a la misma ejecución.")
        if (
            self.run_id
            and self.template_id
            and self.run.maintenance_id != self.template.maintenance_id
        ):
            raise ValidationError("La plantilla pertenece a otro mantenimiento.")


class MaintenanceEvent(AuditEvent):
    maintenance = models.ForeignKey(Maintenance, on_delete=models.PROTECT, related_name="events")
    run = models.ForeignKey(
        MaintenanceRun, null=True, blank=True, on_delete=models.PROTECT, related_name="events"
    )

    class Meta(AuditEvent.Meta):
        default_permissions = ()
