from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.http import require_safe


@login_required
@require_safe
def home(request):
    return render(request, "home.html")


def forbidden(request, exception):
    return render(request, "403.html", status=403)


def not_found(request, exception):
    return render(request, "404.html", status=404)


def server_error(request):
    return render(request, "500.html", status=500)
