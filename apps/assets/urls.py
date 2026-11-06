from django.urls import path

from . import qr_views, views

app_name = "assets"
urlpatterns = [
    path("", views.device_list, name="list"),
    path("escaner/", qr_views.scanner, name="scanner"),
    path("etiquetas/", qr_views.labels, name="labels"),
    path("<uuid:public_id>/qr.png", qr_views.qr_png, name="qr_png"),
    path("nuevo/", views.device_edit, name="create"),
    path("categorias/", views.category_list, name="categories"),
    path("categorias/nueva/", views.category_edit, name="category_create"),
    path("categorias/<int:pk>/", views.category_detail, name="category_detail"),
    path("categorias/<int:pk>/editar/", views.category_edit, name="category_edit"),
    path("movimientos/", views.movement_list, name="movements"),
    path("movimientos/<int:pk>/", views.movement_detail, name="movement_detail"),
    path("<uuid:public_id>/", views.device_detail, name="detail"),
    path("<uuid:public_id>/editar/", views.device_edit, name="edit"),
    path("<uuid:public_id>/estado/", views.device_edit, {"operation": True}, name="operation"),
    path("<uuid:public_id>/trasladar/", views.movement_create, name="move"),
]
