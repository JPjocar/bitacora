from django import forms
from django.utils import timezone

from apps.core.forms import BootstrapFormMixin


class ActionForm(BootstrapFormMixin, forms.Form):
    version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    reason = forms.CharField(
        label="Motivo", max_length=300, required=False, widget=forms.Textarea(attrs={"rows": 3})
    )

    def __init__(self, *args, run, actor, action, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial["version"] = run.version
        administrative = not (
            actor.has_perm("maintenance.execute_maintenance") and run.responsible_id == actor.pk
        )
        if action == "tomar" or (action in ("iniciar", "cerrar") and not administrative):
            self.fields.pop("reason")
        else:
            self.fields["reason"].required = administrative or action in (
                "liberar",
                "cancelar",
                "omitir",
            )
            self.fields[
                "reason"
            ].help_text = (
                "Obligatorio para intervención administrativa, rectificación o fecha anterior."
            )
        if action == "liberar":
            self.fields["reason"].label = "Trabajo realizado y motivo de liberación"
        elif action == "cancelar":
            self.fields["reason"].label = "Motivo de cancelación"
        elif action == "omitir":
            self.fields["reason"].label = "Motivo de omisión del equipo"


class CompletionForm(ActionForm):
    device_executed_on = forms.DateField(
        label="Fecha real de ejecución completa (Lima)",
        initial=timezone.localdate,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )
    completion_summary = forms.CharField(
        label="Resumen breve del trabajo y verificación",
        max_length=300,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    verified = forms.BooleanField(
        label="Confirmo que el mantenimiento del equipo está completo y verificado."
    )

    def __init__(self, *args, **kwargs):
        actor = kwargs["actor"]
        super().__init__(*args, **kwargs)
        self.fields["device_executed_on"].widget.attrs["max"] = timezone.localdate().isoformat()
        if not actor.has_perm("maintenance.backdate_maintenance"):
            self.fields["device_executed_on"].disabled = True
            self.fields[
                "device_executed_on"
            ].help_text = (
                "Se registra hoy. Una fecha anterior requiere intervención administrativa."
            )


class ProgressForm(ActionForm):
    notes = forms.CharField(
        label="Notas técnicas",
        required=False,
        max_length=3000,
        widget=forms.Textarea(attrs={"rows": 4}),
    )

    def __init__(self, *args, tasks, notes, **kwargs):
        super().__init__(*args, **kwargs)
        self.tasks = list(tasks)
        self.initial["notes"] = notes
        self.rows = []
        for task in self.tasks:
            check, observation = f"task_{task.pk}", f"observation_{task.pk}"
            self.fields[check] = forms.BooleanField(
                label=task.name,
                required=False,
                initial=task.completed,
                widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
            )
            self.fields[observation] = forms.CharField(
                label=f"Observación de {task.name}",
                max_length=500,
                required=False,
                initial=task.observation,
                widget=forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
            )
            self.rows.append({"check": self[check], "observation": self[observation], "task": task})

    def clean(self):
        data = super().clean()
        if any(
            (key.startswith("task_") or key.startswith("observation_")) and key not in self.fields
            for key in self.data
        ):
            raise forms.ValidationError("El formulario contiene tareas ajenas a esta operación.")
        if any(
            task.completed and not data.get(f"task_{task.pk}") for task in self.tasks
        ) and not data.get("reason"):
            self.add_error("reason", "Explique la rectificación de una tarea ya marcada.")
        return data

    def task_data(self):
        return {
            task.pk: {
                "completed": self.cleaned_data[f"task_{task.pk}"],
                "observation": self.cleaned_data[f"observation_{task.pk}"],
            }
            for task in self.tasks
        }
