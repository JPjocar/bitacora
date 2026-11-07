from django.contrib import admin
from django.urls import include, path

from apps.core.views import home

urlpatterns = [
    path("", home, name="home"),
    path("cuentas/", include("apps.accounts.urls")),
    path("ubicaciones/", include("apps.locations.urls")),
    path("dispositivos/", include("apps.assets.urls")),
    path("mantenimientos/", include("apps.maintenance.urls")),
    path("avisos/", include("apps.notifications.urls")),
    path("panel/", include("apps.dashboard.urls")),
    path("incidencias/", include("apps.incidents.urls")),
    path("admin/", admin.site.urls),
]
handler403 = "apps.core.views.forbidden"
handler404 = "apps.core.views.not_found"
handler500 = "apps.core.views.server_error"
