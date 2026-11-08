from django import forms
from django.db.models import Q
from django.utils import timezone

from apps.core.forms import BootstrapFormMixin
from apps.locations.models import Location

from .models import Category, Device
from .selectors import movement_warning


class CategoryForm(BootstrapFormMixin, forms.ModelForm):
    version = forms.IntegerField(widget=forms.HiddenInput, required=False, min_value=1)

    class Meta:
        model = Category
        fields = ["name", "kind", "description", "is_active"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["version"].required = True
            self.initial["version"] = self.instance.version


class DeviceForm(BootstrapFormMixin, forms.ModelForm):
    version = forms.IntegerField(widget=forms.HiddenInput, required=False, min_value=1)
    reason = forms.CharField(
        label="Motivo del cambio de estado",
        max_length=300,
        required=False,
        help_text="Obligatorio cuando cambia el estado operativo de un equipo existente.",
    )

    class Meta:
        model = Device
        fields = [
            "name",
            "category",
            "brand",
            "model",
            "serial_number",
            "location",
            "status",
            "observations",
            "technical_details",
            "acquired_on",
            "is_active",
        ]
        widgets = {
            "observations": forms.Textarea(attrs={"rows": 3}),
            "technical_details": forms.Textarea(attrs={"rows": 4}),
            "acquired_on": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
        }
        help_texts = {
            "serial_number": "Opcional; no identifica por sí sola el equipo.",
            "is_active": "Desmarque para archivar sin eliminar el equipo ni su historial.",
            "technical_details": (
                "Datos opcionales relevantes a su categoría. "
                "No incluya contraseñas ni claves de acceso."
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.objects.filter(
            Q(is_active=True) | Q(pk=self.instance.category_id)
        )
        if self.instance.pk:
            self.fields.pop("location")
            self.fields["version"].required = True
            self.initial["version"] = self.instance.version
            self.fields["technical_details"].help_text = self.instance.category.technical_help
        else:
            self.fields["location"].queryset = Location.objects.filter(is_active=True)
            self.fields.pop("reason")

    def service_data(self):
        return {
            field + "_id" if field in ("category", "location") else field: value.pk
            if field in ("category", "location")
            else value
            for field, value in self.cleaned_data.items()
            if field not in ("version", "reason")
        }


class DeviceOperationForm(BootstrapFormMixin, forms.ModelForm):
    version = forms.IntegerField(widget=forms.HiddenInput, min_value=1)
    reason = forms.CharField(label="Motivo del cambio de estado", max_length=300, required=False)

    class Meta:
        model = Device
        fields = ["status", "observations"]
        widgets = {"observations": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial["version"] = self.instance.version

    def service_data(self):
        return {field: self.cleaned_data[field] for field in ("status", "observations")}


class MovementForm(BootstrapFormMixin, forms.Form):
    destination = forms.ModelChoiceField(
        label="Ubicación de destino", queryset=Location.objects.none()
    )
    reason = forms.CharField(label="Motivo", max_length=300)
    notes = forms.CharField(
        label="Observaciones",
        required=False,
        max_length=2000,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    effective_at = forms.DateTimeField(
        label="Fecha y hora efectiva (Lima)",
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}),
    )
    version = forms.IntegerField(widget=forms.HiddenInput, min_value=1)
    confirm_warning = forms.BooleanField(
        label="He leído la advertencia y confirmo el traslado físico.", required=False
    )

    def __init__(self, *args, device, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["destination"].queryset = Location.objects.filter(is_active=True).exclude(
            pk=device.location_id
        )
        self.initial["version"] = device.version
        self.initial["effective_at"] = timezone.localtime().replace(second=0, microsecond=0)
        self.movement_warning = movement_warning(device)
        if not self.movement_warning:
            self.fields.pop("confirm_warning")


class MovementFilterForm(BootstrapFormMixin, forms.Form):
    q = forms.CharField(label="Nombre o código del dispositivo", max_length=120, required=False)
    location = forms.ModelChoiceField(
        label="Origen o destino", queryset=Location.objects.all(), required=False
    )
    start = forms.DateField(
        label="Desde", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    end = forms.DateField(
        label="Hasta", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )

    def clean(self):
        data = super().clean()
        if data.get("start") and data.get("end") and data["start"] > data["end"]:
            raise forms.ValidationError("La fecha inicial no puede ser posterior a la final.")
        return data
