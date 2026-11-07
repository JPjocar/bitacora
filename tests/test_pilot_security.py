from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .asset_helpers import setup_assets


class PilotSecurityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        setup_assets(cls)

    def test_dashboard_history_restore_returns_a_full_document(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("dashboard:panel"),
            HTTP_HX_REQUEST="true",
            HTTP_HX_HISTORY_RESTORE_REQUEST="true",
        )
        self.assertContains(response, "<!doctype")
        self.assertIn("HX-History-Restore-Request", response["Vary"])

    def test_expired_htmx_response_is_private_and_keeps_security_headers(self):
        response = self.client.get(reverse("dashboard:panel"), HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertIn("HX-Redirect", response)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(response["X-Frame-Options"], "DENY")

    def test_application_headers_allow_local_camera_and_deny_script_injection(self):
        response = self.client.get(reverse("accounts:login"))
        self.assertIn("script-src 'self'", response["Content-Security-Policy"])
        self.assertNotIn("'unsafe-eval'", response["Content-Security-Policy"])
        self.assertIn("camera=(self)", response["Permissions-Policy"])

    @override_settings(DEBUG=False, SESSION_COOKIE_SECURE=True, CSRF_COOKIE_SECURE=True)
    def test_secure_cookies_and_no_cache_on_authenticated_responses(self):
        client = Client()
        client.force_login(self.admin)
        response = client.get(reverse("dashboard:panel"), secure=True)
        self.assertTrue(response.cookies["csrftoken"]["secure"])
        self.assertIn("private", response["Cache-Control"])
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")

    def test_login_does_not_redirect_to_an_external_next_url(self):
        from .helpers import PASSWORD

        response = self.client.post(
            reverse("accounts:login"),
            {
                "username": self.admin.username,
                "password": PASSWORD,
                "next": "https://outside.invalid/",
            },
        )
        self.assertRedirects(response, reverse("home"))
