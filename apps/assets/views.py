from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_safe
from django.views.decorators.vary import vary_on_headers

from apps.core.forms import add_validation_errors
from apps.locations.models import Location

from .forms import CategoryForm, DeviceForm, DeviceOperationForm, MovementFilterForm, MovementForm
from .models import Category, Device, Movement
from .selectors import visible_devices
from .services import move_device, save_category, save_device


@login_required
@require_safe
@vary_on_headers("HX-Request")
def device_list(request):
    devices = visible_devices(request.user)
    categories = Category.objects.all()
    locations = Location.objects.all()
    if not request.user.has_perm("assets.view_device"):
        categories = categories.filter(pk__in=devices.values("category_id"))
        locations = locations.filter(pk__in=devices.values("location_id"))
    query = request.GET.get("q", "").strip()[:120]
    category = request.GET.get("category", "")
    location = request.GET.get("location", "")
    status = request.GET.get("status", "")
    active = request.GET.get("active", "")
    if query:
        devices = devices.filter(Q(code__icontains=query) | Q(name__icontains=query))
    if category.isdecimal() and len(category) < 19:
        devices = devices.filter(category_id=category)
    if location.isdecimal() and len(location) < 19:
        devices = devices.filter(location_id=location)
    if status in Device.Status.values:
        devices = devices.filter(status=status)
    if active in ("true", "false") and request.user.has_perm("assets.view_device"):
        devices = devices.filter(is_active=active == "true")
    context = {
        "page_obj": Paginator(devices, 20).get_page(request.GET.get("page")),
        "q": query,
        "category": category,
        "location": location,
        "status": status,
        "active": active,
        "categories": categories,
        "locations": locations,
        "statuses": Device.Status.choices,
    }
    template = (
        "assets/_devices.html"
        if request.htmx and not request.htmx.history_restore_request
        else "assets/devices.html"
    )
    return render(request, template, context)


@login_required
@require_safe
def device_detail(request, public_id):
    device = get_object_or_404(visible_devices(request.user), public_id=public_id)
    events = None
    if request.user.has_perm("assets.view_device"):
        events = Paginator(device.events.select_related("actor"), 20).get_page(
            request.GET.get("page")
        )
    return render(request, "assets/device_detail.html", {"device": device, "events": events})


@login_required
@require_http_methods(["GET", "POST"])
def device_edit(request, public_id=None, operation=False):
    permission = (
        "assets.update_device_operation"
        if operation
        else ("assets.change_device" if public_id else "assets.add_device")
    )
    if not request.user.has_perm(permission):
        raise PermissionDenied
    device = (
        get_object_or_404(visible_devices(request.user), public_id=public_id) if public_id else None
    )
    form_type = DeviceOperationForm if operation else DeviceForm
    form = form_type(request.POST if request.method == "POST" else None, instance=device)
    if request.method == "POST" and form.is_valid():
        try:
            device = save_device(
                actor=request.user,
                device_id=device.pk if device else None,
                data=form.service_data(),
                expected_version=form.cleaned_data.get("version"),
                reason=form.cleaned_data.get("reason", ""),
            )
        except ValidationError as error:
            add_validation_errors(form, error)
        else:
            messages.success(request, "Dispositivo guardado correctamente.")
            return redirect("assets:detail", public_id=device.public_id)
    return render(
        request, "assets/device_form.html", {"form": form, "device": device, "operation": operation}
    )


@login_required
@permission_required("assets.add_movement", raise_exception=True)
@require_http_methods(["GET", "POST"])
def movement_create(request, public_id):
    device = get_object_or_404(visible_devices(request.user), public_id=public_id)
    form = MovementForm(request.POST if request.method == "POST" else None, device=device)
    if request.method == "POST" and form.is_valid():
        try:
            movement = move_device(
                actor=request.user,
                device_id=device.pk,
                destination_id=form.cleaned_data["destination"].pk,
                expected_version=form.cleaned_data["version"],
                reason=form.cleaned_data["reason"],
                notes=form.cleaned_data["notes"],
                effective_at=form.cleaned_data["effective_at"],
                confirm_warning=form.cleaned_data.get("confirm_warning", False),
            )
        except ValidationError as error:
            add_validation_errors(form, error)
        else:
            messages.success(request, "Traslado registrado. La ubicación actual fue actualizada.")
            return redirect("assets:movement_detail", pk=movement.pk)
    return render(request, "assets/movement_form.html", {"form": form, "device": device})


@login_required
@permission_required("assets.view_movement", raise_exception=True)
@require_safe
@vary_on_headers("HX-Request")
def movement_list(request):
    form = MovementFilterForm(request.GET)
    movements = Movement.objects.select_related("device", "origin", "destination", "actor")
    if form.is_valid():
        filters = form.cleaned_data
        if filters["q"]:
            movements = movements.filter(
                Q(device__code__icontains=filters["q"]) | Q(device__name__icontains=filters["q"])
            )
        if filters["location"]:
            movements = movements.filter(
                Q(origin=filters["location"]) | Q(destination=filters["location"])
            )
        if filters["start"]:
            movements = movements.filter(effective_at__date__gte=filters["start"])
        if filters["end"]:
            movements = movements.filter(effective_at__date__lte=filters["end"])
    else:
        movements = movements.none()
    context = {"form": form, "page_obj": Paginator(movements, 20).get_page(request.GET.get("page"))}
    # Include filter errors in the swapped fragment; keep ordinary GET usable.
    template = (
        "assets/_movements.html"
        if request.htmx and not request.htmx.history_restore_request
        else "assets/movements.html"
    )
    return render(request, template, context)


@login_required
@permission_required("assets.view_movement", raise_exception=True)
@require_safe
def movement_detail(request, pk):
    movement = get_object_or_404(
        Movement.objects.select_related("device", "origin", "destination", "actor"), pk=pk
    )
    return render(request, "assets/movement_detail.html", {"movement": movement})


@login_required
@permission_required("assets.view_category", raise_exception=True)
@require_safe
def category_list(request):
    query = request.GET.get("q", "").strip()[:80]
    categories = Category.objects.filter(name__icontains=query)
    return render(
        request,
        "assets/categories.html",
        {"q": query, "page_obj": Paginator(categories, 20).get_page(request.GET.get("page"))},
    )


@login_required
@permission_required("assets.view_category", raise_exception=True)
@require_safe
def category_detail(request, pk):
    category = get_object_or_404(Category, pk=pk)
    events = None
    if request.user.has_perm("assets.change_category"):
        events = Paginator(category.events.select_related("actor"), 20).get_page(
            request.GET.get("page")
        )
    return render(request, "assets/category_detail.html", {"category": category, "events": events})


@login_required
@require_http_methods(["GET", "POST"])
def category_edit(request, pk=None):
    if not request.user.has_perm("assets.change_category" if pk else "assets.add_category"):
        raise PermissionDenied
    category = get_object_or_404(Category, pk=pk) if pk else None
    form = CategoryForm(request.POST if request.method == "POST" else None, instance=category)
    if request.method == "POST" and form.is_valid():
        try:
            category = save_category(
                actor=request.user,
                data=form.cleaned_data,
                category_id=pk,
                expected_version=form.cleaned_data.get("version"),
            )
        except ValidationError as error:
            add_validation_errors(form, error)
        else:
            messages.success(request, "Categoría guardada correctamente.")
            return redirect("assets:category_detail", pk=category.pk)
    return render(request, "assets/category_form.html", {"form": form, "category": category})
