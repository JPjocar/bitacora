from django import forms

from apps.core.forms import BootstrapFormMixin


class NextRunForm(BootstrapFormMixin, forms.Form):
    version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    previous_run_id = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    targets = forms.MultipleChoiceField(
        label="Equipos de la siguiente ejecución", widget=forms.CheckboxSelectMultiple
    )
    reason = forms.CharField(
        label="Motivo de inclusión anticipada (si corresponde)",
        max_length=300,
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Obligatorio si incluye equipos cuyo vencimiento está a más de 7 días.",
    )

    def __init__(self, *args, maintenance, previous_run, schedules, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial["version"] = maintenance.version
        self.initial["previous_run_id"] = previous_run.pk if previous_run else None
        self.fields["targets"].choices = [
            (
                str(row.target.pk),
                f"{row.target.device.code} · {row.target.device.name} · "
                f"{row.due_date:%d/%m/%Y} · {row.timing_label}",
            )
            for row in schedules
            if row.selectable
        ]
        self.initial["targets"] = [str(row.target.pk) for row in schedules if row.proposed]
        self.fields["targets"].widget.attrs.pop("class", None)
