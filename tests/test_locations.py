from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import Client, TestCase
from django.urls import reverse

from apps.locations.models import Location, LocationEvent
from apps.locations.services import save_location

from .helpers import setup_users


class LocationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        setup_users(cls)
        cls.location = save_location(
            actor=cls.admin,
            data={"name": "Laboratorio 1", "code": "LAB-01", "kind": Location.Kind.LABORATORY},
        )

    def test_create_normalizes_and_records_actor(self):
        location = save_location(
            actor=self.admin,
            data={"name": "  Almacén  ", "code": "  alm-01 ", "kind": Location.Kind.STORAGE},
        )
        self.assertEqual(location.name, "Almacén")
        self.assertEqual(location.code, "ALM-01")
        self.assertEqual(location.events.get().actor, self.admin)
        self.assertEqual(location.events.get().action, "Creación")

    def test_optional_code_can_repeat_blank(self):
        for name in ["Almacén A", "Almacén B"]:
            save_location(actor=self.admin, data={"name": name, "kind": Location.Kind.STORAGE})
        self.assertEqual(Location.objects.filter(code="").count(), 2)

    def test_duplicate_name_or_code_is_rejected(self):
        for data in [
            {"name": " laboratorio 1 ", "kind": Location.Kind.STORAGE},
            {"name": "Otro", "code": "lab-01", "kind": Location.Kind.STORAGE},
        ]:
            with self.assertRaises(ValidationError):
                save_location(actor=self.admin, data=data)

    def test_database_constraints_even_without_model_clean(self):
        for data in [
            {"name": "laboratorio 1", "kind": Location.Kind.STORAGE},
            {"name": "Otro", "code": "lab-01", "kind": Location.Kind.STORAGE},
            {"name": "  ", "kind": Location.Kind.STORAGE},
            {"name": "Otro", "kind": "INVALIDO"},
        ]:
            with self.subTest(data=data), self.assertRaises(IntegrityError), transaction.atomic():
                Location.objects.create(**data)

    def test_validation_blank_long_invalid_kind_and_code(self):
        for data in [
            {"name": "  ", "kind": Location.Kind.STORAGE},
            {"name": "X" * 121, "kind": Location.Kind.STORAGE},
            {"name": "Otro", "kind": "INVALIDO"},
            {"name": "Otro", "code": "<codigo>", "kind": Location.Kind.STORAGE},
        ]:
            with self.subTest(data=data), self.assertRaises(ValidationError):
                save_location(actor=self.admin, data=data)

    def test_deactivation_and_reactivation_preserve_history(self):
        for version, active in [(1, False), (2, True)]:
            location = save_location(
                actor=self.admin,
                location_id=self.location.pk,
                expected_version=version,
                data={"is_active": active},
            )
            self.assertEqual(location.is_active, active)
            self.assertEqual(location.events.count(), version + 1)
        self.assertEqual(Location.objects.count(), 1)
        self.assertEqual(location.events.first().action, "Reactivación")

    def test_no_delete_and_protected_reference(self):
        for operation in [
            self.location.delete,
            lambda: Location.objects.all().delete(),
            lambda: self.location.events.all().delete(),
        ]:
            with self.assertRaises(ValidationError):
                operation()
        # Bypass the public delete override to verify Django's PROTECT relationship.
        from django.db.models import Model

        with self.assertRaises(ProtectedError):
            Model.delete(self.location)

    def test_noop_does_not_add_event(self):
        save_location(
            actor=self.admin,
            location_id=self.location.pk,
            expected_version=1,
            data={"name": self.location.name},
        )
        self.assertEqual(self.location.events.count(), 1)

    def test_stale_edit_rejected(self):
        save_location(
            actor=self.admin,
            location_id=self.location.pk,
            expected_version=1,
            data={"name": "Cambio A"},
        )
        with self.assertRaises(ValidationError):
            save_location(
                actor=self.admin,
                location_id=self.location.pk,
                expected_version=1,
                data={"name": "Cambio B"},
            )
        self.location.refresh_from_db()
        self.assertEqual(self.location.name, "Cambio A")

    def test_audit_failure_rolls_back(self):
        with (
            patch("apps.locations.services.LocationEvent.objects.create", side_effect=RuntimeError),
            self.assertRaises(RuntimeError),
        ):
            save_location(
                actor=self.admin,
                location_id=self.location.pk,
                expected_version=1,
                data={"is_active": False},
            )
        self.location.refresh_from_db()
        self.assertTrue(self.location.is_active)

    def test_service_permissions(self):
        for actor in (self.technician, self.teacher):
            with self.assertRaises(PermissionDenied):
                save_location(actor=actor, data={"name": "Ambiente", "kind": Location.Kind.STORAGE})
            with self.assertRaises(PermissionDenied):
                save_location(
                    actor=actor,
                    location_id=self.location.pk,
                    expected_version=1,
                    data={"is_active": False},
                )

    def test_anonymous_and_teacher_denied(self):
        urls = [
            reverse("locations:list"),
            reverse("locations:create"),
            reverse("locations:detail", args=[self.location.pk]),
            reverse("locations:edit", args=[self.location.pk]),
        ]
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.teacher)
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 403)
            self.assertEqual(self.client.post(url, HTTP_HX_REQUEST="true").status_code, 403)

    def test_technician_read_only_and_no_history_personal_data(self):
        self.client.force_login(self.technician)
        self.assertEqual(self.client.get(reverse("locations:list")).status_code, 200)
        response = self.client.get(reverse("locations:detail", args=[self.location.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.admin.username)
        for url in [
            reverse("locations:create"),
            reverse("locations:edit", args=[self.location.pk]),
        ]:
            self.assertEqual(self.client.get(url).status_code, 403)
            self.assertEqual(self.client.post(url, {"is_active": False}).status_code, 403)

    def test_admin_pages_and_invalid_ids(self):
        self.client.force_login(self.admin)
        for name, args in [
            ("locations:list", []),
            ("locations:create", []),
            ("locations:detail", [self.location.pk]),
            ("locations:edit", [self.location.pk]),
        ]:
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 200)
        self.assertEqual(
            self.client.get(reverse("locations:detail", args=[99999])).status_code, 404
        )
        self.assertEqual(
            self.client.delete(reverse("locations:edit", args=[self.location.pk])).status_code, 405
        )

    def test_form_invalid_create_edit_and_get_does_not_mutate(self):
        self.client.force_login(self.admin)
        create = reverse("locations:create")
        self.assertContains(
            self.client.post(create, {"name": "", "kind": "INVALIDO"}), "Este campo es obligatorio"
        )
        response = self.client.post(
            create, {"name": "Nuevo", "kind": Location.Kind.STORAGE, "is_active": "on"}
        )
        self.assertEqual(response.status_code, 302)
        edit = reverse("locations:edit", args=[self.location.pk])
        self.client.get(edit, {"is_active": "false"})
        self.location.refresh_from_db()
        self.assertTrue(self.location.is_active)
        response = self.client.post(
            edit,
            {
                "name": self.location.name,
                "code": self.location.code,
                "kind": self.location.kind,
                "version": 1,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.location.refresh_from_db()
        self.assertFalse(self.location.is_active)

    def test_missing_version_cannot_overwrite(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("locations:edit", args=[self.location.pk]),
            {"name": "Reemplazo", "kind": self.location.kind},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("version", response.context["form"].errors)
        self.location.refresh_from_db()
        self.assertNotEqual(self.location.name, "Reemplazo")

    def test_csrf_enforced_for_plain_and_htmx(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        for headers in ({}, {"HTTP_HX_REQUEST": "true"}):
            self.assertEqual(
                client.post(reverse("locations:create"), {}, **headers).status_code, 403
            )

    def test_filter_search_pagination_and_htmx_restore(self):
        Location.objects.bulk_create(
            [
                Location(name=f"Almacén {i:02}", code=f"ALM-{i:02}", kind=Location.Kind.STORAGE)
                for i in range(25)
            ]
        )
        self.client.force_login(self.admin)
        url = reverse("locations:list")
        page = self.client.get(url, {"kind": Location.Kind.STORAGE, "page": 2, "active": "true"})
        self.assertEqual(len(page.context["page_obj"]), 5)
        response = self.client.get(url, {"q": " lab-01 "}, HTTP_HX_REQUEST="true")
        self.assertEqual(response.context["page_obj"].paginator.count, 1)
        self.assertContains(response, "Laboratorio 1")
        self.assertNotContains(response, "<!doctype html>")
        restored = self.client.get(
            url, HTTP_HX_REQUEST="true", HTTP_HX_HISTORY_RESTORE_REQUEST="true"
        )
        self.assertContains(restored, "<!doctype html>")
        self.assertIn("HX-Request", response["Vary"])

    def test_htmx_expired_session_redirects_whole_page(self):
        response = self.client.get(reverse("locations:list"), HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertIn("/cuentas/ingresar/", response["HX-Redirect"])

    def test_template_escapes_description(self):
        save_location(
            actor=self.admin,
            location_id=self.location.pk,
            expected_version=1,
            data={"description": '<script>alert("x")</script>'},
        )
        self.client.force_login(self.technician)
        response = self.client.get(reverse("locations:detail", args=[self.location.pk]))
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, '<script>alert("x")</script>')

    def test_audit_not_modifiable(self):
        event = self.location.events.get()
        with self.assertRaises(ValidationError):
            LocationEvent.objects.filter(pk=event.pk).update(action="Alterado")
        with self.assertRaises(ValidationError):
            LocationEvent.objects.bulk_update([event], ["action"])
