from datetime import UTC, date, datetime, timedelta
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.assets.models import Device
from apps.assets.services import save_category, save_device
from apps.maintenance.execution import complete_device
from apps.maintenance.models import MaintenanceEvent, MaintenanceRun
from apps.maintenance.selectors import target_schedule
from apps.maintenance.services import MAX_TARGETS, save_maintenance, template_data

from .asset_helpers import device_data, setup_assets
from .execution_helpers import make_run, operate, progress, start_run
from .maintenance_helpers import task_data
from .recurrence_helpers import cancel_run, finish_run, next_run, recurring_run


class RecurrenceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        setup_assets(cls)
        cls.second = save_device(actor=cls.admin, data=device_data(cls, name="Segundo equipo"))
        cls.third = save_device(actor=cls.admin, data=device_data(cls, name="Tercer equipo"))

    def schedules(self, maintenance, **kwargs):
        return {row.target.device_id: row for row in target_schedule(maintenance, **kwargs)}

    def edit(self, maintenance, **kwargs):
        maintenance.refresh_from_db()
        return save_maintenance(
            **{
                "actor": self.admin,
                "maintenance_id": maintenance.pk,
                "expected_version": maintenance.version,
                "data": {},
                "device_ids": list(
                    maintenance.targets.filter(is_active=True).values_list("device_id", flat=True)
                ),
                "tasks": template_data(maintenance),
                "reason": "Cambio futuro autorizado",
                **kwargs,
            }
        )

    def test_initial_calendar_uses_base_not_creation_day_or_status(self):
        run = recurring_run(self)
        row = target_schedule(run.maintenance)[0]
        self.assertEqual(row.due_date, date(2026, 12, 1))
        self.assertIsNone(row.target.last_completed_on)
        self.assertFalse(row.selectable)
        self.assertEqual(row.target.open_run_id, run.pk)
        self.assertEqual(run.maintenance.runs.count(), 1)

    @patch("django.utils.timezone.now", return_value=datetime(2026, 11, 30, 17, tzinfo=UTC))
    def test_master_case_per_device_dates_and_omitted_overdue_selection(self, mock_now):
        run = recurring_run(self, [self.device, self.second, self.third])
        finish_run(
            self, run, {self.device.pk: date(2026, 11, 25), self.second.pk: date(2026, 11, 28)}
        )
        rows = self.schedules(run.maintenance, today=date(2026, 12, 2))
        self.assertEqual(rows[self.device.pk].due_date, date(2027, 1, 25))
        self.assertEqual(rows[self.second.pk].due_date, date(2027, 1, 28))
        self.assertEqual(rows[self.third.pk].due_date, date(2026, 12, 1))
        self.assertTrue(rows[self.third.pk].proposed)
        self.assertEqual(rows[self.third.pk].timing, "overdue")
        self.assertIsNone(rows[self.third.pk].target.last_completed_on)

    def test_calendar_timing_boundaries_do_not_create_runs(self):
        for delta, expected in ((-1, "overdue"), (0, "today"), (7, "soon"), (8, "later")):
            base = date(2026, 10, 1)
            run = recurring_run(self, base_date=base)
            cancel_run(self, run)
            due = date(2026, 12, 1)
            row = target_schedule(run.maintenance, today=due - timedelta(days=delta))[0]
            self.assertEqual(row.timing, expected)
            self.assertEqual(row.proposed, delta <= 7)
            self.assertEqual(run.maintenance.runs.count(), 1)

    def test_next_run_has_new_unassigned_clean_tasks_and_individual_due_snapshots(self):
        previous = recurring_run(self, [self.device, self.second])
        finish_run(self, previous)
        old_participants, old_tasks = (
            list(previous.participants.values()),
            list(previous.tasks.values()),
        )
        current = next_run(self, previous)
        self.assertEqual(current.number, 2)
        self.assertEqual(current.version, 1)
        self.assertEqual(current.state, MaintenanceRun.State.PENDING)
        self.assertIsNone(current.responsible)
        self.assertIsNone(current.started_at)
        self.assertEqual(current.notes, "")
        self.assertFalse(current.tasks.filter(completed=True).exists())
        self.assertFalse(current.tasks.filter(changed_at__isnull=False).exists())
        self.assertFalse(current.tasks.exclude(observation="").exists())
        self.assertEqual(current.tasks.filter(participant__isnull=True).count(), 1)
        self.assertEqual(current.participants.filter(result="SIN_FINALIZAR").count(), 2)
        self.assertEqual(list(previous.participants.values()), old_participants)
        self.assertEqual(list(previous.tasks.values()), old_tasks)
        rows = self.schedules(previous.maintenance)
        for participant in current.participants.all():
            self.assertEqual(participant.due_date, rows[participant.target.device_id].due_date)

    def test_cancelled_run_does_not_advance_calendar_or_reset_interval(self):
        previous = recurring_run(self)
        cancel_run(self, previous)
        due = target_schedule(previous.maintenance)[0].due_date
        current = next_run(self, previous)
        cancel_run(self, current)
        row = target_schedule(previous.maintenance)[0]
        self.assertEqual(row.due_date, due)
        self.assertIsNone(row.target.last_completed_on)
        self.assertEqual(previous.maintenance.interval_value, 2)

    def test_omitted_device_can_return_without_resetting_due(self):
        previous = recurring_run(self, [self.device, self.second])
        finish_run(self, previous, {self.device.pk: timezone.localdate()})
        target = previous.maintenance.targets.get(device=self.second)
        original = previous.participants.get(target=target).due_date
        current = next_run(self, previous, target_ids=[target.pk])
        self.assertEqual(current.participants.count(), 1)
        self.assertEqual(current.participants.get().due_date, original)
        self.assertEqual(previous.participants.get(target=target).result, "OMITIDO")

    def test_repeated_omissions_and_cancellations_keep_last_valid_completion(self):
        previous = recurring_run(self)
        finish_run(self, previous)
        due = target_schedule(previous.maintenance)[0].due_date
        current = next_run(self, previous)
        finish_run(self, current, {})
        after = next_run(self, current)
        cancel_run(self, after)
        self.assertEqual(target_schedule(previous.maintenance)[0].due_date, due)

    def test_only_closed_recurring_active_maintenance_can_open_next_run(self):
        previous = recurring_run(self)
        with self.assertRaises(ValidationError):
            next_run(self, previous)
        cancel_run(self, previous)
        self.edit(previous.maintenance, data={"is_active": False})
        with self.assertRaises(ValidationError):
            next_run(self, previous)
        unique = make_run(self)
        cancel_run(self, unique)
        with self.assertRaises(ValidationError):
            next_run(self, unique)

    def test_admin_and_technician_can_open_but_teacher_and_inactive_actor_cannot(self):
        for actor in (self.admin, self.technician):
            previous = recurring_run(self)
            cancel_run(self, previous)
            self.assertEqual(next_run(self, previous, actor=actor).events.get().actor, actor)
        previous = recurring_run(self)
        cancel_run(self, previous)
        with self.assertRaises(PermissionDenied):
            next_run(self, previous, actor=self.teacher)
        self.assertTrue(self.technician.has_perm("maintenance.create_next_run"))
        User.objects.filter(pk=self.technician.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            next_run(self, previous)

    def test_replay_and_stale_predecessor_cannot_duplicate_even_after_new_cycle_closes(self):
        previous = recurring_run(self)
        cancel_run(self, previous)
        current = next_run(self, previous)
        with self.assertRaises(ValidationError):
            next_run(self, previous)
        cancel_run(self, current)
        with self.assertRaises(ValidationError):
            next_run(self, previous)
        self.assertEqual(previous.maintenance.runs.count(), 2)

    def test_changed_configuration_rejects_old_form_version(self):
        previous = recurring_run(self)
        cancel_run(self, previous)
        old = previous.maintenance.version
        self.edit(previous.maintenance, data={"description": "Configuración futura"})
        with self.assertRaises(ValidationError):
            next_run(self, previous, expected_version=old)

    def test_foreign_inactive_duplicate_and_oversize_selections_are_rejected(self):
        previous = recurring_run(self)
        cancel_run(self, previous)
        foreign = recurring_run(self).maintenance.targets.get()
        own = previous.maintenance.targets.get()
        for selected in ([], [foreign.pk], [True], [own.pk, own.pk], [own.pk] * (MAX_TARGETS + 1)):
            with self.assertRaises(ValidationError):
                next_run(self, previous, target_ids=selected)
        for data in ({"is_active": False}, {"is_active": True, "status": Device.Status.WITHDRAWN}):
            Device.objects.filter(pk=self.device.pk).update(**data)
            with self.assertRaises(ValidationError):
                next_run(self, previous)

    def test_inactive_devices_remain_in_calendar_but_cannot_be_selected(self):
        previous = recurring_run(self)
        cancel_run(self, previous)
        Device.objects.filter(pk=self.device.pk).update(is_active=False)
        row = target_schedule(previous.maintenance)[0]
        self.assertFalse(row.selectable)
        self.assertEqual(row.target.device.pk, self.device.pk)

    def test_out_of_service_device_can_be_selected(self):
        previous = recurring_run(self)
        cancel_run(self, previous)
        Device.objects.filter(pk=self.device.pk).update(status=Device.Status.OUT_OF_SERVICE)
        self.assertEqual(next_run(self, previous).participants.count(), 1)

    def test_early_selection_requires_reason_and_due_selection_does_not(self):
        previous = recurring_run(self, base_date=timezone.localdate())
        cancel_run(self, previous)
        with self.assertRaises(ValidationError):
            next_run(self, previous, reason="")
        current = next_run(self, previous, reason="Revisión anticipada autorizada")
        self.assertEqual(
            current.events.get().changes["reason"]["después"], "Revisión anticipada autorizada"
        )
        with patch("django.utils.timezone.now", return_value=datetime(2027, 1, 1, 17, tzinfo=UTC)):
            due = recurring_run(self)
            cancel_run(self, due)
            self.assertEqual(next_run(self, due, reason="").number, 2)

    def test_future_template_changes_only_affect_next_cycle(self):
        previous = recurring_run(self)
        finish_run(self, previous)
        before = previous.configuration.copy(), list(previous.tasks.values())
        self.edit(
            previous.maintenance,
            data={"name": "Nombre futuro", "interval_value": 3},
            tasks=[task_data(name="Verificación futura")],
        )
        current = next_run(self, previous)
        self.assertEqual(current.configuration["name"], "Nombre futuro")
        self.assertEqual(current.tasks.get().name, "Verificación futura")
        self.assertFalse(current.tasks.get().completed)
        self.assertEqual((previous.configuration, list(previous.tasks.values())), before)

    def test_current_interval_changes_future_dates_without_rewriting_closed_copies(self):
        previous = recurring_run(self, [self.device, self.second])
        finish_run(self, previous, {self.device.pk: timezone.localdate()})
        old = list(previous.participants.values())
        changed = self.edit(
            previous.maintenance, data={"interval_value": 1, "base_date": date(2026, 9, 1)}
        )
        rows = self.schedules(changed)
        self.assertEqual(rows[self.second.pk].due_date, date(2026, 10, 1))
        self.assertEqual(list(previous.participants.values()), old)
        current = next_run(self, previous)
        for participant in current.participants.all():
            self.assertEqual(participant.due_date, rows[participant.target.device_id].due_date)

    def test_reactivated_subscription_keeps_completion_history(self):
        previous = recurring_run(self, [self.device, self.second])
        finish_run(self, previous)
        original = self.schedules(previous.maintenance)[self.device.pk]
        self.edit(previous.maintenance, device_ids=[self.second.pk])
        self.assertNotIn(self.device.pk, self.schedules(previous.maintenance))
        self.edit(previous.maintenance, device_ids=[self.device.pk, self.second.pk])
        restored = self.schedules(previous.maintenance)[self.device.pk]
        self.assertEqual(restored.target.pk, original.target.pk)
        self.assertEqual(restored.target.last_completed_on, original.target.last_completed_on)

    def test_latest_real_completion_is_used_instead_of_latest_recording_date(self):
        previous = recurring_run(self)
        finish_run(self, previous)
        first_due = target_schedule(previous.maintenance)[0].due_date
        current = next_run(self, previous)
        finish_run(self, current, {self.device.pk: timezone.localdate() - timedelta(days=10)})
        row = target_schedule(previous.maintenance)[0]
        self.assertEqual(row.due_date, first_due)
        self.assertEqual(row.target.last_completed_run_id, previous.pk)

    def test_calendar_uses_completed_device_even_before_group_is_closed(self):
        previous = recurring_run(self, [self.device, self.second])
        start_run(self, previous)
        participant = previous.participants.get(target__device=self.device)
        progress(self, previous, participant)
        operate(
            complete_device,
            self,
            previous,
            participant_id=participant.pk,
            device_executed_on=timezone.localdate(),
            verified=True,
            completion_summary="Trabajo válido",
        )
        self.assertEqual(
            self.schedules(previous.maintenance)[self.device.pk].target.last_completed_run_id,
            previous.pk,
        )
        with self.assertRaises(ValidationError):
            next_run(self, previous)

    def test_audit_failure_rolls_back_new_snapshots_and_number(self):
        previous = recurring_run(self)
        cancel_run(self, previous)
        with (
            patch.object(MaintenanceEvent.objects, "create", side_effect=RuntimeError("audit")),
            self.assertRaises(RuntimeError),
        ):
            next_run(self, previous)
        self.assertEqual(previous.maintenance.runs.count(), 1)
        self.assertEqual(next_run(self, previous).number, 2)

    def test_database_prevents_second_open_execution_and_nonpositive_number(self):
        previous = recurring_run(self)
        with self.assertRaises(IntegrityError), transaction.atomic():
            MaintenanceRun.objects.create(
                maintenance=previous.maintenance, number=2, configuration={}
            )
        with self.assertRaises(IntegrityError), transaction.atomic():
            MaintenanceRun.objects.create(
                maintenance=previous.maintenance, number=0, configuration={}
            )

    def test_configured_interval_overflow_is_rejected_against_last_completion(self):
        previous = recurring_run(self, base_date=date(1, 1, 1))
        finish_run(self, previous)
        old = previous.maintenance.interval_value
        with self.assertRaises(ValidationError):
            self.edit(previous.maintenance, data={"interval_value": 100000})
        previous.maintenance.refresh_from_db()
        self.assertEqual(previous.maintenance.interval_value, old)

    def test_no_per_target_queries_for_calendar(self):
        previous = recurring_run(self, [self.device, self.second, self.third])
        with self.assertNumQueries(1):
            rows = target_schedule(previous.maintenance)
            self.assertEqual(len(rows), 3)
            self.assertTrue(all(row.target.device.location.name for row in rows))

    def test_subset_uses_only_applicable_category_tasks_and_one_general_copy(self):
        router_category = save_category(
            actor=self.admin, data={"name": "Routers de recurrencia", "kind": "ROUTER"}
        )
        router = save_device(
            actor=self.admin, data=device_data(self, category_id=router_category.pk)
        )
        previous = make_run(
            self,
            devices=[self.device, router],
            recurring=True,
            tasks=[
                task_data(name="Revisar PC", category_id=self.category.pk),
                task_data(name="Revisar router", category_id=router_category.pk),
                task_data(name="Preparar área", scope="GRUPAL"),
            ],
        )
        finish_run(self, previous)
        target = previous.maintenance.targets.get(device=self.device)
        current = next_run(self, previous, target_ids=[target.pk])
        self.assertEqual(
            set(current.tasks.values_list("name", flat=True)), {"Revisar PC", "Preparar área"}
        )
        self.assertEqual(current.participants.count(), 1)
        self.assertTrue(previous.tasks.filter(name="Revisar router").exists())

    def test_changed_device_category_requires_new_applicable_template(self):
        previous = make_run(self, recurring=True, tasks=[task_data(category_id=self.category.pk)])
        finish_run(self, previous)
        category = save_category(
            actor=self.admin, data={"name": "Otra categoría de recurrencia", "kind": "OTROS"}
        )
        save_device(
            actor=self.admin,
            device_id=self.device.pk,
            expected_version=self.device.version,
            data={"category_id": category.pk},
        )
        with self.assertRaises(ValidationError):
            next_run(self, previous)
        self.assertEqual(previous.maintenance.runs.count(), 1)
