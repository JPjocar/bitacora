from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, SetPasswordForm

from apps.core.forms import BootstrapFormMixin

from .models import User
from .roles import ROLE_PERMISSIONS


class LoginForm(BootstrapFormMixin, AuthenticationForm):
    pass


class PersonalPasswordForm(BootstrapFormMixin, PasswordChangeForm):
    pass


class ResetPasswordForm(BootstrapFormMixin, SetPasswordForm):
    pass


class UserForm(BootstrapFormMixin, forms.ModelForm):
    role = forms.ChoiceField(label="Rol", choices=[(name, name) for name in ROLE_PERMISSIONS])
    version = forms.IntegerField(widget=forms.HiddenInput, required=False, min_value=1)
    password1 = forms.CharField(
        label="Contraseña inicial",
        widget=forms.PasswordInput,
        required=False,
        help_text="Al menos 12 caracteres; evite datos personales o contraseñas comunes.",
    )
    password2 = forms.CharField(
        label="Confirmar contraseña", widget=forms.PasswordInput, required=False
    )

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "role", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields.pop("password1")
            self.fields.pop("password2")
            self.fields["version"].required = True
            self.initial["version"] = self.instance.version
            role = self.instance.business_role
            self.initial["role"] = role.name if role else ""
        else:
            self.fields["password1"].required = True
            self.fields["password2"].required = True

    def clean(self):
        data = super().clean()
        if not self.instance.pk and data.get("password1") != data.get("password2"):
            self.add_error("password2", "Las contraseñas no coinciden.")
        return data
