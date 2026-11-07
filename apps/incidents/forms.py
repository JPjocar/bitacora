from uuid import uuid4

from django import forms

from apps.assets.models import Category
from apps.core.forms import BootstrapFormMixin
from apps.locations.models import Location

from .models import Incident


class ReportForm(BootstrapFormMixin, forms.Form):
    creation_key = forms.UUIDField(widget=forms.HiddenInput, initial=uuid4)
    symptoms = forms.CharField(
        label="Síntomas observados",
        max_length=3000,
        widget=forms.Textarea(attrs={"rows": 5}),
        help_text="Describa qué ocurre y desde cuándo. No incluya contraseñas ni datos personales.",
    )


class IncidentFilters(BootstrapFormMixin, forms.Form):
    q = forms.CharField(label="Código, equipo o síntomas", max_length=120, required=False)
    state = forms.ChoiceField(
        label="Estado", choices=[("", "Todos")] + list(Incident.State.choices), required=False
    )
    outcome = forms.ChoiceField(
        label="Resultado de cierre",
        choices=[("", "Todos")] + list(Incident.Outcome.choices),
        required=False,
    )
    location = forms.ModelChoiceField(
        label="Ubicación actual", queryset=Location.objects.all(), required=False
    )
    kind = forms.ChoiceField(
        label="Tipo de equipo",
        choices=[("", "Todos")] + list(Category.Kind.choices),
        required=False,
    )
    start = forms.DateField(
        label="Reportado desde", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    end = forms.DateField(
        label="Reportado hasta", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )

    def __init__(self, *args, visible_reports=None, **kwargs):
        super().__init__(*args, **kwargs)
        if visible_reports is not None:
            self.fields["location"].queryset = Location.objects.filter(
                pk__in=visible_reports.order_by().values("device__location_id")
            )

    def clean(self):
        data = super().clean()
        if data.get("start") and data.get("end") and data["start"] > data["end"]:
            self.add_error("end", "La fecha final no puede ser anterior a la inicial.")
        return data


class ActionForm(BootstrapFormMixin, forms.Form):
    version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)

    def __init__(self, *args, incident, action, actor, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial["version"] = incident.version
        admin_reason = not (
            actor.has_perm("incidents.attend_incident") and incident.responsible_id == actor.pk
        )
        if action == "nota":
            self.fields["note"] = forms.CharField(
                label="Nota técnica",
                max_length=3000,
                widget=forms.Textarea(attrs={"rows": 5, "class": "form-control"}),
                help_text="Registro interno visible para técnicos y administradores.",
            )
        if action in {"liberar", "cerrar"}:
            self.fields["summary"] = forms.CharField(
                label="Resumen de lo realizado y pendiente"
                if action == "liberar"
                else "Resumen del cierre para el reportante",
                max_length=1000 if action == "liberar" else 3000,
                widget=forms.Textarea(attrs={"rows": 5, "class": "form-control"}),
                help_text=(
                    "No incluya secretos ni datos personales. "
                    "El resumen de cierre será visible para quien reportó."
                ),
            )
        if action == "cerrar":
            choices = list(Incident.Outcome.choices)
            if not actor.has_perm("incidents.close_unrepairable_incident"):
                choices = [
                    choice for choice in choices if choice[0] != Incident.Outcome.UNREPAIRABLE
                ]
            if incident.state == Incident.State.PENDING:
                choices = [choice for choice in choices if choice[0] == Incident.Outcome.INVALID]
            self.fields["outcome"] = forms.ChoiceField(
                label="Resultado",
                choices=[("", "Seleccione")] + choices,
                widget=forms.Select(attrs={"class": "form-select"}),
            )
        if action != "tomar":
            self.fields["reason"] = forms.CharField(
                label="Motivo / justificación",
                max_length=300,
                required=action == "liberar" or admin_reason,
                widget=forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
                help_text=(
                    "Obligatorio al liberar, intervenir administrativamente "
                    "o declarar no reparable."
                ),
            )
