from django import forms

from apps.assets.models import Category, Device
from apps.core.forms import BootstrapFormMixin
from apps.locations.models import Location
from apps.maintenance.models import MaintenanceRun

SECTIONS = [
    ("deadlines", "Vencimientos"),
    ("runs", "Ejecuciones"),
    ("unconfigured", "Sin preventivo periódico"),
    ("omissions", "Omisiones pendientes"),
    ("devices", "Inventario"),
]


class DashboardFilters(BootstrapFormMixin, forms.Form):
    q = forms.CharField(label="Código o nombre de equipo", max_length=120, required=False)
    location = forms.ModelChoiceField(
        label="Ubicación", queryset=Location.objects.all(), required=False
    )
    kind = forms.ChoiceField(
        label="Tipo", choices=[("", "Todos")] + list(Category.Kind.choices), required=False
    )
    status = forms.ChoiceField(
        label="Estado del equipo",
        choices=[("", "Todos")] + list(Device.Status.choices),
        required=False,
    )
    active = forms.ChoiceField(
        label="Registro",
        choices=[("", "Todos"), ("yes", "Activos"), ("no", "Archivados")],
        required=False,
    )
    run_state = forms.ChoiceField(
        label="Estado de ejecución",
        choices=[("", "Todos")] + list(MaintenanceRun.State.choices),
        required=False,
    )
    start = forms.DateField(
        label="Desde", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    end = forms.DateField(
        label="Hasta", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    section = forms.ChoiceField(label="Tabla / reporte", choices=SECTIONS, required=False)

    def clean(self):
        data = super().clean()
        if data.get("start") and data.get("end") and data["start"] > data["end"]:
            self.add_error("end", "La fecha final debe ser igual o posterior a la inicial.")
        data["section"] = data.get("section") or "deadlines"
        return data
