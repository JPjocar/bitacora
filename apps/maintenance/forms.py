import uuid

from django import forms
from django.forms import formset_factory
from django.utils import timezone

from apps.assets.models import Category, Device
from apps.core.forms import BootstrapFormMixin

from .models import Maintenance, MaintenanceTaskTemplate
from .selectors import eligible_devices
from .services import MAX_TARGETS, MAX_TASKS
from .widgets import DeviceGridWidget


class DeviceSelection(forms.ModelMultipleChoiceField):
    def clean(self, value):
        if value and len(value) > MAX_TARGETS:
            raise forms.ValidationError(f"Seleccione como máximo {MAX_TARGETS} equipos.")
        return super().clean(value)


class MaintenanceForm(BootstrapFormMixin, forms.Form):
    kind = forms.ChoiceField(
        choices=[("unique", "Único"), ("recurring", "Periódico")], widget=forms.HiddenInput
    )
    name = forms.CharField(label="Nombre", max_length=120)
    description = forms.CharField(
        label="Descripción",
        max_length=3000,
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    planned_date = forms.DateField(
        label="Fecha prevista",
        initial=timezone.localdate,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )
    base_date = forms.DateField(
        label="Fecha base",
        initial=timezone.localdate,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
        help_text="No indica trabajo realizado. Primer vencimiento: fecha base más intervalo.",
    )
    interval_value = forms.IntegerField(
        label="Cada cuántos días o meses", min_value=1, max_value=2147483647
    )
    interval_unit = forms.ChoiceField(label="Unidad", choices=Maintenance.Unit.choices)
    devices = DeviceSelection(
        label="Equipos inscritos",
        queryset=Device.objects.none(),
        widget=DeviceGridWidget,
        help_text="Agrega equipos con el botón +. Se guardan al confirmar el mantenimiento.",
    )
    is_active = forms.BooleanField(
        label="Mantenimiento activo",
        required=False,
        initial=True,
        help_text="Desactivar conserva la ejecución y su historial; no equivale a cancelarla.",
    )
    creation_key = forms.UUIDField(initial=uuid.uuid4, widget=forms.HiddenInput)
    version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    reason = forms.CharField(label="Motivo del cambio", max_length=300)

    def __init__(self, *args, maintenance=None, kind="unique", actor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.maintenance = maintenance
        mode = (
            ("recurring" if maintenance.is_recurring else "unique")
            if maintenance
            else (self.data.get("kind", kind) if self.is_bound else kind)
        )
        self.initial["kind"] = mode
        if mode == "recurring":
            self.fields.pop("planned_date")
        else:
            for field in ("base_date", "interval_value", "interval_unit"):
                self.fields.pop(field)
        if maintenance:
            current_ids = list(
                maintenance.targets.filter(is_active=True).values_list("device_id", flat=True)
            )
            for field in self.fields:
                if hasattr(maintenance, field):
                    self.initial[field] = getattr(maintenance, field)
            self.initial["devices"] = current_ids
            self.fields.pop("creation_key")
            if not maintenance.is_recurring:
                self.fields["planned_date"].disabled = True
        else:
            for field in ("version", "reason", "is_active"):
                self.fields.pop(field)
        self.fields["devices"].queryset = eligible_devices(maintenance, actor=actor)
        self.fields["devices"].widget.attrs.pop("class", None)

    def clean_kind(self):
        value = self.cleaned_data["kind"]
        if self.maintenance and (value == "recurring") != self.maintenance.is_recurring:
            raise forms.ValidationError("No se puede cambiar el tipo de mantenimiento.")
        return value

    def service_data(self):
        recurring = self.cleaned_data["kind"] == "recurring"
        return {
            "name": self.cleaned_data["name"],
            "description": self.cleaned_data["description"],
            "is_recurring": recurring,
            "is_active": self.cleaned_data.get("is_active", True),
            "base_date": self.cleaned_data.get("base_date") if recurring else None,
            "interval_value": self.cleaned_data.get("interval_value") if recurring else None,
            "interval_unit": self.cleaned_data.get("interval_unit", "") if recurring else "",
            "planned_date": None if recurring else self.cleaned_data.get("planned_date"),
        }


class TaskForm(BootstrapFormMixin, forms.Form):
    name = forms.CharField(label="Tarea verificable", max_length=180)
    scope = forms.ChoiceField(
        label="Ámbito", choices=MaintenanceTaskTemplate.Scope.choices, initial="DISPOSITIVO"
    )
    category = forms.ModelChoiceField(
        label="Solo para categoría",
        queryset=Category.objects.all(),
        required=False,
        empty_label="Todos los equipos",
        help_text="Solo para tareas por dispositivo. Debe corresponder a un equipo seleccionado.",
    )
    required = forms.BooleanField(label="Obligatoria", initial=True, required=False)


TaskFormSet = formset_factory(
    TaskForm,
    extra=1,
    min_num=1,
    validate_min=True,
    max_num=MAX_TASKS,
    validate_max=True,
    absolute_max=MAX_TASKS + 1,
    can_order=True,
    can_delete=True,
)
