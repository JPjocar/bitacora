from django import forms
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_safe

from apps.core.forms import BootstrapFormMixin

from .qr import device_qr_png, label_sheets, resolve_scan
from .selectors import visible_devices


class ScanForm(BootstrapFormMixin, forms.Form):
    query = forms.CharField(
        label="Código del equipo o contenido del QR",
        max_length=2048,
        widget=forms.TextInput(attrs={"placeholder": "EQ-XXXXXXXX", "autocomplete": "off"}),
    )


@login_required
@require_safe
def qr_png(request, public_id):
    device = get_object_or_404(visible_devices(request.user), public_id=public_id)
    response = HttpResponse(device_qr_png(device), content_type="image/png")
    response["Content-Disposition"] = f'inline; filename="{device.code}.png"'
    return response


@login_required
@permission_required("assets.print_device_label", raise_exception=True)
@require_http_methods(["GET", "POST"])
def labels(request):
    selection = request.POST if request.method == "POST" else request.GET
    try:
        sheets = label_sheets(actor=request.user, identifiers=selection.getlist("device"))
    except ValidationError as error:
        return render(request, "assets/labels.html", {"errors": error.messages}, status=400)
    return render(request, "assets/labels.html", {"sheets": sheets})


@login_required
@require_http_methods(["GET", "POST"])
def scanner(request):
    visible_devices(request.user)  # Enforce access even before displaying the form.
    form = ScanForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            device = resolve_scan(actor=request.user, value=form.cleaned_data["query"])
        except ValidationError as error:
            form.add_error("query", error)
        else:
            return redirect("assets:detail", public_id=device.public_id)
    return render(request, "assets/scanner.html", {"form": form})
