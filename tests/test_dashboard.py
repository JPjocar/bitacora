from datetime import UTC, date, datetime, timedelta
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.assets.models import Device
from apps.assets.services import save_device
from apps.dashboard.forms import DashboardFilters
from apps.dashboard.reports import safe_cell
from apps.dashboard.selectors import dashboard_data
from apps.maintenance.execution import take_maintenance
from apps.maintenance.models import MaintenanceRun
from apps.notifications.models import Notification

from .asset_helpers import device_data, setup_assets
from .execution_helpers import make_run, operate
from .recurrence_helpers import cancel_run, finish_run, next_run, recurring_run


class DashboardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        setup_assets(cls)
        cls.second = save_device(actor=cls.admin, data=device_data(cls, name="Segundo"))

    def data(self, **filters):
        return dashboard_data({"section": "deadlines", **filters})

    def test_inventory_group_counts_and_unconfigured(self):
        recurring_run(self)
        data = self.data()
        self.assertEqual(data["inventory_count"], 2)
        self.assertEqual(data["unconfigured_count"], 1)
        self.assertEqual(list(data["by_kind"])[0]["total"], 2)
        self.assertEqual(list(data["by_location"])[0]["total"], 2)

    def test_unique_maintenance_does_not_count_as_periodic_configuration(self):
        make_run(self)
        self.assertEqual(self.data()["unconfigured_count"], 2)

    def test_archived_and_withdrawn_inventory_retained_but_not_preventive_candidates(self):
        self.device.is_active = False
        self.device.save(update_fields=["is_active"])
        self.second.status = Device.Status.WITHDRAWN
        self.second.save(update_fields=["status"])
        data = self.data()
        self.assertEqual(data["inventory_count"], 2)
        self.assertEqual(data["unconfigured_count"], 0)

    def test_group_run_counted_once_with_multiple_participants(self):
        make_run(self, devices=[self.device, self.second])
        counts = {item["label"]: item["count"] for item in self.data()["run_counts"]}
        self.assertEqual(counts["Pendiente de atención"], 1)

    def test_actual_completion_anchors_each_device_independently(self):
        run = recurring_run(self, [self.device, self.second], base_date=date(2026, 8, 1))
        finish_run(self, run, dates={self.device.pk: timezone.localdate()})
        rows = self.data()["rows"]
        by_device = {row.target.device_id: row for row in rows}
        self.assertEqual(by_device[self.second.pk].due_date, date(2026, 10, 1))
        self.assertGreater(by_device[self.device.pk].due_date, timezone.localdate())
        self.assertEqual(rows[0].target.device_id, self.second.pk)
        self.assertEqual(self.data()["omission_count"], 1)

    def test_omission_stays_pending_in_new_cycle_until_device_is_completed(self):
        run = recurring_run(self, [self.device, self.second], base_date=date(2026, 8, 1))
        finish_run(self, run, dates={self.device.pk: timezone.localdate()})
        second = next_run(self, run)
        self.assertEqual(self.data()["omission_count"], 1)
        finish_run(self, second, dates={self.second.pk: timezone.localdate()})
        omissions = self.data(section="omissions")["rows"]
        self.assertEqual(len(omissions), 1)
        self.assertEqual(omissions[0].device_id, self.device.pk)
        self.assertEqual(omissions[0].omitted_cycle, 2)

    def test_one_off_due_disappears_after_completion(self):
        run = make_run(self)
        self.assertEqual(self.data()["today_count"], 1)
        finish_run(self, run)
        self.assertEqual(self.data()["today_count"], 0)

    def test_cancelled_unique_excluded_periodic_stays_due(self):
        one = make_run(self)
        periodic = recurring_run(self, base_date=date(2026, 8, 1))
        cancel_run(self, one)
        cancel_run(self, periodic)
        self.assertEqual(len(self.data()["rows"]), 1)
        self.assertEqual(self.data()["overdue_count"], 1)

    def test_due_window_boundaries(self):
        run = recurring_run(self, base_date=date(2026, 10, 1))
        for day, key in [
            (date(2026, 11, 23), None),
            (date(2026, 11, 24), "soon_count"),
            (date(2026, 12, 1), "today_count"),
            (date(2026, 12, 2), "overdue_count"),
        ]:
            data = dashboard_data({"section": "deadlines"}, today=day)
            self.assertEqual(
                sum(data[name] for name in ["soon_count", "today_count", "overdue_count"]),
                int(key is not None),
            )
            if key:
                self.assertEqual(data[key], 1)
        self.assertEqual(run.maintenance.runs.count(), 1)

    def test_search_location_type_status_and_archive_filters(self):
        self.assertEqual(self.data(q=self.device.code.lower())["inventory_count"], 1)
        self.assertEqual(self.data(q="Segundo")["inventory_count"], 1)
        self.assertEqual(self.data(location=self.destination)["inventory_count"], 0)
        self.assertEqual(self.data(kind="LAPTOP")["inventory_count"], 0)
        self.assertEqual(self.data(status=Device.Status.WITHDRAWN)["inventory_count"], 0)
        self.assertEqual(self.data(active="no")["inventory_count"], 0)

    def test_date_filter_applies_to_closure_not_open_run_creation(self):
        finished = make_run(self)
        finish_run(self, finished)
        pending = make_run(self)
        data = self.data(section="runs", start=timezone.localdate() + timedelta(days=1))
        self.assertEqual(list(data["rows"].values_list("pk", flat=True)), [pending.pk])
        counts = {item["label"]: item["count"] for item in data["run_counts"]}
        self.assertEqual(counts["Completado"], 0)

    @patch("django.utils.timezone.now", return_value=datetime(2026, 11, 6, 2, tzinfo=UTC))
    def test_closure_period_uses_lima_date_at_utc_boundary(self, _now):
        run = make_run(self)
        finish_run(self, run)
        self.client.force_login(self.admin)
        exported = self.client.get(reverse("dashboard:csv"), {"section": "runs"})
        self.assertIn("2026-11-05T21:00:00-05:00", exported.content.decode("utf8"))
        self.assertEqual(
            self.data(section="runs", start=date(2026, 11, 5), end=date(2026, 11, 5))[
                "rows"
            ].count(),
            1,
        )
        self.assertEqual(self.data(section="runs", start=date(2026, 11, 6))["rows"].count(), 0)

    def test_run_state_filter(self):
        run = make_run(self)
        operate(take_maintenance, self, run)
        self.assertEqual(
            self.data(section="runs", run_state=MaintenanceRun.State.PENDING)["rows"].count(), 0
        )
        self.assertEqual(
            self.data(section="runs", run_state=MaintenanceRun.State.ASSIGNED)["rows"].count(), 1
        )

    def test_invalid_filters_do_not_export_unfiltered_data(self):
        self.client.force_login(self.admin)
        for params in [
            {"start": "2026-12-01", "end": "2026-01-01"},
            {"kind": "inventado"},
            {"location": "999999"},
            {"section": "otro"},
        ]:
            self.assertFalse(DashboardFilters(params).is_valid())
            self.assertEqual(self.client.get(reverse("dashboard:csv"), params).status_code, 400)

    def test_all_tables_render_and_exports_share_scope(self):
        make_run(self)
        self.client.force_login(self.technician)
        for section in ["deadlines", "runs", "unconfigured", "omissions", "devices"]:
            with self.subTest(section=section):
                response = self.client.get(reverse("dashboard:panel"), {"section": section})
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'id="dashboard-results"')
                response = self.client.get(reverse("dashboard:print"), {"section": section})
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Imprimir del navegador")
        response = self.client.get(
            reverse("dashboard:csv"), {"section": "devices", "q": self.device.code}
        )
        self.assertTrue(response.content.startswith(b"\xef\xbb\xbf"))
        text = response.content.decode("utf-8-sig")
        self.assertIn(self.device.code, text)
        self.assertNotIn(self.second.code, text)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("no-store", response["Cache-Control"])

    def test_htmx_fragment_and_invalid_filters(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("dashboard:panel"), HTTP_HX_REQUEST="true")
        self.assertNotContains(response, "<!doctype")
        self.assertContains(response, 'id="dashboard-results"', count=1)
        response = self.client.get(
            reverse("dashboard:panel"), {"end": "incorrecto"}, HTTP_HX_REQUEST="true"
        )
        self.assertContains(response, "Revise los filtros")

    def test_csv_formula_defense_and_html_escaping(self):
        self.device.name = '=HYPERLINK("https://example.invalid")<script>alert(1)</script>'
        self.device.save(update_fields=["name"])
        self.client.force_login(self.admin)
        response = self.client.get(reverse("dashboard:csv"), {"section": "devices"})
        self.assertIn("'=HYPERLINK", response.content.decode("utf8"))
        response = self.client.get(reverse("dashboard:print"), {"section": "devices"})
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, "&lt;script&gt;")
        for value in ["=1+1", " +1", "\t=1", "@SUM(1)", "-2", "\ntexto"]:
            self.assertTrue(safe_cell(value).startswith("'"))

    def test_report_limit_rejects_instead_of_truncating(self):
        self.client.force_login(self.admin)
        with patch("apps.dashboard.views.REPORT_LIMIT", 1):
            self.assertEqual(
                self.client.get(reverse("dashboard:csv"), {"section": "devices"}).status_code, 400
            )

    def test_invalid_legacy_date_is_visible_and_csv_does_not_silently_omit_it(self):
        recurring_run(self)
        self.client.force_login(self.admin)
        with patch(
            "apps.dashboard.selectors.schedule_row", side_effect=ValidationError("Fecha inválida")
        ):
            self.assertContains(self.client.get(reverse("dashboard:panel")), "fechas inválidas")
            self.assertEqual(self.client.get(reverse("dashboard:csv")).status_code, 400)

    def test_teachers_cannot_access_any_dashboard_route(self):
        self.client.force_login(self.teacher)
        for name in ["panel", "csv", "print"]:
            self.assertEqual(self.client.get(reverse(f"dashboard:{name}")).status_code, 403)

    def test_anonymous_redirect_and_dashboard_get_does_not_write(self):
        self.assertEqual(self.client.get(reverse("dashboard:panel")).status_code, 302)
        make_run(self)
        count = Notification.objects.count()
        self.client.force_login(self.admin)
        with CaptureQueriesContext(connection) as queries:
            self.assertEqual(self.client.get(reverse("dashboard:panel")).status_code, 200)
        self.assertFalse(
            any(
                query["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
                for query in queries
            )
        )
        self.assertEqual(Notification.objects.count(), count)

    def test_pagination_twenty_rows_and_query_count_does_not_grow_per_device(self):
        # Retained synthetic data; test the projection without per-device selector calls.
        for number in range(20):
            save_device(actor=self.admin, data=device_data(self, name=f"Sintético {number}"))
        run = recurring_run(self, list(Device.objects.all()))
        with CaptureQueriesContext(connection) as queries:
            data = self.data()
            self.assertEqual(len(data["rows"]), 22)
        self.assertLessEqual(len(queries), 8)
        self.client.force_login(self.admin)
        response = self.client.get(reverse("dashboard:panel"))
        self.assertEqual(len(response.context["page_obj"]), 20)
        self.assertEqual(run.participants.count(), 22)
