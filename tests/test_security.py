from django.contrib import admin
from django.contrib.auth.models import Group
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.locations.models import Location

from .helpers import create_user, setup_users


class SecurityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        setup_users(cls)

    def test_business_admin_does_not_have_django_admin_access(self):
        self.client.force_login(self.admin)
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)

    def test_internal_admin_cannot_bypass_services(self):
        root = create_user("root", is_superuser=True, is_staff=True)
        self.client.force_login(root)
        self.assertNotIn(Group, admin.site._registry)
        for model in (User, Location):
            model_admin = admin.site._registry[model]
            request = type("Request", (), {"user": root})()
            self.assertFalse(model_admin.has_add_permission(request))
            self.assertFalse(model_admin.has_change_permission(request))
            self.assertFalse(model_admin.has_delete_permission(request))
        self.assertEqual(
            self.client.post(
                f"/admin/accounts/user/{self.teacher.pk}/change/", {"is_superuser": True}
            ).status_code,
            403,
        )
        self.teacher.refresh_from_db()
        self.assertFalse(self.teacher.is_superuser)

    def test_deactivated_session_loses_access(self):
        self.client.force_login(self.teacher)
        User.objects.filter(pk=self.teacher.pk).update(is_active=False)
        self.assertEqual(self.client.get(reverse("accounts:profile")).status_code, 302)

    def test_authenticated_response_cannot_be_cached(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("accounts:list"))
        self.assertIn("no-store", response["Cache-Control"])

    def test_csrf_allows_valid_token_for_creation(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        client.get(reverse("locations:create"))
        token = client.cookies["csrftoken"].value
        response = client.post(
            reverse("locations:create"),
            {
                "name": "Con CSRF",
                "kind": Location.Kind.STORAGE,
                "is_active": "on",
                "csrfmiddlewaretoken": token,
            },
        )
        self.assertEqual(response.status_code, 302)

    @override_settings(DEBUG=False, SECURE_SSL_REDIRECT=True)
    def test_production_redirects_http_to_https(self):
        self.assertEqual(self.client.get(reverse("accounts:login")).status_code, 301)

    @override_settings(DEBUG=False)
    def test_error_pages_in_production(self):
        self.client.force_login(self.teacher)
        self.assertContains(
            self.client.get(reverse("accounts:list")), "No tienes permiso", status_code=403
        )
        self.assertContains(
            self.client.get("/pagina-inexistente/"), "No encontramos", status_code=404
        )
