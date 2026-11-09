"""Read-only, permission-scoped HTML picker. Selecting does not save a maintenance."""

from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_safe

from apps.assets.qr import resolve_scan
from apps.locations.models import Location

from .models import Maintenance
from .selectors import eligible_devices
from .services import MAX_TARGETS


class DeviceSearchForm(forms.Form):
    q = forms.CharField(max_length=120, required=False)
    location = forms.ModelChoiceField(queryset=Location.objects.all(), required=False)
    query = forms.CharField(max_length=2048, required=False)


@login_required
@require_safe
def device_picker(request, pk=None):
    permission = "maintenance.change_maintenance" if pk else "maintenance.add_maintenance"
    if not request.user.has_perm(permission):
        raise PermissionDenied
    maintenance = get_object_or_404(Maintenance, pk=pk) if pk else None
    devices = eligible_devices(maintenance, actor=request.user)
    form = DeviceSearchForm(request.GET)
    mode = request.GET.get("mode", "search")
    context = {"picker_error": "", "auto_add": mode in {"scan", "all"}}
    if not form.is_valid():
        context["picker_error"] = "Revisa la búsqueda: texto demasiado largo o ubicación inválida."
        devices = devices.none()
    elif mode == "scan":
        try:
            device = resolve_scan(actor=request.user, value=form.cleaned_data["query"])
            device = devices.get(pk=device.pk)
        except (ValidationError, devices.model.DoesNotExist):
            context["picker_error"] = (
                "Código no reconocido o equipo no disponible para este mantenimiento."
            )
        else:
            context["devices"] = [device]
    else:
        query = form.cleaned_data["q"].strip()
        if query:
            devices = devices.filter(
                Q(name__icontains=query)
                | Q(code__icontains=query)
                | Q(location__name__icontains=query)
            )
        if form.cleaned_data["location"]:
            devices = devices.filter(location=form.cleaned_data["location"])
        if mode == "all":
            matches = list(devices.order_by("name", "pk")[: MAX_TARGETS + 1])
            if len(matches) > MAX_TARGETS:
                context["picker_error"] = (
                    f"El filtro supera {MAX_TARGETS} equipos. "
                    "Acota la búsqueda antes de agregar todos."
                )
            else:
                context["devices"] = matches
    if context["auto_add"]:
        return render(request, "maintenance/picker_selection.html", context)
    context["page_obj"] = Paginator(devices.order_by("name", "pk"), 20).get_page(
        request.GET.get("page")
    )
    return render(request, "maintenance/picker_results.html", context)
