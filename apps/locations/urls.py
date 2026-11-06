from django.urls import path

from . import views

app_name = "locations"
urlpatterns = [
    path("", views.location_list, name="list"),
    path("nueva/", views.location_edit, name="create"),
    path("<int:pk>/", views.location_detail, name="detail"),
    path("<int:pk>/editar/", views.location_edit, name="edit"),
]
