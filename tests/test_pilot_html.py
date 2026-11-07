from collections import Counter
from html.parser import HTMLParser

from django.test import TestCase
from django.urls import reverse

from .asset_helpers import setup_assets


class Controls(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.ids, self.labels, self.controls = [], set(), []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id"):
            self.ids.append(attrs["id"])
        if tag == "label" and attrs.get("for"):
            self.labels.add(attrs["for"])
        if tag in {"input", "select", "textarea"} and attrs.get("type") not in {
            "hidden",
            "submit",
            "button",
        }:
            self.controls.append(attrs.get("id"))


class PilotHTMLTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        setup_assets(cls)

    def test_main_forms_have_unique_ids_and_explicit_labels(self):
        self.client.force_login(self.admin)
        routes = [
            reverse(name)
            for name in [
                "home",
                "accounts:profile",
                "accounts:create",
                "locations:create",
                "assets:create",
                "assets:scanner",
                "maintenance:create",
                "dashboard:panel",
                "incidents:list",
            ]
        ]
        routes.append(reverse("incidents:report", args=[self.device.public_id]))
        for route in routes:
            with self.subTest(route=route):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 200)
                html = response.content.decode("utf8")
                parsed = Controls(html)
                self.assertFalse([key for key, count in Counter(parsed.ids).items() if count > 1])
                self.assertTrue(
                    all(control and control in parsed.labels for control in parsed.controls)
                )
                self.assertIn('<html lang="es-PE">', html)
                self.assertIn('name="viewport"', html)
                self.assertIn('href="#main"', html)
