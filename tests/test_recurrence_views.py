from datetime import date

from django.test import Client, TestCase
from django.urls import reverse

from apps.assets.models import Device
from apps.assets.services import save_device
from apps.maintenance.models import Maintenance, MaintenanceEvent
from apps.maintenance.selectors import target_schedule
from apps.maintenance.services import save_maintenance, template_data

from .asset_helpers import device_data, setup_assets
from .execution_helpers import make_run
from .recurrence_helpers import cancel_run, finish_run, next_run, recurring_run


class RecurrenceViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        setup_assets(cls)
        cls.previous = recurring_run(cls)
        cancel_run(cls, cls.previous)

    def path(self, name):
        return reverse(f"maintenance:{name}", args=[self.previous.maintenance_id])

    def payload(self, **kwargs):
        return {
            "version": self.previous.maintenance.version,
            "previous_run_id": self.previous.pk,
            "targets": [self.previous.maintenance.targets.get().pk],
            "reason": "Selección anticipada autorizada",
            **kwargs,
        }

    def test_authentication_and_role_matrix_on_all_new_pages(self):
        paths = [
            self.path("due_dates"),
            self.path("executions"),
            self.path("next_run"),
            reverse(
                "maintenance:run_detail", args=[self.previous.maintenance_id, self.previous.pk]
            ),
        ]
        for path in paths:
            self.assertEqual(self.client.get(path).status_code, 302)
        for actor in (self.admin, self.technician, self.teacher):
            self.client.force_login(actor)
            for path in paths:
                self.assertEqual(
                    self.client.get(path).status_code, 403 if actor == self.teacher else 200
                )
        self.assertEqual(self.client.post(self.path("next_run"), self.payload()).status_code, 403)

    def test_post_creates_next_and_redirects_to_its_exact_history_detail(self):
        self.client.force_login(self.technician)
        response = self.client.post(
            self.path("next_run"), self.payload(state="COMPLETADO", responsible=self.admin.pk)
        )
        current = self.previous.maintenance.runs.first()
        self.assertRedirects(
            response, reverse("maintenance:run_detail", args=[current.maintenance_id, current.pk])
        )
        self.assertEqual(current.number, 2)
        self.assertEqual(current.state, "PENDIENTE_ATENCION")
        self.assertIsNone(current.responsible)
        self.assertIsNone(current.started_at)
        self.assertFalse(current.tasks.filter(completed=True).exists())

    def test_get_does_not_mutate_and_repeated_post_is_rejected(self):
        self.client.force_login(self.technician)
        count = MaintenanceEvent.objects.count()
        for name in ("due_dates", "executions", "next_run"):
            self.assertEqual(self.client.get(self.path(name)).status_code, 200)
        self.assertEqual(MaintenanceEvent.objects.count(), count)
        data = self.payload()
        self.assertEqual(self.client.post(self.path("next_run"), data).status_code, 302)
        self.assertEqual(self.client.post(self.path("next_run"), data).status_code, 200)
        self.assertEqual(self.previous.maintenance.runs.count(), 2)

    def test_default_proposals_and_missing_early_reason(self):
        self.client.force_login(self.technician)
        response = self.client.get(self.path("next_run"))
        schedules = target_schedule(self.previous.maintenance)
        self.assertEqual(
            response.context["form"].initial["targets"],
            [str(row.target.pk) for row in schedules if row.proposed],
        )
        # Use a known future base independent of the execution date of this test.
        Maintenance.objects.filter(pk=self.previous.maintenance_id).update(
            base_date=date(9998, 1, 1)
        )
        response = self.client.post(self.path("next_run"), self.payload(reason=""))
        self.assertEqual(response.status_code, 200)
        self.assertIn("reason", response.context["form"].errors)
        self.assertEqual(self.previous.maintenance.runs.count(), 1)

    def test_invalid_or_foreign_target_stale_version_and_missing_predecessor(self):
        self.client.force_login(self.technician)
        foreign = recurring_run(self).maintenance.targets.get()
        for data in (
            self.payload(targets=[foreign.pk]),
            self.payload(version=999),
            self.payload(previous_run_id=""),
            self.payload(targets=[]),
        ):
            response = self.client.post(self.path("next_run"), data)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["form"].errors)
        self.assertEqual(self.previous.maintenance.runs.count(), 1)

    def test_open_inactive_or_unique_has_no_create_button_and_no_write(self):
        self.client.force_login(self.admin)
        for record in (make_run(self), recurring_run(self)):
            path = reverse("maintenance:next_run", args=[record.maintenance_id])
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["blocked"])
            self.assertNotContains(response, 'type="submit">Crear ejecución pendiente')
        Maintenance.objects.filter(pk=self.previous.maintenance_id).update(is_active=False)
        response = self.client.post(self.path("next_run"), self.payload())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.previous.maintenance.runs.count(), 1)

    def test_unavailable_devices_are_omitted_from_choices_without_losing_history(self):
        self.client.force_login(self.admin)
        Device.objects.filter(pk=self.device.pk).update(is_active=False)
        response = self.client.get(self.path("next_run"))
        self.assertEqual(list(response.context["form"].fields["targets"].choices), [])
        self.assertContains(response, "No hay equipos disponibles")
        self.assertContains(self.client.get(self.path("due_dates")), "Equipo inactivo")

    def test_calendar_query_and_temporal_filter_return_htmx_and_restore_documents(self):
        self.client.force_login(self.technician)
        path = self.path("due_dates")
        response = self.client.get(path, {"q": self.device.code.lower()}, HTTP_HX_REQUEST="true")
        self.assertContains(response, self.device.code)
        self.assertNotContains(response, "<!doctype")
        self.assertIn("HX-Request", response["Vary"])
        restored = self.client.get(
            path, HTTP_HX_REQUEST="true", HTTP_HX_HISTORY_RESTORE_REQUEST="true"
        )
        self.assertContains(restored, "<!doctype")
        self.assertContains(self.client.get(path, {"q": "no existe"}), "No se encontraron")
        present = target_schedule(self.previous.maintenance)[0].timing
        other = "overdue" if present != "overdue" else "later"
        self.assertContains(self.client.get(path, {"timing": other}), "No se encontraron")

    def test_specific_history_detail_preserves_old_name_tasks_dates_and_parent_scope(self):
        self.client.force_login(self.admin)
        maintenance = self.previous.maintenance
        save_maintenance(
            actor=self.admin,
            maintenance_id=maintenance.pk,
            expected_version=maintenance.version,
            data={"name": "Configuración nueva"},
            device_ids=[self.device.pk],
            tasks=template_data(maintenance),
            reason="Cambiar nombre futuro",
        )
        current = next_run(self, self.previous)
        historic = reverse("maintenance:run_detail", args=[maintenance.pk, self.previous.pk])
        response = self.client.get(historic)
        self.assertContains(response, "Preventivo de prueba")
        self.assertContains(response, "Consulta de la ejecución 1")
        self.assertEqual(response.context["run"].pk, self.previous.pk)
        self.assertEqual(self.client.get(self.path("detail")).context["run"].pk, current.pk)
        foreign = recurring_run(self)
        wrong_parent = reverse("maintenance:run_detail", args=[maintenance.pk, foreign.pk])
        self.assertEqual(self.client.get(wrong_parent).status_code, 404)

    def test_main_state_filter_uses_latest_run_not_closed_history(self):
        self.client.force_login(self.technician)
        next_run(self, self.previous)
        closed = self.client.get(reverse("maintenance:list"), {"state": "CANCELADO"})
        self.assertNotContains(closed, "Preventivo de prueba")
        pending = self.client.get(reverse("maintenance:list"), {"state": "PENDIENTE_ATENCION"})
        self.assertContains(pending, "Preventivo de prueba")

    def test_history_filter_and_pagination(self):
        self.client.force_login(self.technician)
        previous = self.previous
        for _ in range(21):
            previous = next_run(self, previous)
            cancel_run(self, previous)
        response = self.client.get(self.path("executions"))
        self.assertEqual(response.context["page_obj"].paginator.count, 22)
        self.assertEqual(len(response.context["page_obj"]), 20)
        self.assertEqual(
            len(self.client.get(self.path("executions"), {"page": 2}).context["page_obj"]), 2
        )
        self.assertContains(
            self.client.get(self.path("executions"), {"state": "COMPLETADO"}), "No hay ejecuciones"
        )

    def test_calendar_pagination_and_latest_completion_links(self):
        self.client.force_login(self.admin)
        devices = [self.device]
        for index in range(20):
            devices.append(
                save_device(actor=self.admin, data=device_data(self, name=f"Equipo {index}"))
            )
        record = recurring_run(self, devices)
        finish_run(self, record)
        path = reverse("maintenance:due_dates", args=[record.maintenance_id])
        response = self.client.get(path)
        self.assertEqual(len(response.context["page_obj"]), 20)
        self.assertEqual(len(self.client.get(path, {"page": 2}).context["page_obj"]), 1)
        self.assertContains(
            response, reverse("maintenance:run_detail", args=[record.maintenance_id, record.pk])
        )

    def test_events_can_be_scoped_to_one_cycle(self):
        self.client.force_login(self.technician)
        current = next_run(self, self.previous)
        path = self.path("history")
        response = self.client.get(path, {"run": current.pk})
        self.assertContains(response, "Siguiente ejecución creada")
        self.assertNotContains(response, "Mantenimiento cancelado")
        self.assertEqual(response.context["selected_run"].pk, current.pk)
        other = recurring_run(self)
        for value in (other.pk, "invalid", "99999999999999999999999"):
            self.assertEqual(self.client.get(path, {"run": value}).status_code, 404)

    def test_unique_calendar_explains_absence_of_recurrence(self):
        self.client.force_login(self.technician)
        unique = make_run(self)
        response = self.client.get(reverse("maintenance:due_dates", args=[unique.maintenance_id]))
        self.assertContains(response, "Este mantenimiento es único")

    def test_legacy_invalid_interval_reports_error_instead_of_server_failure(self):
        record = recurring_run(self, base_date=date(1, 1, 1))
        finish_run(self, record)
        Maintenance.objects.filter(pk=record.maintenance_id).update(interval_value=100000)
        self.client.force_login(self.admin)
        for name in ("due_dates", "next_run"):
            response = self.client.get(reverse(f"maintenance:{name}", args=[record.maintenance_id]))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Revise la configuración de fechas")

    def test_csrf_methods_and_escaped_names_on_new_views(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.technician)
        self.assertEqual(client.post(self.path("next_run"), self.payload()).status_code, 403)
        client.get(self.path("next_run"))
        response = client.post(
            self.path("next_run"),
            self.payload(csrfmiddlewaretoken=client.cookies["csrftoken"].value),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            client.delete(
                self.path("next_run"), HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value
            ).status_code,
            405,
        )
        self.assertEqual(
            client.post(
                self.path("executions"), {}, HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value
            ).status_code,
            405,
        )
        self.client.force_login(self.admin)
        Device.objects.filter(pk=self.device.pk).update(name="<script>alert(1)</script>")
        response = self.client.get(self.path("due_dates"))
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertIn("no-store", response["Cache-Control"])
