from django.urls import path

from . import views

app_name = "incidents"
urlpatterns = [
    path("", views.incident_list, name="list"),
    path("reportar/<uuid:public_id>/", views.report, name="report"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/<str:action>/", views.action, name="action"),
]
