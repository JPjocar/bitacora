from django import forms
from django.template.loader import render_to_string

from .services import MAX_TARGETS


class DeviceGridWidget(forms.SelectMultiple):
    template_name = "maintenance/widgets/device_grid.html"

    def render(self, name, value, attrs=None, renderer=None):
        # Use the project template engine, including shared, escaped UI components.
        return render_to_string(self.template_name, self.get_context(name, value, attrs))

    def use_required_attribute(self, initial):
        return False  # Selection is validated by the field and transactional service.

    def optgroups(self, name, value, attrs=None):
        return []  # Never enumerate the complete device queryset to render a form.

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        identifiers = []
        for raw in (value or [])[:MAX_TARGETS]:
            text = str(raw)
            if len(text) <= 19 and text.isascii() and text.isdecimal() and 0 < int(text) < 2**63:
                identifier = int(text)
                if identifier not in identifiers:
                    identifiers.append(identifier)
        devices = {item.pk: item for item in self.choices.queryset.filter(pk__in=identifiers)}
        context["widget"]["devices"] = [devices[pk] for pk in identifiers if pk in devices]
        context["widget"]["limit"] = MAX_TARGETS
        return context
