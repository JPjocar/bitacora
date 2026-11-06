from django.urls import path

from . import views

app_name = "accounts"
urlpatterns = [
    path("ingresar/", views.SignInView.as_view(), name="login"),
    path("salir/", views.SignOutView.as_view(), name="logout"),
    path("perfil/", views.profile, name="profile"),
    path("contrasena/", views.password_change, name="password_change"),
    path("roles/", views.roles, name="roles"),
    path("usuarios/", views.user_list, name="list"),
    path("usuarios/nuevo/", views.user_edit, name="create"),
    path("usuarios/<int:pk>/", views.user_detail, name="detail"),
    path("usuarios/<int:pk>/editar/", views.user_edit, name="edit"),
    path("usuarios/<int:pk>/contrasena/", views.password_reset, name="password_reset"),
]
