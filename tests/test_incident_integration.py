from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from django.db import IntegrityError, connection, transaction
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.assets.services import move_device, save_device
from apps.dashboard.selectors import dashboard_data
from apps.incidents.models import Incident
from apps.incidents.services import close_incident, take_incident
from apps.notifications.models import Notification

from .asset_helpers import device_data, setup_assets
from .incident_helpers import act, report
from .recurrence_helpers import recurring_run


class IncidentIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        setup_assets(cls)
        cls.second = save_device(actor=cls.admin, data=device_data(cls, name="Segundo equipo"))

    def data(self, **filters):
        return dashboard_data({"section": "incidents", **filters}, include_incidents=True)

    def test_dashboard_counts_incidents_and_distinct_recurrent_devices(self):
        first = report(self)
        report(self)
        report(self, device_id=self.second.pk)
        act(self, take_incident, first)
        data = self.data()
        counts = {item["label"]: item["count"] for item in data["incident_counts"]}
        self.assertEqual(counts["Pendiente de atención"], 2)
        self.assertEqual(counts["En atención"], 1)
        self.assertEqual(counts["Cerrada"], 0)
        self.assertEqual(data["repeated_incident_count"], 1)
        rows = self.data(section="recurrent_incidents")["rows"]
        self.assertEqual(rows.get().pk, self.device.pk)
        self.assertEqual(rows.get().incident_count, 2)

    def test_invalid_duplicate_reports_are_excluded_from_recurrence(self):
        report(self)
        duplicate = report(self)
        act(
            self,
            close_incident,
            duplicate,
            actor=self.admin,
            outcome="INVALIDA_DUPLICADA",
            summary="Reporte duplicado",
            reason="Revisión administrativa",
        )
        self.assertEqual(self.data()["repeated_incident_count"], 0)
        self.assertEqual(self.data()["rows"].count(), 2)

    def test_incident_period_filters_closures_and_keeps_open_work(self):
        first = report(self)
        pending = report(self)
        act(self, take_incident, first)
        act(self, close_incident, first, outcome="SOLUCIONADA", summary="Falla atendida")
        data = self.data(start=timezone.localdate() + timedelta(days=1))
        self.assertEqual(list(data["rows"].values_list("pk", flat=True)), [pending.pk])
        self.assertEqual(data["repeated_incident_count"], 0)

    def test_device_and_incident_state_filters_apply_to_incident_metrics(self):
        first = report(self)
        report(self, device_id=self.second.pk)
        act(self, take_incident, first)
        self.assertEqual(self.data(q=self.device.code)["rows"].get().pk, first.pk)
        self.assertEqual(self.data(incident_state="EN_ATENCION")["rows"].get().pk, first.pk)
        self.assertEqual(self.data(location=self.destination)["rows"].count(), 0)
        self.assertEqual(self.data(kind="LAPTOP")["rows"].count(), 0)

    def test_operator_can_export_both_new_sections_and_teacher_cannot(self):
        report(self, symptoms='=HYPERLINK("https://example.invalid")')
        report(self)
        self.client.force_login(self.technician)
        for section in ["incidents", "recurrent_incidents"]:
            response = self.client.get(reverse("dashboard:panel"), {"section": section})
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Incidencias")
            response = self.client.get(reverse("dashboard:csv"), {"section": section})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.content.startswith(b"\xef\xbb\xbf"))
            self.assertEqual(
                self.client.get(reverse("dashboard:print"), {"section": section}).status_code, 200
            )
        response = self.client.get(reverse("dashboard:csv"), {"section": "incidents"})
        self.assertIn("'=HYPERLINK", response.content.decode("utf8"))
        self.client.force_login(self.teacher)
        self.assertEqual(
            self.client.get(reverse("dashboard:csv"), {"section": "incidents"}).status_code, 403
        )

    def test_user_without_full_incident_permission_gets_no_dashboard_incident_data(self):
        from django.contrib.auth.models import Permission

        from .helpers import create_user

        user = create_user("consulta_parcial")
        for app, code in [("assets", "view_device"), ("maintenance", "view_maintenance")]:
            user.user_permissions.add(
                Permission.objects.get(content_type__app_label=app, codename=code)
            )
        report(self, symptoms="Incidencia reservada")
        self.client.force_login(user)
        self.assertNotContains(self.client.get(reverse("dashboard:panel")), "Incidencia reservada")
        self.assertNotContains(
            self.client.get(reverse("dashboard:panel")), "Equipos con incidencias recurrentes"
        )
        self.assertEqual(
            self.client.get(reverse("dashboard:csv"), {"section": "incidents"}).status_code, 400
        )

    def test_movements_during_attention_do_not_close_or_release_incidents(self):
        incident = report(self)
        act(self, take_incident, incident)
        move_device(
            actor=self.technician,
            device_id=self.device.pk,
            destination_id=self.destination.pk,
            expected_version=self.device.version,
            reason="Traslado físico",
            effective_at=timezone.now(),
        )
        incident.refresh_from_db()
        self.assertEqual(incident.state, Incident.State.ATTENDING)
        self.assertEqual(incident.responsible_id, self.technician.pk)
        self.assertEqual(incident.events.count(), 2)

    def test_existing_incident_can_be_closed_after_archiving_device(self):
        incident = report(self)
        act(self, take_incident, incident)
        self.device.is_active = False
        self.device.save(update_fields=["is_active"])
        act(
            self,
            close_incident,
            incident,
            outcome="SOLUCIONADA",
            summary="Verificado antes del archivo",
        )
        incident.refresh_from_db()
        self.assertEqual(incident.state, Incident.State.CLOSED)

    def test_notification_source_constraint_rejects_mixed_modules(self):
        incident = report(self)
        run = recurring_run(self)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Notification.objects.create(
                recipient=self.teacher,
                event=run.events.first(),
                incident_event=incident.events.first(),
                event_key="mixed:test",
                kind="INC_NEW",
                title="Inválido",
                description="Inválido",
            )

    @patch("django.utils.timezone.now", return_value=datetime(2026, 11, 6, 2, tzinfo=UTC))
    def test_incident_report_date_filter_uses_lima_not_utc(self, _now):
        report(self)
        self.client.force_login(self.teacher)
        url = reverse("incidents:list")
        response = self.client.get(url, {"start": "2026-11-05", "end": "2026-11-05"})
        self.assertEqual(response.context["page_obj"].paginator.count, 1)
        self.assertEqual(
            self.client.get(url, {"start": "2026-11-06"}).context["page_obj"].paginator.count, 0
        )

    def test_device_history_pagination_is_independent_and_query_count_bounded(self):
        for number in range(12):
            report(self, symptoms=f"Síntoma {number}")
        self.client.force_login(self.admin)
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(
                reverse("assets:detail", args=[self.device.public_id]), {"incident_page": 2}
            )
        self.assertEqual(len(response.context["incident_history"]), 2)
        self.assertLessEqual(len(queries), 20)
