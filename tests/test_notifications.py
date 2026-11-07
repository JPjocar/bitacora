from datetime import date, timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import reverse

from apps.accounts.roles import TECHNICIAN
from apps.maintenance.execution import release_maintenance, take_maintenance
from apps.maintenance.models import MaintenanceEvent
from apps.maintenance.services import save_maintenance, template_data
from apps.notifications.models import Notification
from apps.notifications.services import (
    generate_for_maintenance,
    handle_maintenance_event,
    mark_read,
    recipients,
)

from .asset_helpers import setup_assets
from .execution_helpers import make_run, operate
from .helpers import create_user
from .recurrence_helpers import cancel_run, finish_run, next_run, recurring_run


class NotificationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        setup_assets(cls)

    def mine(self, **kwargs):
        return Notification.objects.filter(recipient=self.technician, **kwargs)

    def test_creation_notifies_only_active_authorized_business_roles(self):
        inactive = create_user("inactivo", TECHNICIAN, is_active=False)
        outsider = create_user("sin_rol", is_superuser=True)
        run = make_run(self)
        notices = Notification.objects.filter(event__run=run)
        self.assertCountEqual(
            notices.values_list("recipient_id", flat=True), [self.admin.pk, self.technician.pk]
        )
        self.assertFalse(notices.filter(recipient__in=[inactive, outsider, self.teacher]).exists())
        self.assertEqual(
            self.mine().get().get_absolute_url(),
            reverse("maintenance:run_detail", args=[run.maintenance_id, run.pk]),
        )

    def test_recipients_require_both_permissions_and_are_deduplicated(self):
        self.technician.groups.add(Group.objects.get(name="Administrador"))
        self.assertEqual([user.pk for user in recipients()].count(self.technician.pk), 1)
        permission = Permission.objects.get(
            content_type__app_label="notifications", codename="view_notification"
        )
        for group in self.technician.groups.all():
            group.permissions.remove(permission)
        self.assertNotIn(self.technician.pk, [user.pk for user in recipients()])

    def test_same_event_is_idempotent_and_preserves_read(self):
        run = make_run(self)
        event = run.events.get()
        notice = self.mine().get()
        mark_read(actor=self.technician, notice_id=notice.pk)
        read_at = self.mine().get().read_at
        self.assertEqual(handle_maintenance_event(event), 0)
        self.assertEqual(self.mine().count(), 1)
        self.assertEqual(self.mine().get().read_at, read_at)

    def test_every_release_notifies_again_and_resolves_old_availability(self):
        run = make_run(self)
        for cycle in range(2):
            operate(take_maintenance, self, run)
            self.assertFalse(self.mine(resolved_at=None).exists())
            operate(release_maintenance, self, run, reason="Equipo aún no disponible")
            self.assertEqual(self.mine(resolved_at=None).count(), 1)
            self.assertEqual(self.mine(kind="RELEASED").count(), cycle + 1)
        self.assertEqual(self.mine().count(), 3)

    def test_cancel_resolves_availability_without_deleting_it(self):
        run = make_run(self)
        cancel_run(self, run)
        self.assertEqual(self.mine().count(), 1)
        self.assertIsNotNone(self.mine().get().resolved_at)

    def test_new_cycle_creates_a_distinct_available_notice(self):
        run = recurring_run(self)
        cancel_run(self, run)
        second = next_run(self, run)
        self.assertEqual(self.mine(kind="AVAILABLE").count(), 2)
        self.assertEqual(self.mine(resolved_at=None).get().event.run_id, second.pk)

    def test_date_phases_deduplicate_and_resolve_prior_phase(self):
        run = recurring_run(self, base_date=date(2026, 10, 1))
        due = date(2026, 12, 1)
        for day, kind in [
            (due - timedelta(days=7), "SOON"),
            (due, "TODAY"),
            (due + timedelta(days=1), "OVERDUE"),
        ]:
            generate_for_maintenance(run.maintenance_id, today=day)
            self.assertEqual(generate_for_maintenance(run.maintenance_id, today=day), 0)
            self.assertEqual(self.mine(target__isnull=False, resolved_at=None).get().kind, kind)
        generate_for_maintenance(run.maintenance_id, today=due + timedelta(days=9))
        self.assertEqual(self.mine(kind="OVERDUE").count(), 1)
        self.assertEqual(self.mine(target__isnull=False).count(), 3)

    def test_no_date_notice_before_seven_day_window(self):
        run = recurring_run(self, base_date=date(2026, 10, 1))
        generate_for_maintenance(run.maintenance_id, today=date(2026, 11, 23))
        self.assertFalse(self.mine(target__isnull=False).exists())

    def test_one_off_due_and_completed_notice_reconciliation(self):
        run = make_run(self)
        generate_for_maintenance(run.maintenance_id)
        self.assertEqual(self.mine(kind="TODAY", resolved_at=None).count(), 1)
        finish_run(self, run)
        generate_for_maintenance(run.maintenance_id)
        self.assertFalse(self.mine(target__isnull=False, resolved_at=None).exists())

    def test_cancelled_one_off_has_no_due_alert(self):
        run = make_run(self)
        cancel_run(self, run)
        generate_for_maintenance(run.maintenance_id)
        self.assertFalse(self.mine(target__isnull=False).exists())

    def test_inactive_or_withdrawn_device_clears_due_notices(self):
        run = make_run(self)
        generate_for_maintenance(run.maintenance_id)
        self.device.is_active = False
        self.device.save(update_fields=["is_active"])
        generate_for_maintenance(run.maintenance_id)
        self.assertFalse(self.mine(target__isnull=False, resolved_at=None).exists())

    def test_configuration_change_replaces_due_key_without_mutating_old_notice(self):
        run = recurring_run(self, base_date=date(2026, 10, 1))
        generate_for_maintenance(run.maintenance_id, today=date(2026, 12, 1))
        before = self.mine(kind="TODAY").get()
        maintenance = run.maintenance
        save_maintenance(
            actor=self.admin,
            maintenance_id=maintenance.pk,
            expected_version=maintenance.version,
            data={"interval_value": 3},
            device_ids=[self.device.pk],
            tasks=template_data(maintenance),
            reason="Ampliar intervalo vigente",
        )
        generate_for_maintenance(maintenance.pk, today=date(2026, 12, 1))
        before.refresh_from_db()
        self.assertEqual(before.due_on, date(2026, 12, 1))
        self.assertIsNotNone(before.resolved_at)

    def test_completion_changes_live_due_without_rewriting_historical_notice(self):
        run = recurring_run(self, base_date=date(2026, 8, 1))
        generate_for_maintenance(run.maintenance_id)
        notice = self.mine(kind="OVERDUE").get()
        finish_run(self, run)
        generate_for_maintenance(run.maintenance_id)
        notice.refresh_from_db()
        self.assertEqual(notice.due_on, date(2026, 10, 1))
        self.assertIsNotNone(notice.resolved_at)

    def test_command_backfills_pending_legacy_events_only_and_is_idempotent(self):
        with patch("apps.notifications.services.handle_maintenance_event"):
            pending = make_run(self)
            closed = make_run(self)
        cancel_run(self, closed)
        output = StringIO()
        call_command("generate_notifications", stdout=output)
        first = Notification.objects.count()
        call_command("generate_notifications", stdout=StringIO())
        self.assertEqual(Notification.objects.count(), first)
        self.assertTrue(self.mine(event__run=pending).exists())
        self.assertFalse(self.mine(event__run=closed).exists())

    def test_business_transaction_rolls_back_when_delivery_fails(self):
        count = MaintenanceEvent.objects.count()
        with patch(
            "apps.notifications.services._deliver", side_effect=RuntimeError("fallo simulado")
        ):
            with self.assertRaises(RuntimeError):
                make_run(self)
        self.assertEqual(MaintenanceEvent.objects.count(), count)
        self.assertFalse(Notification.objects.exists())

    def test_database_unique_source_and_immutable_content(self):
        make_run(self)
        notice = self.mine().get()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Notification.objects.create(
                recipient=self.technician,
                event=notice.event,
                kind=notice.kind,
                event_key=notice.event_key,
                title="Duplicado",
                description="Duplicado",
            )
        with self.assertRaises(IntegrityError), transaction.atomic():
            Notification.objects.create(
                recipient=self.technician,
                kind="TODAY",
                event=notice.event,
                event_key="inválido",
                title="Inválido",
                description="Inválido",
            )
        with self.assertRaises(ValidationError):
            Notification.objects.filter(pk=notice.pk).update(title="Otro")
        notice.description = "Otro"
        with self.assertRaises(ValidationError):
            notice.save()
        with self.assertRaises(ValidationError):
            notice.delete()

    def test_inbox_counter_and_get_are_read_only(self):
        make_run(self)
        self.client.force_login(self.technician)
        self.assertContains(self.client.get(reverse("notifications:inbox")), "Sin leer")
        response = self.client.get(reverse("notifications:counter"), HTTP_HX_REQUEST="true")
        self.assertContains(response, "every 30s")
        self.assertContains(response, "1 sin leer")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIsNone(self.mine().get().read_at)

    def test_open_marks_read_only_own_notice_and_repeated_post_preserves_time(self):
        run = make_run(self)
        mine = self.mine().get()
        other = Notification.objects.get(recipient=self.admin)
        self.client.force_login(self.technician)
        self.assertEqual(
            self.client.get(reverse("notifications:read", args=[mine.pk])).status_code, 405
        )
        self.assertEqual(
            self.client.post(reverse("notifications:read", args=[other.pk])).status_code, 404
        )
        self.assertRedirects(
            self.client.post(reverse("notifications:read", args=[mine.pk])),
            reverse("maintenance:run_detail", args=[run.maintenance_id, run.pk]),
        )
        stamp = self.mine().get().read_at
        self.client.post(reverse("notifications:read", args=[mine.pk]))
        self.assertEqual(self.mine().get().read_at, stamp)
        other.refresh_from_db()
        self.assertIsNone(other.read_at)

    def test_teacher_can_receive_incident_notices_but_revoked_and_inactive_users_are_denied(self):
        for url in [reverse("notifications:inbox"), reverse("notifications:counter")]:
            self.client.force_login(self.teacher)
            self.assertEqual(self.client.get(url).status_code, 200)
        self.teacher.groups.clear()
        self.assertEqual(self.client.get(reverse("notifications:inbox")).status_code, 403)
        self.technician.is_active = False
        self.technician.save(update_fields=["is_active"])
        with self.assertRaises(PermissionDenied):
            mark_read(actor=self.technician)

    def test_csrf_and_bulk_read_are_scoped(self):
        make_run(self)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.technician)
        self.assertEqual(client.post(reverse("notifications:read_all")).status_code, 403)
        self.client.force_login(self.technician)
        self.assertEqual(self.client.post(reverse("notifications:read_all")).status_code, 302)
        self.assertFalse(self.mine(read_at=None, resolved_at=None).exists())
        self.assertTrue(Notification.objects.filter(recipient=self.admin, read_at=None).exists())

    def test_inbox_pagination(self):
        run = make_run(self)
        event = run.events.get()
        Notification.objects.bulk_create(
            [
                Notification(
                    recipient=self.technician,
                    event=event,
                    kind="AVAILABLE",
                    event_key=f"test:{i}",
                    title="Aviso sintético",
                    description="Paginación",
                )
                for i in range(21)
            ]
        )
        self.client.force_login(self.technician)
        response = self.client.get(reverse("notifications:inbox"))
        self.assertEqual(len(response.context["page_obj"]), 20)
        self.assertTrue(response.context["page_obj"].has_next())
