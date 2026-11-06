import uuid
from datetime import timedelta

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.assets.models import Category, Device, Movement
from apps.assets.services import move_device, save_device

from .asset_helpers import setup_assets


class AssetViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        setup_assets(cls)

    def device_url(self, name):
        return reverse(f"assets:{name}", args=[self.device.public_id])

    def move_payload(self, **overrides):
        return {
            "destination": self.destination.pk,
            "reason": "Cambio de ambiente",
            "effective_at": (timezone.localtime() - timedelta(minutes=2)).strftime(
                "%Y-%m-%dT%H:%M"
            ),
            "version": 1,
            **overrides,
        }

    def test_anonymous_redirects_on_all_asset_routes(self):
        for url in [
            reverse("assets:list"),
            reverse("assets:create"),
            reverse("assets:categories"),
            reverse("assets:movements"),
            self.device_url("detail"),
            self.device_url("move"),
        ]:
            self.assertEqual(self.client.get(url).status_code, 302)

    def test_admin_pages_render(self):
        self.client.force_login(self.admin)
        for url in [
            reverse("assets:list"),
            reverse("assets:create"),
            reverse("assets:categories"),
            reverse("assets:category_create"),
            reverse("assets:category_detail", args=[self.category.pk]),
            reverse("assets:category_edit", args=[self.category.pk]),
            reverse("assets:movements"),
            self.device_url("detail"),
            self.device_url("edit"),
            self.device_url("operation"),
            self.device_url("move"),
        ]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_teacher_only_limited_fields_and_no_sensitive_list_search(self):
        save_device(
            actor=self.admin,
            device_id=self.device.pk,
            expected_version=1,
            data={
                "serial_number": "SERIE-PRIVADA",
                "technical_details": "DETALLE-PRIVADO",
                "observations": "NOTA-PRIVADA",
            },
        )
        self.client.force_login(self.teacher)
        response = self.client.get(self.device_url("detail"))
        self.assertContains(response, self.device.code)
        self.assertContains(response, self.origin.name)
        for value in (
            "SERIE-PRIVADA",
            "DETALLE-PRIVADO",
            "NOTA-PRIVADA",
            "Historial de cambios",
            "Registrar traslado",
        ):
            self.assertNotContains(response, value)
        response = self.client.get(reverse("assets:list"), {"q": "SERIE-PRIVADA"})
        self.assertEqual(response.context["page_obj"].paginator.count, 0)

    def test_teacher_cannot_access_inactive_or_withdrawn_device_by_id(self):
        self.client.force_login(self.teacher)
        Device.objects.filter(pk=self.device.pk).update(is_active=False)
        self.assertEqual(self.client.get(self.device_url("detail")).status_code, 404)
        self.assertEqual(
            self.client.get(reverse("assets:list"), {"active": "false"})
            .context["page_obj"]
            .paginator.count,
            0,
        )
        Device.objects.filter(pk=self.device.pk).update(
            is_active=True, status=Device.Status.WITHDRAWN
        )
        self.assertEqual(self.client.get(self.device_url("detail")).status_code, 404)
        response = self.client.get(reverse("assets:list"))
        self.assertNotContains(response, self.origin.name)

    def test_teacher_cannot_write_or_read_movement_and_category_by_url(self):
        self.client.force_login(self.teacher)
        urls = [
            reverse("assets:create"),
            self.device_url("edit"),
            self.device_url("operation"),
            self.device_url("move"),
            reverse("assets:movements"),
            reverse("assets:movement_detail", args=[999]),
            reverse("assets:categories"),
            reverse("assets:category_create"),
            reverse("assets:category_edit", args=[self.category.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
                self.assertEqual(self.client.post(url, {}, HTTP_HX_REQUEST="true").status_code, 403)

    def test_technician_cannot_create_device_or_change_catalog(self):
        self.client.force_login(self.technician)
        for url in [
            reverse("assets:create"),
            self.device_url("edit"),
            reverse("assets:category_create"),
            reverse("assets:category_edit", args=[self.category.pk]),
        ]:
            self.assertEqual(self.client.get(url).status_code, 403)
            self.assertEqual(self.client.post(url, {}).status_code, 403)

    def test_technician_operation_requires_reason_and_ignores_injected_fields(self):
        self.client.force_login(self.technician)
        data = {
            "status": Device.Status.OUT_OF_SERVICE,
            "version": 1,
            "name": "Inyectado",
            "location": self.destination.pk,
        }
        response = self.client.post(self.device_url("operation"), data)
        self.assertContains(response, "Explique brevemente")
        data["reason"] = "No enciende"
        self.assertEqual(self.client.post(self.device_url("operation"), data).status_code, 302)
        self.device.refresh_from_db()
        self.assertEqual(self.device.name, "Equipo de prueba")
        self.assertEqual(self.device.location, self.origin)
        self.assertEqual(self.device.status, Device.Status.OUT_OF_SERVICE)

    def test_device_create_form_without_serial_and_with_bad_dates(self):
        self.client.force_login(self.admin)
        data = {
            "name": "Router",
            "category": self.category.pk,
            "location": self.origin.pk,
            "status": Device.Status.OPERATIONAL,
            "is_active": "on",
        }
        invalid = self.client.post(reverse("assets:create"), data | {"acquired_on": "no-es-fecha"})
        self.assertEqual(invalid.status_code, 200)
        self.assertIn("acquired_on", invalid.context["form"].errors)
        response = self.client.post(reverse("assets:create"), data)
        self.assertEqual(response.status_code, 302)
        device = Device.objects.get(name="Router")
        self.assertEqual(device.serial_number, "")
        self.assertIn(str(device.public_id), response.url)

    def test_admin_edit_preserves_identifiers_and_location(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            self.device_url("edit"),
            {
                "name": "Equipo editado",
                "category": self.category.pk,
                "location": self.destination.pk,
                "status": Device.Status.OPERATIONAL,
                "version": 1,
                "is_active": "on",
                "code": "EQ-ABCDEFGH",
            },
        )
        self.assertEqual(response.status_code, 302)
        old_code = self.device.code
        self.device.refresh_from_db()
        self.assertEqual(self.device.location, self.origin)
        self.assertEqual(self.device.code, old_code)
        self.assertEqual(self.device.name, "Equipo editado")

    def test_missing_versions_rejected(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            self.device_url("operation"), {"status": Device.Status.OPERATIONAL}
        )
        self.assertIn("version", response.context["form"].errors)
        data = self.move_payload()
        data.pop("version")
        response = self.client.post(self.device_url("move"), data)
        self.assertIn("version", response.context["form"].errors)
        self.assertEqual(Movement.objects.count(), 0)

    def test_filter_code_case_spaces_pagination_and_htmx(self):
        self.client.force_login(self.technician)
        response = self.client.get(
            reverse("assets:list"), {"q": f" {self.device.code.lower()} "}, HTTP_HX_REQUEST="true"
        )
        self.assertContains(response, self.device.code)
        self.assertNotContains(response, "<!doctype html>")
        self.assertIn("HX-Request", response["Vary"])
        response = self.client.get(
            reverse("assets:list"), HTTP_HX_REQUEST="true", HTTP_HX_HISTORY_RESTORE_REQUEST="true"
        )
        self.assertContains(response, "<!doctype html>")
        Device.objects.bulk_create(
            [
                Device(
                    name=f"Equipo {i:02}",
                    category=self.category,
                    location=self.origin,
                    created_by=self.admin,
                )
                for i in range(22)
            ]
        )
        page = self.client.get(
            reverse("assets:list"),
            {
                "category": self.category.pk,
                "location": self.origin.pk,
                "status": "OPERATIVO",
                "page": 2,
            },
        )
        self.assertEqual(len(page.context["page_obj"]), 3)

    def test_category_create_edit_and_deactivate(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("assets:category_create"),
            {"name": "Periféricos", "kind": "OTROS", "is_active": "on"},
        )
        self.assertEqual(response.status_code, 302)
        category = Category.objects.get(name="Periféricos")
        response = self.client.post(
            reverse("assets:category_edit", args=[category.pk]),
            {"name": category.name, "kind": category.kind, "version": 1},
        )
        self.assertEqual(response.status_code, 302)
        category.refresh_from_db()
        self.assertFalse(category.is_active)
        self.assertEqual(category.events.count(), 2)

    def test_movement_form_real_origin_and_actor_ignore_payload(self):
        self.client.force_login(self.technician)
        response = self.client.post(
            self.device_url("move"), self.move_payload(origin=self.other.pk, actor=self.teacher.pk)
        )
        self.assertEqual(response.status_code, 302)
        movement = Movement.objects.get()
        self.assertEqual(movement.origin, self.origin)
        self.assertEqual(movement.actor, self.technician)
        self.assertEqual(
            timezone.localtime(movement.effective_at).strftime("%Y-%m-%dT%H:%M"),
            self.move_payload()["effective_at"],
        )
        self.assertEqual(self.client.get(response.url).status_code, 200)

    def test_warning_required_in_view_and_visible_before_submission(self):
        Device.objects.filter(pk=self.device.pk).update(status=Device.Status.OUT_OF_SERVICE)
        self.client.force_login(self.technician)
        self.assertContains(
            self.client.get(self.device_url("move")), "Trasladarlo no implica repararlo"
        )
        response = self.client.post(self.device_url("move"), self.move_payload())
        self.assertIn("confirm_warning", response.context["form"].errors)
        self.assertEqual(
            self.client.post(
                self.device_url("move"), self.move_payload(confirm_warning="on")
            ).status_code,
            302,
        )

    def test_movement_list_filters_date_errors_and_htmx(self):
        movement = move_device(
            actor=self.admin,
            device_id=self.device.pk,
            destination_id=self.destination.pk,
            expected_version=1,
            reason="Probando",
            effective_at=timezone.now(),
        )
        self.client.force_login(self.technician)
        response = self.client.get(
            reverse("assets:movements"),
            {
                "q": self.device.code.lower(),
                "location": self.origin.pk,
                "start": timezone.localdate().isoformat(),
                "end": timezone.localdate().isoformat(),
            },
            HTTP_HX_REQUEST="true",
        )
        self.assertContains(response, self.device.code)
        self.assertNotContains(response, "<!doctype html>")
        self.assertEqual(response.context["page_obj"].paginator.count, 1)
        response = self.client.get(
            reverse("assets:movements"),
            {"start": "2026-11-10", "end": "2026-11-01"},
            HTTP_HX_REQUEST="true",
        )
        self.assertContains(response, "La fecha inicial")
        self.assertEqual(
            self.client.get(reverse("assets:movement_detail", args=[movement.pk])).status_code, 200
        )

    def test_csrf_protects_all_mutations_and_get_does_not_move(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        for url in [
            reverse("assets:create"),
            reverse("assets:category_create"),
            self.device_url("edit"),
            self.device_url("operation"),
            self.device_url("move"),
        ]:
            self.assertEqual(client.post(url, {}, HTTP_HX_REQUEST="true").status_code, 403)
        self.client.force_login(self.admin)
        self.client.get(self.device_url("move"), self.move_payload())
        self.assertEqual(Movement.objects.count(), 0)
        self.assertEqual(self.client.delete(self.device_url("move")).status_code, 405)

    def test_valid_csrf_movement(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.technician)
        client.get(self.device_url("move"))
        response = client.post(
            self.device_url("move"),
            self.move_payload(csrfmiddlewaretoken=client.cookies["csrftoken"].value),
        )
        self.assertEqual(response.status_code, 302)

    def test_invalid_ids_and_xss_escaping(self):
        self.client.force_login(self.admin)
        self.assertEqual(
            self.client.get(reverse("assets:detail", args=[uuid.uuid4()])).status_code, 404
        )
        save_device(
            actor=self.admin,
            device_id=self.device.pk,
            expected_version=1,
            data={"technical_details": "<script>evil()</script>"},
        )
        response = self.client.get(self.device_url("detail"))
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, "<script>evil()</script>")
