from django import forms

from apps.core.forms import BootstrapFormMixin

from .models import Location


class LocationForm(BootstrapFormMixin, forms.ModelForm):
    version = forms.IntegerField(widget=forms.HiddenInput, required=False, min_value=1)

    class Meta:
        model = Location
        fields = ["name", "code", "kind", "description", "is_active"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}
        help_texts = {
            "code": "Opcional. Debe ser único cuando se indique.",
            "is_active": "Desactive el ambiente para conservar su historial sin eliminarlo.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["version"].required = True
            self.initial["version"] = self.instance.version
