from datetime import UTC, datetime
from unittest.mock import patch
from uuid import uuid4

from django.contrib import admin
from django.test import Client, TestCase
from django.urls import reverse

from apps.assets.models import Device
from apps.assets.selectors import movement_warning
from apps.maintenance.forms import MaintenanceForm
from apps.maintenance.models import (
    Maintenance,
    MaintenanceEvent,
    MaintenanceRun,
    MaintenanceRunDevice,
    MaintenanceTarget,
    MaintenanceTaskResult,
    MaintenanceTaskTemplate,
)

from .asset_helpers import setup_assets
from .helpers import create_user
from .maintenance_helpers import create_maintenance


class MaintenanceViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        setup_assets(cls)
        cls.maintenance = create_maintenance(cls)

    def payload(self, **overrides):
        return {
            "kind": "unique",
            "name": "Preventivo por formulario",
            "description": "",
            "planned_date": "2026-12-01",
            "devices": [self.device.pk],
            "creation_key": str(uuid4()),
            "tasks-TOTAL_FORMS": "1",
            "tasks-INITIAL_FORMS": "0",
            "tasks-0-name": "Verificar conexiones",
            "tasks-0-scope": "DISPOSITIVO",
            "tasks-0-category": "",
            "tasks-0-required": "on",
            "tasks-0-ORDER": "1",
            **overrides,
        }

    def test_anonymous_redirects_and_roles_are_enforced_on_all_routes(self):
        paths = [
            reverse("maintenance:list"),
            reverse("maintenance:create"),
            reverse("maintenance:detail", args=[self.maintenance.pk]),
            reverse("maintenance:edit", args=[self.maintenance.pk]),
            reverse("maintenance:history", args=[self.maintenance.pk]),
        ]
        for path in paths:
            self.assertEqual(self.client.get(path).status_code, 302)
        for actor in (self.admin, self.technician, self.teacher):
            self.client.force_login(actor)
            for index, path in enumerate(paths):
                expected = (
                    200
                    if actor == self.admin or (actor == self.technician and index in (0, 2, 4))
                    else 403
                )
                self.assertEqual(
                    self.client.get(path).status_code, expected, (actor.username, path)
                )
            expected_post = 403 if actor != self.admin else 302
            self.assertEqual(
                self.client.post(reverse("maintenance:create"), self.payload()).status_code,
                expected_post,
            )

    def test_create_unique_and_repeated_post_produce_one_execution(self):
        self.client.force_login(self.admin)
        data = self.payload()
        response = self.client.post(reverse("maintenance:create"), data)
        created = Maintenance.objects.get(creation_key=data["creation_key"])
        self.assertRedirects(response, reverse("maintenance:detail", args=[created.pk]))
        self.assertRedirects(self.client.post(reverse("maintenance:create"), data), response.url)
        self.assertEqual(created.runs.count(), 1)
        self.assertEqual(created.events.count(), 1)

    def test_create_periodic_through_form_and_ignore_injected_state(self):
        self.client.force_login(self.admin)
        data = self.payload(
            kind="recurring",
            base_date="2026-01-31",
            interval_value="1",
            interval_unit="MESES",
            state="COMPLETADO",
            created_by=self.teacher.pk,
        )
        response = self.client.post(reverse("maintenance:create"), data)
        self.assertEqual(response.status_code, 302)
        created = Maintenance.objects.get(creation_key=data["creation_key"])
        self.assertEqual(str(created.runs.get().participants.get().due_date), "2026-02-28")
        self.assertEqual(created.created_by, self.admin)
        self.assertEqual(created.runs.get().state, "PENDIENTE_ATENCION")

    def test_date_fields_follow_type_and_default_to_lima_today(self):
        with patch("django.utils.timezone.now", return_value=datetime(2026, 11, 7, 2, tzinfo=UTC)):
            unique = MaintenanceForm(kind="unique")
            periodic = MaintenanceForm(kind="recurring")
            self.assertEqual(str(unique["planned_date"].value()), "2026-11-06")
            self.assertEqual(str(periodic["base_date"].value()), "2026-11-06")
            self.assertNotIn("base_date", unique.fields)
            self.assertNotIn("interval_unit", unique.fields)
            self.assertNotIn("planned_date", periodic.fields)

    def test_invalid_configuration_renders_errors_and_preserves_values(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("maintenance:create"),
            self.payload(
                kind="recurring", base_date="2026-10-01", interval_value="0", interval_unit="MESES"
            ),
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertContains(response, "Preventivo por formulario")
        self.assertEqual(Maintenance.objects.count(), 1)

    def test_formset_category_errors_and_missing_individual_tasks(self):
        self.client.force_login(self.admin)
        for changes in ({"tasks-0-scope": "GRUPAL"}, {"tasks-0-category": "9999999"}):
            response = self.client.post(reverse("maintenance:create"), self.payload(**changes))
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["form"].errors or response.context["formset"].errors)
        self.assertEqual(Maintenance.objects.count(), 1)

    def test_task_order_optional_and_delete_are_honored(self):
        self.client.force_login(self.admin)
        data = self.payload(
            **{
                "tasks-TOTAL_FORMS": "3",
                "tasks-0-ORDER": "2",
                "tasks-1-name": "Preparar área",
                "tasks-1-scope": "GRUPAL",
                "tasks-1-category": "",
                "tasks-1-ORDER": "1",
                "tasks-2-name": "No incluir",
                "tasks-2-scope": "DISPOSITIVO",
                "tasks-2-DELETE": "on",
            }
        )
        response = self.client.post(reverse("maintenance:create"), data)
        self.assertEqual(response.status_code, 302)
        maintenance = Maintenance.objects.get(creation_key=data["creation_key"])
        self.assertEqual(
            list(maintenance.task_templates.values_list("name", flat=True)),
            ["Preparar área", "Verificar conexiones"],
        )
        self.assertFalse(maintenance.task_templates.get(name="Preparar área").required)

    def test_add_task_without_javascript_preserves_form_and_does_not_save(self):
        self.client.force_login(self.admin)
        data = self.payload(action="add_task")
        response = self.client.post(reverse("maintenance:create"), data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["formset"].total_form_count(), 2)
        self.assertFalse(response.context["formset"].forms[-1].has_changed())
        self.assertTrue(response.context["formset"].is_valid())
        self.assertContains(response, data["creation_key"])
        self.assertContains(response, 'name="tasks-1-name"')
        self.assertEqual(Maintenance.objects.count(), 1)

    def test_forged_or_missing_management_form_is_rejected(self):
        self.client.force_login(self.admin)
        for count in ("999999", "invalid", "0"):
            response = self.client.post(
                reverse("maintenance:create"), self.payload(**{"tasks-TOTAL_FORMS": count})
            )
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["formset"].non_form_errors())
        self.assertEqual(Maintenance.objects.count(), 1)

    def test_edit_requires_version_and_does_not_rewrite_snapshot(self):
        self.client.force_login(self.admin)
        url = reverse("maintenance:edit", args=[self.maintenance.pk])
        data = self.payload(
            name="Configuración corregida",
            reason="Aclarar tareas futuras",
            is_active="on",
            **{"tasks-INITIAL_FORMS": "1"},
        )
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertIn("version", response.context["form"].errors)
        data["version"] = 1
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.maintenance.refresh_from_db()
        self.assertEqual(self.maintenance.name, "Configuración corregida")
        self.assertEqual(self.maintenance.runs.get().configuration["name"], "Preventivo de prueba")
        self.assertEqual(self.client.post(url, data).status_code, 200)

    def test_retired_or_inactive_new_device_is_excluded_from_picker(self):
        Device.objects.filter(pk=self.device.pk).update(is_active=False)
        form = MaintenanceForm()
        self.assertFalse(form.fields["devices"].queryset.filter(pk=self.device.pk).exists())
        existing = MaintenanceForm(maintenance=self.maintenance)
        self.assertTrue(existing.fields["devices"].queryset.filter(pk=self.device.pk).exists())

    def test_htmx_filter_and_history_restore(self):
        self.client.force_login(self.technician)
        url = reverse("maintenance:list")
        response = self.client.get(url, {"q": self.device.code.lower()}, HTTP_HX_REQUEST="true")
        self.assertContains(response, 'id="results"')
        self.assertContains(response, "Preventivo de prueba")
        self.assertNotContains(response, "<!doctype")
        restored = self.client.get(
            url, HTTP_HX_REQUEST="true", HTTP_HX_HISTORY_RESTORE_REQUEST="true"
        )
        self.assertContains(restored, "<!doctype")
        self.assertIn("HX-Request", restored["Vary"])

    def test_filters_pagination_and_empty_list(self):
        self.client.force_login(self.admin)
        for index in range(21):
            create_maintenance(
                self,
                data={
                    "name": f"Equipo preventivo {index}",
                    "planned_date": self.maintenance.planned_date,
                },
            )
        response = self.client.get(reverse("maintenance:list"))
        self.assertEqual(len(response.context["page_obj"]), 20)
        second = self.client.get(reverse("maintenance:list"), {"page": 2})
        self.assertEqual(len(second.context["page_obj"]), 2)
        for filters in ({"kind": "recurring"}, {"active": "false"}, {"q": "no existe"}):
            self.assertContains(
                self.client.get(reverse("maintenance:list"), filters), "No se encontraron"
            )

    def test_get_views_do_not_mutate_and_escape_text(self):
        maintenance = create_maintenance(
            self,
            data={
                "name": "<script>alert(1)</script>",
                "planned_date": self.maintenance.planned_date,
            },
        )
        self.client.force_login(self.technician)
        count = MaintenanceEvent.objects.count()
        response = self.client.get(reverse("maintenance:detail", args=[maintenance.pk]))
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(MaintenanceEvent.objects.count(), count)

    def test_csrf_for_creation_and_task_row_request(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        for action in ("save", "add_task"):
            self.assertEqual(
                client.post(reverse("maintenance:create"), self.payload(action=action)).status_code,
                403,
            )
        client.get(reverse("maintenance:create"))
        response = client.post(
            reverse("maintenance:create"),
            self.payload(csrfmiddlewaretoken=client.cookies["csrftoken"].value),
        )
        self.assertEqual(response.status_code, 302)

    def test_legacy_action_paths_and_delete_remain_unavailable(self):
        self.client.force_login(self.admin)
        for action in ("tomar", "iniciar", "liberar", "completar"):
            self.assertEqual(
                self.client.post(f"/mantenimientos/{self.maintenance.pk}/{action}/").status_code,
                404,
            )
        self.assertEqual(
            self.client.delete(reverse("maintenance:edit", args=[self.maintenance.pk])).status_code,
            405,
        )
        self.assertEqual(
            self.client.get(reverse("maintenance:detail", args=[9999999])).status_code, 404
        )

    def test_internal_admin_cannot_bypass_configuration_services(self):
        root = create_user("root-maintenance", is_staff=True, is_superuser=True)
        request = type("Request", (), {"user": root})()
        for model in (
            Maintenance,
            MaintenanceTarget,
            MaintenanceTaskTemplate,
            MaintenanceRun,
            MaintenanceRunDevice,
            MaintenanceTaskResult,
            MaintenanceEvent,
        ):
            handler = admin.site._registry[model]
            self.assertFalse(handler.has_add_permission(request))
            self.assertFalse(handler.has_change_permission(request))
            self.assertFalse(handler.has_delete_permission(request))

    def test_pending_preventive_warns_and_requires_confirmation_before_movement(self):
        self.client.force_login(self.technician)
        path = reverse("assets:move", args=[self.device.public_id])
        self.assertIn("preventivo pendiente", movement_warning(self.device))
        response = self.client.get(path)
        self.assertContains(response, 'name="confirm_warning"')
        data = {
            "version": self.device.version,
            "destination": self.destination.pk,
            "reason": "Traslado pendiente",
            "effective_at": "2026-01-01T10:00",
        }
        response = self.client.post(path, data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Confirme que leyó")
        data["confirm_warning"] = "on"
        self.assertEqual(self.client.post(path, data).status_code, 302)
        self.assertEqual(self.maintenance.runs.get().participants.get().result, "SIN_FINALIZAR")
