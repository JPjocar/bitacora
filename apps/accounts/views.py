from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import Group
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_safe
from django.views.decorators.vary import vary_on_headers

from apps.core.forms import add_validation_errors

from .forms import LoginForm, PersonalPasswordForm, ResetPasswordForm, UserForm
from .models import User
from .roles import ROLE_PERMISSIONS
from .services import change_password, reset_password, save_user


class SignInView(LoginView):
    template_name = "registration/login.html"
    authentication_form = LoginForm


class SignOutView(LogoutView):
    pass


@login_required
@require_safe
def profile(request):
    return render(request, "accounts/profile.html")


@login_required
@permission_required("accounts.view_user", raise_exception=True)
@require_safe
@vary_on_headers("HX-Request")
def user_list(request):
    query = request.GET.get("q", "").strip()[:150]
    role = request.GET.get("role", "")
    active = request.GET.get("active", "")
    users = User.objects.prefetch_related("groups")
    if query:
        users = users.filter(
            Q(username__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
        )
    if role in ROLE_PERMISSIONS:
        users = users.filter(groups__name=role)
    if active in ("true", "false"):
        users = users.filter(is_active=active == "true")
    context = {
        "page_obj": Paginator(users, 20).get_page(request.GET.get("page")),
        "q": query,
        "role": role,
        "active": active,
        "roles": ROLE_PERMISSIONS,
    }
    template = (
        "accounts/_results.html"
        if request.htmx and not request.htmx.history_restore_request
        else "accounts/list.html"
    )
    return render(request, template, context)


@login_required
@permission_required("accounts.view_user", raise_exception=True)
@require_safe
def user_detail(request, pk):
    subject = get_object_or_404(User.objects.prefetch_related("groups"), pk=pk)
    events = Paginator(subject.events.select_related("actor"), 20).get_page(request.GET.get("page"))
    return render(request, "accounts/detail.html", {"subject": subject, "events": events})


@login_required
@require_http_methods(["GET", "POST"])
def user_edit(request, pk=None):
    permission = "accounts.change_user" if pk else "accounts.add_user"
    if not request.user.has_perm(permission):
        raise PermissionDenied
    subject = get_object_or_404(User, pk=pk) if pk else None
    if subject and subject.is_superuser:
        raise PermissionDenied
    form = UserForm(request.POST if request.method == "POST" else None, instance=subject)
    if request.method == "POST" and form.is_valid():
        try:
            subject = save_user(
                actor=request.user,
                data=form.cleaned_data,
                user_id=pk,
                expected_version=form.cleaned_data.get("version"),
                password=form.cleaned_data.get("password1"),
            )
        except ValidationError as error:
            add_validation_errors(form, error)
        else:
            messages.success(request, "Usuario guardado correctamente.")
            return redirect("accounts:detail", pk=subject.pk)
    return render(request, "accounts/form.html", {"form": form, "subject": subject})


@login_required
@permission_required("auth.view_group", raise_exception=True)
@require_safe
def roles(request):
    groups = Group.objects.filter(name__in=ROLE_PERMISSIONS).prefetch_related(
        "permissions__content_type"
    )
    return render(request, "accounts/roles.html", {"groups": groups})


@login_required
@require_http_methods(["GET", "POST"])
def password_change(request):
    form = PersonalPasswordForm(request.user, request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            user = change_password(
                actor=request.user,
                old_password=form.cleaned_data["old_password"],
                password=form.cleaned_data["new_password1"],
            )
        except ValidationError as error:
            add_validation_errors(form, error)
        else:
            update_session_auth_hash(request, user)
            messages.success(request, "Contraseña actualizada.")
            return redirect("accounts:profile")
    return render(
        request, "accounts/password.html", {"form": form, "title": "Cambiar mi contraseña"}
    )


@login_required
@permission_required("accounts.change_user", raise_exception=True)
@require_http_methods(["GET", "POST"])
def password_reset(request, pk):
    subject = get_object_or_404(User, pk=pk)
    if subject.is_superuser or subject.pk == request.user.pk:
        raise PermissionDenied
    form = ResetPasswordForm(subject, request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            reset_password(
                actor=request.user, user_id=pk, password=form.cleaned_data["new_password1"]
            )
        except ValidationError as error:
            add_validation_errors(form, error)
        else:
            messages.success(
                request, "Contraseña restablecida. Las sesiones anteriores dejarán de ser válidas."
            )
            return redirect("accounts:detail", pk=pk)
    return render(
        request,
        "accounts/password.html",
        {"form": form, "title": f"Restablecer contraseña: {subject.username}"},
    )
