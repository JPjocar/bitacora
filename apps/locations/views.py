from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_safe
from django.views.decorators.vary import vary_on_headers

from apps.core.forms import add_validation_errors

from .forms import LocationForm
from .models import Location
from .services import save_location


@login_required
@permission_required("locations.view_location", raise_exception=True)
@require_safe
@vary_on_headers("HX-Request")
def location_list(request):
    query = request.GET.get("q", "").strip()[:120]
    kind = request.GET.get("kind", "")
    active = request.GET.get("active", "")
    locations = Location.objects.all()
    if query:
        locations = locations.filter(Q(name__icontains=query) | Q(code__icontains=query))
    if kind in Location.Kind.values:
        locations = locations.filter(kind=kind)
    if active in ("true", "false"):
        locations = locations.filter(is_active=active == "true")
    context = {
        "page_obj": Paginator(locations, 20).get_page(request.GET.get("page")),
        "q": query,
        "kind": kind,
        "active": active,
        "kinds": Location.Kind.choices,
    }
    template = (
        "locations/_results.html"
        if request.htmx and not request.htmx.history_restore_request
        else "locations/list.html"
    )
    return render(request, template, context)


@login_required
@permission_required("locations.view_location", raise_exception=True)
@require_safe
def location_detail(request, pk):
    location = get_object_or_404(Location, pk=pk)
    events = None
    if request.user.has_perm("locations.change_location"):
        events = Paginator(location.events.select_related("actor"), 20).get_page(
            request.GET.get("page")
        )
    return render(request, "locations/detail.html", {"location": location, "events": events})


@login_required
@require_http_methods(["GET", "POST"])
def location_edit(request, pk=None):
    if not request.user.has_perm("locations.change_location" if pk else "locations.add_location"):
        raise PermissionDenied
    location = get_object_or_404(Location, pk=pk) if pk else None
    form = LocationForm(request.POST if request.method == "POST" else None, instance=location)
    if request.method == "POST" and form.is_valid():
        try:
            location = save_location(
                actor=request.user,
                data=form.cleaned_data,
                location_id=pk,
                expected_version=form.cleaned_data.get("version"),
            )
        except ValidationError as error:
            add_validation_errors(form, error)
        else:
            messages.success(request, "Ubicación guardada correctamente.")
            return redirect("locations:detail", pk=location.pk)
    return render(request, "locations/form.html", {"form": form, "location": location})
