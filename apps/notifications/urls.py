from django.urls import path

from . import views

app_name = "notifications"
urlpatterns = [
    path("", views.inbox, name="inbox"),
    path("contador/", views.counter, name="counter"),
    path("leer-todas/", views.read_all, name="read_all"),
    path("<int:pk>/abrir/", views.read_notice, name="read"),
]
