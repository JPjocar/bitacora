from django.urls import path

from . import views

app_name = "dashboard"
urlpatterns = [
    path("", views.panel, name="panel"),
    path("exportar/", views.report, {"output": "csv"}, name="csv"),
    path("imprimir/", views.report, {"output": "print"}, name="print"),
]
