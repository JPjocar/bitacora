from datetime import UTC, date, datetime, timedelta
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth.models import Permission
from django.template import Context, Template
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone
from django.utils.text import Truncator

from apps.assets.forms import DeviceForm
from apps.assets.models import Device
from apps.assets.services import save_category, save_device
from apps.incidents.models import Incident
from apps.maintenance.dates import add_interval
from apps.maintenance.execution import release_maintenance, take_maintenance
from apps.maintenance.models import Maintenance, MaintenanceRun, MaintenanceRunDevice
from apps.maintenance.selectors import list_schedules
from apps.maintenance.services import save_maintenance, template_data
from apps.notifications.models import Notification
from apps.notifications.selectors import describe_context, with_context
from apps.notifications.services import generate_for_maintenance

from .asset_helpers import device_data, setup_assets
from .execution_helpers import make_run, operate
from .helpers import create_user
from .incident_helpers import act, report
from .recurrence_helpers import cancel_run, finish_run


class StatusPresentationTests(SimpleTestCase):
    def render(self, source, **context):
        return Template("{% load ui %}" + source).render(Context(context))

    def test_all_domain_states_keep_visible_labels_and_semantic_colors(self):
        for choices in (
            Device.Status.choices,
            MaintenanceRun.State.choices,
            MaintenanceRunDevice.Result.choices,
            Incident.State.choices,
            Incident.Outcome.choices,
        ):
            for value, label in choices:
                with self.subTest(state=value):
                    html = self.render("{% status_badge value %}", value=value)
                    self.assertIn("rounded-pill", html)
                    self.assertIn(label, html)
        self.assertIn("bg-danger-subtle", self.render("{% status_badge 'NO_REPARABLE' %}"))
        self.assertIn("bg-success-subtle", self.render("{% status_badge 'SOLUCIONADA' %}"))

    def test_active_green_inactive_red_and_task_statuses(self):
        for value, color, label in [(True, "success", "Activo"), (False, "danger", "Inactivo")]:
            html = self.render("{% status_badge value 'active' %}", value=value)
            self.assertIn(f"bg-{color}-subtle", html)
            self.assertIn(label, html)
        self.assertIn("Realizada", self.render("{% status_badge value 'task' %}", value=True))

    def test_custom_labels_and_unknown_values_remain_escaped(self):
        for source in ["{% status_badge value %}", "{% status_badge True 'active' label=value %}"]:
            html = self.render(source, value="<script>alert(1)</script>")
            self.assertNotIn("<script>", html)
            self.assertIn("&lt;script&gt;", html)

    def test_relative_deadlines_include_exact_date_and_priority(self):
        today = date(2026, 11, 8)
        for offset, label, color in [
            (-3, "Vencido hace 3 días", "danger"),
            (-1, "Vencido hace 1 día", "danger"),
            (0, "Hoy", "warning"),
            (1, "Mañana", "warning"),
            (7, "En 7 días", "warning"),
            (8, "En 8 días", "info"),
        ]:
            due = today + timedelta(days=offset)
            html = self.render("{% deadline due today=today %}", due=due, today=today)
            self.assertIn(label, html)
            self.assertIn(f"bg-{color}-subtle", html)
            self.assertIn(f'datetime="{due.isoformat()}"', html)

    def test_deadlines_use_lima_day_at_utc_midnight_and_allow_no_date(self):
        with patch("django.utils.timezone.now", return_value=datetime(2026, 11, 9, 2, tzinfo=UTC)):
            self.assertIn("Hoy", self.render("{% deadline due %}", due=date(2026, 11, 8)))
        self.assertEqual(self.render("{% deadline due %}", due=None).strip(), "")


class InterfaceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        setup_assets(cls)

    def test_commissioning_date_removed_from_form_and_detail_without_erasing_legacy_data(self):
        legacy_date = timezone.localdate() - timedelta(days=3)
        Device.objects.filter(pk=self.device.pk).update(commissioned_on=legacy_date)
        self.client.force_login(self.admin)
        self.assertNotIn("commissioned_on", DeviceForm().fields)
        for name in ("create", "edit", "detail"):
            args = [] if name == "create" else [self.device.public_id]
            response = self.client.get(reverse(f"assets:{name}", args=args))
            self.assertNotContains(response, 'name="commissioned_on"')
            # Existing audit labels are historical records, not editable fields.
            self.assertNotContains(response, '<dt class="col-sm-4">Puesta en servicio</dt>')
        response = self.client.post(
            reverse("assets:edit", args=[self.device.public_id]),
            {
                "name": self.device.name,
                "category": self.category.pk,
                "status": self.device.status,
                "is_active": "on",
                "version": self.device.version,
                "commissioned_on": "2026-01-01",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.device.refresh_from_db()
        self.assertEqual(self.device.commissioned_on, legacy_date)

    def test_grouped_navigation_preserves_links_and_role_permissions(self):
        cases = [
            (self.admin, True, True, True),
            (self.technician, True, True, False),
            (self.teacher, False, False, False),
        ]
        for actor, maintenance, locations, users in cases:
            with self.subTest(role=actor.username):
                self.client.force_login(actor)
                html = self.client.get(reverse("home")).content.decode()
                nav = html.split('<nav class="navbar', 1)[1].split("</nav>", 1)[0]
                self.assertIn('id="equipment-menu"', nav)
                self.assertIn('data-bs-toggle="dropdown"', nav)
                self.assertIn('aria-label="Bitacora · Inicio"', html)
                for name, visible in [
                    ("assets:list", True),
                    ("assets:scanner", True),
                    ("maintenance:list", maintenance),
                    ("locations:list", locations),
                    ("accounts:list", users),
                    ("accounts:roles", users),
                ]:
                    self.assertEqual(f'href="{reverse(name)}"' in nav, visible, name)

    def test_user_without_module_permissions_gets_no_empty_dropdown(self):
        outsider = create_user("sin_modulos")
        self.client.force_login(outsider)
        html = self.client.get(reverse("home")).content.decode()
        self.assertNotIn('id="equipment-menu"', html)
        self.assertNotIn('id="administration-menu"', html)

    def test_active_inactive_badges_on_lists_details_and_htmx(self):
        Device.objects.filter(pk=self.device.pk).update(is_active=False)
        self.client.force_login(self.admin)
        for url in [reverse("assets:list"), reverse("assets:detail", args=[self.device.public_id])]:
            html = self.client.get(url).content.decode()
            self.assertIn("bg-danger-subtle", html)
            self.assertIn("Inactivo", html)
            self.assertIn("bg-success-subtle", html)  # Operational despite being archived.
        response = self.client.get(reverse("assets:list"), HTTP_HX_REQUEST="true")
        self.assertNotContains(response, "<!doctype")
        self.assertContains(response, "bg-danger-subtle")

    def test_inactive_badges_on_accounts_categories_and_locations(self):
        self.teacher.is_active = self.category.is_active = self.origin.is_active = False
        for record in (self.teacher, self.category, self.origin):
            record.save(update_fields=["is_active"])
        self.client.force_login(self.admin)
        for name, args in [
            ("accounts:list", []),
            ("accounts:detail", [self.teacher.pk]),
            ("assets:categories", []),
            ("assets:category_detail", [self.category.pk]),
            ("locations:list", []),
            ("locations:detail", [self.origin.pk]),
        ]:
            with self.subTest(route=name):
                self.assertContains(self.client.get(reverse(name, args=args)), "bg-danger-subtle")

    def test_print_reports_share_statuses_and_csv_keeps_plain_values(self):
        make_run(self)
        report(self)
        self.client.force_login(self.admin)
        for section in ("devices", "runs", "incidents", "deadlines"):
            with self.subTest(section=section):
                response = self.client.get(reverse("dashboard:print"), {"section": section})
                self.assertContains(response, "status-badge")
                self.assertContains(response, "rounded-pill")
                csv = self.client.get(reverse("dashboard:csv"), {"section": section})
                self.assertEqual(csv.status_code, 200)
                self.assertNotContains(csv, "<span")

    def test_maintenance_responsible_full_name_and_release(self):
        self.technician.first_name, self.technician.last_name = "Ana", "Pérez"
        self.technician.save(update_fields=["first_name", "last_name"])
        run = make_run(self)
        self.client.force_login(self.technician)
        url = reverse("maintenance:list")
        self.assertContains(self.client.get(url), "Sin asignar")
        operate(take_maintenance, self, run)
        response = self.client.get(url, HTTP_HX_REQUEST="true")
        self.assertContains(response, "Ana Pérez")
        self.assertContains(response, "Asignado")
        operate(release_maintenance, self, run, reason="Disponible para otro técnico")
        self.assertContains(self.client.get(url), "Sin asignar")

    def test_completed_one_off_has_no_false_overdue_and_names_last_responsible(self):
        run = make_run(self)
        finish_run(self, run)
        self.client.force_login(self.technician)
        response = self.client.get(reverse("maintenance:list"))
        self.assertContains(response, "Sin vencimientos pendientes")
        self.assertContains(response, "Última ejecución cerrada")
        self.assertNotContains(response, "Vencido hace")

    def test_list_deadlines_render_tomorrow_and_overdue_with_counts(self):
        run = make_run(self)
        tomorrow = timezone.localdate() + timedelta(days=1)
        future = save_maintenance(
            actor=self.admin,
            data={"name": "Preventivo mañana", "planned_date": tomorrow, "is_recurring": False},
            device_ids=[self.device.pk],
            tasks=template_data(run.maintenance),
            creation_key=uuid4(),
        )
        self.client.force_login(self.technician)
        response = self.client.get(reverse("maintenance:list"))
        self.assertContains(response, "Hoy")
        self.assertContains(response, "Mañana")
        self.assertContains(response, tomorrow.strftime("%d/%m/%Y"))
        summary = list_schedules([future], today=tomorrow + timedelta(days=2))[future.pk]
        self.assertEqual(summary.overdue_count, 1)

    def test_list_names_current_user_when_full_name_is_empty(self):
        run = make_run(self)
        operate(take_maintenance, self, run)
        self.client.force_login(self.admin)
        response = self.client.get(reverse("maintenance:list"))
        self.assertContains(response, self.technician.username)
        self.assertNotContains(response, "Última ejecución cerrada")


class MaintenanceScheduleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        setup_assets(cls)
        cls.second = save_device(actor=cls.admin, data=device_data(cls, name="Segundo equipo"))

    def test_open_work_keeps_snapshot_after_configuration_change(self):
        run = make_run(self, recurring=True)
        original = run.participants.get().due_date
        maintenance = run.maintenance
        save_maintenance(
            actor=self.admin,
            maintenance_id=maintenance.pk,
            expected_version=maintenance.version,
            data={"interval_value": 4},
            device_ids=[self.device.pk],
            tasks=template_data(maintenance),
            reason="Cambiar periodicidad futura",
        )
        summary = list_schedules([maintenance])[maintenance.pk]
        self.assertEqual(summary.earliest_due, original)
        self.assertEqual(summary.equipment_count, 1)

    def test_archiving_does_not_hide_unfinished_existing_work(self):
        run = make_run(self)
        Device.objects.filter(pk=self.device.pk).update(is_active=False)
        summary = list_schedules([run.maintenance])[run.maintenance_id]
        self.assertEqual(summary.earliest_due, run.participants.get().due_date)

    def test_partial_group_uses_omitted_due_not_completed_device_date(self):
        today = timezone.localdate()
        run = make_run(
            self,
            devices=[self.device, self.second],
            recurring=True,
            base_date=today - timedelta(days=120),
        )
        original = run.participants.first().due_date
        finish_run(self, run, {self.device.pk: today})
        summary = list_schedules([run.maintenance], today=today)[run.maintenance_id]
        self.assertEqual(summary.earliest_due, original)
        self.assertEqual(summary.overdue_count, 1)
        self.assertEqual(summary.equipment_count, 2)

    def test_completed_group_keeps_individual_calendars(self):
        today = timezone.localdate()
        run = make_run(self, devices=[self.device, self.second], recurring=True)
        earlier = today - timedelta(days=2)
        finish_run(self, run, {self.device.pk: earlier, self.second.pk: today})
        summary = list_schedules([run.maintenance])[run.maintenance_id]
        self.assertEqual(summary.earliest_due, add_interval(earlier, 2, "MESES"))
        self.assertEqual(summary.overdue_count, 0)

    def test_cancelled_unique_has_no_pending_deadline(self):
        run = make_run(self)
        cancel_run(self, run)
        self.assertIsNone(list_schedules([run.maintenance])[run.maintenance_id].earliest_due)

    def test_cancelled_recurring_keeps_outstanding_deadline(self):
        run = make_run(self, recurring=True)
        due = run.participants.get().due_date
        cancel_run(self, run)
        self.assertEqual(list_schedules([run.maintenance])[run.maintenance_id].earliest_due, due)

    def test_queries_are_batched_for_multiple_maintenances(self):
        for _ in range(3):
            make_run(self, devices=[self.device, self.second], recurring=True)
        maintenances = list(Maintenance.objects.all())
        with self.assertNumQueries(2):
            summaries = list_schedules(maintenances)
        self.assertEqual(len(summaries), 3)
        self.assertTrue(all(summary.equipment_count == 2 for summary in summaries.values()))


class NoticeContextTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        setup_assets(cls)

    def test_existing_incident_notices_show_equipment_location_and_short_escaped_symptoms(self):
        symptoms = "<script>alert(1)</script> No enciende la máquina. " + "Detalle adicional. " * 30
        report(self, symptoms=symptoms)
        self.client.force_login(self.technician)
        before = list(Notification.objects.values())
        response = self.client.get(reverse("notifications:inbox"))
        self.assertContains(response, self.device.code)
        self.assertContains(response, self.device.name)
        self.assertContains(response, self.category.get_kind_display())
        self.assertContains(response, self.origin.name)
        self.assertContains(response, "Ver incidencia y marcar leída")
        self.assertNotContains(response, "Ver mantenimiento y marcar leída")
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertNotContains(response, symptoms)
        self.assertEqual(list(Notification.objects.values()), before)
        notice = response.context["page_obj"][0]
        self.assertEqual(notice.context["excerpt"], Truncator(symptoms).chars(160))

    def test_group_notice_has_device_count_and_mixed_types(self):
        router = save_category(actor=self.admin, data={"name": "Routers", "kind": "ROUTER"})
        second = save_device(actor=self.admin, data=device_data(self, category_id=router.pk))
        make_run(self, devices=[self.device, second])
        self.client.force_login(self.technician)
        response = self.client.get(reverse("notifications:inbox"))
        self.assertContains(response, "2 equipos")
        self.assertContains(response, "PC de escritorio")
        self.assertContains(response, "Router")
        self.assertContains(response, "Ver mantenimiento y marcar leída")

    def test_due_notice_shows_equipment_and_links_to_deadlines(self):
        run = make_run(self)
        generate_for_maintenance(run.maintenance_id)
        self.client.force_login(self.technician)
        response = self.client.get(reverse("notifications:inbox"))
        due_notice = next(item for item in response.context["page_obj"] if item.target_id)
        self.assertEqual(due_notice.context["action"], "Ver vencimiento")
        self.assertContains(response, "Hoy")
        self.assertIn(self.device.code, due_notice.context["equipment"])

    def test_notice_context_is_batched_and_does_not_read_per_notice(self):
        for _ in range(3):
            make_run(self)
        notices = with_context(Notification.objects.filter(recipient=self.technician))
        with self.assertNumQueries(2):
            contexts = [describe_context(notice) for notice in notices]
        self.assertEqual(len(contexts), 3)

    def test_closure_notice_for_teacher_shows_public_symptoms_without_internal_notes(self):
        from apps.incidents.services import add_note, close_incident, take_incident

        incident = report(self)
        act(self, take_incident, incident)
        act(self, add_note, incident, note="NOTA-INTERNA-SECRETA")
        act(self, close_incident, incident, outcome="SOLUCIONADA", summary="Conexión restablecida")
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("notifications:inbox"))
        self.assertContains(response, incident.symptoms)
        self.assertNotContains(response, "NOTA-INTERNA-SECRETA")

    def test_module_permission_revocation_hides_incident_context(self):
        report(self, symptoms="SINTOMA-RESTRINGIDO")
        permission = Permission.objects.get(
            content_type__app_label="incidents", codename="view_incident"
        )
        for group in self.technician.groups.all():
            group.permissions.remove(permission)
        self.client.force_login(self.technician)
        self.assertNotContains(
            self.client.get(reverse("notifications:inbox")), "SINTOMA-RESTRINGIDO"
        )
