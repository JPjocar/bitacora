from datetime import date, datetime
from io import StringIO
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import User
from apps.assets.models import Device
from apps.assets.services import move_device, save_category, save_device
from apps.maintenance.dates import add_interval
from apps.maintenance.models import (
    Maintenance,
    MaintenanceEvent,
    MaintenanceRun,
    MaintenanceRunDevice,
    MaintenanceTarget,
    MaintenanceTaskResult,
    MaintenanceTaskTemplate,
)
from apps.maintenance.services import MAX_TARGETS, MAX_TASKS, save_maintenance, template_data

from .asset_helpers import device_data, setup_assets
from .maintenance_helpers import create_maintenance, maintenance_data, task_data


class CalendarTests(SimpleTestCase):
    def test_calendar_month_edges_and_leap_years(self):
        for base, months, expected in (
            (date(2026, 10, 1), 2, date(2026, 12, 1)),
            (date(2026, 1, 31), 1, date(2026, 2, 28)),
            (date(2024, 1, 31), 1, date(2024, 2, 29)),
            (date(2024, 2, 29), 12, date(2025, 2, 28)),
            (date(2026, 3, 31), 1, date(2026, 4, 30)),
            (date(2026, 11, 30), 2, date(2027, 1, 30)),
            (date(2026, 11, 25), 2, date(2027, 1, 25)),
            (date(2026, 11, 28), 2, date(2027, 1, 28)),
        ):
            with self.subTest(base=base, months=months):
                self.assertEqual(add_interval(base, months, "MESES"), expected)

    def test_day_interval_crosses_month_and_year(self):
        self.assertEqual(add_interval(date(2026, 12, 31), 1, "DIAS"), date(2027, 1, 1))
        self.assertEqual(add_interval(date(2024, 2, 28), 2, "DIAS"), date(2024, 3, 1))

    def test_invalid_and_overflow_intervals(self):
        for base, amount, unit in (
            (None, 1, "DIAS"),
            (datetime(2026, 1, 1), 1, "DIAS"),
            (date.today(), 0, "DIAS"),
            (date.today(), -1, "MESES"),
            (date.today(), True, "DIAS"),
            (date.today(), "2", "MESES"),
            (date.today(), 1, "HORAS"),
            (date(9999, 12, 31), 1, "DIAS"),
            (date(9999, 12, 31), 1, "MESES"),
        ):
            with (
                self.subTest(base=base, amount=amount, unit=unit),
                self.assertRaises(ValidationError),
            ):
                add_interval(base, amount, unit)


class MaintenanceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        setup_assets(cls)
        cls.router_category = save_category(
            actor=cls.admin, data={"name": "Routers de prueba", "kind": "ROUTER"}
        )
        cls.router = save_device(
            actor=cls.admin,
            data=device_data(cls, name="Router", category_id=cls.router_category.pk),
        )

    def edit(self, maintenance, **overrides):
        return save_maintenance(
            **{
                "actor": self.admin,
                "maintenance_id": maintenance.pk,
                "expected_version": maintenance.version,
                "data": {},
                "device_ids": [self.device.pk],
                "tasks": template_data(maintenance),
                "reason": "Corrección para futuras ejecuciones",
                **overrides,
            }
        )

    def recurring(self, **overrides):
        return create_maintenance(
            self,
            data=maintenance_data(
                **{
                    "is_recurring": True,
                    "planned_date": None,
                    "base_date": date(2026, 10, 1),
                    "interval_value": 2,
                    "interval_unit": "MESES",
                    **overrides,
                }
            ),
        )

    def test_single_device_creates_pending_run_and_independent_task_snapshot(self):
        maintenance = create_maintenance(self)
        run = maintenance.runs.get()
        participant = run.participants.get()
        task = participant.tasks.get()
        self.assertEqual(run.state, "PENDIENTE_ATENCION")
        self.assertEqual(participant.result, "SIN_FINALIZAR")
        self.assertEqual(participant.due_date, date(2026, 12, 1))
        self.assertEqual(participant.target.device, self.device)
        self.assertFalse(task.completed)
        self.assertTrue(task.required)
        self.assertEqual(task.name, "Verificar conexiones")
        self.assertIsNotNone(task.template_id)
        self.assertEqual(maintenance.events.get().actor, self.admin)

    def test_heterogeneous_group_copies_tasks_by_scope_and_category(self):
        maintenance = create_maintenance(
            self,
            device_ids=[self.device.pk, self.router.pk],
            tasks=[
                task_data(),
                task_data(name="Revisar RAM", category_id=self.category.pk),
                task_data(
                    name="Verificar antenas", category_id=self.router_category.pk, required=False
                ),
                task_data(name="Preparar área", scope="GRUPAL"),
            ],
        )
        run = maintenance.runs.get()
        self.assertEqual(run.tasks.filter(participant__isnull=True).count(), 1)
        pc_tasks = run.participants.get(target__device=self.device).tasks
        router_tasks = run.participants.get(target__device=self.router).tasks
        self.assertEqual(pc_tasks.count(), 2)
        self.assertEqual(router_tasks.count(), 2)
        self.assertFalse(pc_tasks.filter(pk__in=router_tasks.values("pk")).exists())
        self.assertTrue(router_tasks.filter(name="Verificar antenas", required=False).exists())
        self.assertFalse(pc_tasks.filter(name="Verificar antenas").exists())

    def test_recurring_first_due_uses_base_plus_interval_for_each_device(self):
        maintenance = self.recurring()
        self.assertEqual(maintenance.initial_due_date, date(2026, 12, 1))
        self.assertEqual(maintenance.runs.get().participants.get().due_date, date(2026, 12, 1))
        self.assertIsNone(maintenance.planned_date)

    def test_periodic_date_overflow_rejected_without_partial_writes(self):
        with self.assertRaises(ValidationError):
            self.recurring(base_date=date(9999, 12, 1))
        self.assertFalse(Maintenance.objects.exists())

    def test_invalid_schedule_combinations_rejected(self):
        for data in (
            maintenance_data(name=None),
            maintenance_data(description=[]),
            maintenance_data(planned_date=None),
            maintenance_data(base_date=date(2026, 1, 1)),
            maintenance_data(interval_value=0),
            maintenance_data(is_recurring="false"),
            maintenance_data(planned_date=datetime(2026, 1, 1)),
            maintenance_data(
                is_recurring=True,
                base_date=date(2026, 1, 1),
                interval_value=1,
                interval_unit="DIAS",
            ),
            maintenance_data(
                is_recurring=True,
                planned_date=None,
                base_date=date(2026, 1, 1),
                interval_value=0,
                interval_unit="MESES",
            ),
            maintenance_data(
                is_recurring=True,
                planned_date=None,
                base_date=date(2026, 1, 1),
                interval_value=-1,
                interval_unit="MESES",
            ),
            maintenance_data(
                is_recurring=True,
                planned_date=None,
                base_date=date(2026, 1, 1),
                interval_value=True,
                interval_unit="MESES",
            ),
        ):
            with self.subTest(data=data), self.assertRaises(ValidationError):
                create_maintenance(self, data=data)
        self.assertEqual(Maintenance.objects.count(), 0)

    def test_only_admin_can_configure_and_stale_inactive_actor_is_rejected(self):
        for actor in (self.teacher, self.technician):
            with self.assertRaises(PermissionDenied):
                create_maintenance(self, actor=actor)
        self.assertTrue(self.admin.has_perm("maintenance.add_maintenance"))
        User.objects.filter(pk=self.admin.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            create_maintenance(self)

    def test_create_replay_is_idempotent_even_after_device_deactivation(self):
        key = uuid4()
        first = create_maintenance(self, creation_key=key)
        Device.objects.filter(pk=self.device.pk).update(is_active=False)
        repeated = create_maintenance(self, creation_key=key)
        self.assertEqual(first.pk, repeated.pk)
        self.assertEqual(MaintenanceRun.objects.count(), 1)
        self.assertEqual(MaintenanceTaskResult.objects.count(), 1)
        self.assertEqual(MaintenanceEvent.objects.count(), 1)

    def test_reusing_creation_key_with_changed_payload_rejected(self):
        key = uuid4()
        create_maintenance(self, creation_key=key)
        with self.assertRaises(ValidationError):
            create_maintenance(self, creation_key=key, tasks=[task_data(name="Otra tarea")])

    def test_creation_requires_valid_idempotency_key(self):
        for value in (None, "", "invalid"):
            with self.assertRaises(ValidationError):
                create_maintenance(self, creation_key=value)

    def test_edit_preserves_initial_tasks_dates_and_participants(self):
        maintenance = self.recurring()
        run = maintenance.runs.get()
        original_configuration = run.configuration.copy()
        original_task = run.tasks.get()
        original_participant = run.participants.get()
        self.edit(
            maintenance,
            data={"name": "Cambio futuro", "interval_value": 3},
            device_ids=[self.router.pk],
            tasks=[task_data(name="Revisar router", category_id=self.router_category.pk)],
        )
        run.refresh_from_db()
        original_task.refresh_from_db()
        original_participant.refresh_from_db()
        maintenance.refresh_from_db()
        self.assertEqual(run.configuration, original_configuration)
        self.assertEqual(original_task.name, "Verificar conexiones")
        self.assertEqual(original_participant.due_date, date(2026, 12, 1))
        self.assertEqual(original_participant.target.device, self.device)
        self.assertFalse(maintenance.targets.get(device=self.device).is_active)
        self.assertFalse(
            MaintenanceTaskTemplate.objects.get(pk=original_task.template_id).is_active
        )
        self.assertEqual(maintenance.initial_due_date, date(2027, 1, 1))
        self.assertEqual(maintenance.version, 2)
        self.assertEqual(maintenance.events.count(), 2)
        self.assertEqual(maintenance.runs.count(), 1)

    def test_type_and_single_planned_date_are_not_reprogrammable(self):
        maintenance = create_maintenance(self)
        for data in ({"is_recurring": True}, {"planned_date": date(2026, 12, 2)}):
            with self.assertRaises(ValidationError):
                self.edit(maintenance, data=data)

    def test_edit_requires_reason_and_current_version(self):
        maintenance = create_maintenance(self)
        with self.assertRaises(ValidationError):
            self.edit(maintenance, data={"name": "Otro"}, reason="")
        self.edit(maintenance, data={"name": "Otro"})
        with self.assertRaises(ValidationError):
            self.edit(maintenance, data={"name": "Sobrescritura"})

    def test_noop_does_not_duplicate_events_or_task_templates(self):
        maintenance = create_maintenance(self)
        self.edit(maintenance, reason="")
        self.assertEqual(maintenance.events.count(), 1)
        self.assertEqual(maintenance.task_templates.count(), 1)

    def test_deactivation_does_not_cancel_or_remove_initial_execution(self):
        maintenance = create_maintenance(self)
        self.edit(maintenance, data={"is_active": False})
        self.assertEqual(maintenance.runs.get().state, "PENDIENTE_ATENCION")
        self.assertEqual(maintenance.runs.get().participants.count(), 1)

    def test_reactivate_target_reuses_subscription_identity(self):
        maintenance = create_maintenance(self)
        target = maintenance.targets.get()
        maintenance = self.edit(maintenance, device_ids=[self.router.pk])
        self.edit(maintenance, device_ids=[self.device.pk])
        target.refresh_from_db()
        self.assertTrue(target.is_active)
        self.assertEqual(maintenance.targets.count(), 2)

    def test_new_inactive_retired_unknown_repeated_or_empty_targets_rejected(self):
        for data in ({"is_active": False}, {"is_active": True, "status": Device.Status.WITHDRAWN}):
            Device.objects.filter(pk=self.device.pk).update(**data)
            with self.assertRaises(ValidationError):
                create_maintenance(self)
        for identifiers in (
            [],
            [99999999],
            [True],
            [self.router.pk] * 2,
            [self.router.pk] * (MAX_TARGETS + 1),
        ):
            with self.assertRaises(ValidationError):
                create_maintenance(self, device_ids=identifiers)

    def test_out_of_service_device_is_allowed(self):
        Device.objects.filter(pk=self.device.pk).update(status=Device.Status.OUT_OF_SERVICE)
        self.assertIsNotNone(create_maintenance(self).pk)

    def test_existing_inactive_target_is_retained_on_edit(self):
        maintenance = create_maintenance(self)
        Device.objects.filter(pk=self.device.pk).update(is_active=False)
        self.edit(maintenance, data={"description": "Se conserva el equipo"})
        self.assertEqual(maintenance.targets.filter(is_active=True).count(), 1)

    def test_invalid_scope_duplicate_tasks_or_uncovered_device_rejected(self):
        for tasks in (
            [],
            [task_data(name="   ")],
            [task_data(scope="INVALIDO")],
            [task_data(required="yes")],
            [task_data(), task_data(name=" verificar conexiones ")],
            [task_data(scope="GRUPAL")],
            [task_data(category_id=self.router_category.pk)],
            [task_data(scope="GRUPAL", category_id=self.category.pk)],
            [task_data(name="x" * 181)],
            [task_data()] * (MAX_TASKS + 1),
        ):
            with self.subTest(tasks=str(tasks)[:80]), self.assertRaises(ValidationError):
                create_maintenance(self, tasks=tasks)
        self.assertFalse(Maintenance.objects.exists())

    def test_unknown_fields_cannot_inject_state_or_actor(self):
        with self.assertRaises(ValidationError):
            create_maintenance(self, data=maintenance_data(state="COMPLETADO"))

    def test_audit_failure_rolls_back_whole_creation(self):
        with (
            patch.object(
                MaintenanceEvent.objects, "create", side_effect=RuntimeError("audit failed")
            ),
            self.assertRaises(RuntimeError),
        ):
            create_maintenance(self)
        for model in (
            Maintenance,
            MaintenanceTarget,
            MaintenanceTaskTemplate,
            MaintenanceRun,
            MaintenanceRunDevice,
            MaintenanceTaskResult,
        ):
            self.assertFalse(model.objects.exists(), model.__name__)

    def test_snapshots_and_events_are_immutable_and_retained(self):
        maintenance = create_maintenance(self)
        for record in (
            maintenance.runs.get(),
            maintenance.runs.get().participants.get(),
            maintenance.runs.get().tasks.get(),
            maintenance.events.get(),
        ):
            with self.assertRaises(ValidationError):
                record.save()
            with self.assertRaises(ValidationError):
                type(record).objects.filter(pk=record.pk).update(pk=record.pk)
            with self.assertRaises(ValidationError):
                record.delete()
        with self.assertRaises(ValidationError):
            maintenance.delete()

    def test_references_protect_devices(self):
        create_maintenance(self)
        with self.assertRaises(ProtectedError):
            Device._base_manager.filter(pk=self.device.pk).delete()

    def test_database_rejects_invalid_schedules_and_duplicate_participants(self):
        maintenance = create_maintenance(self)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Maintenance.objects.filter(pk=maintenance.pk).update(is_recurring=True)
        participant = maintenance.runs.get().participants.get()
        with self.assertRaises(IntegrityError), transaction.atomic():
            MaintenanceRunDevice.objects.create(
                run=participant.run,
                target=participant.target,
                device_name="Duplicado",
                category=self.category,
                category_name="Prueba",
                due_date=participant.due_date,
            )

    def test_models_validate_cross_run_relationships(self):
        first, second = create_maintenance(self), create_maintenance(self)
        participant = first.runs.get().participants.get()
        participant.run = second.runs.get()
        with self.assertRaises(ValidationError):
            participant.clean()
        task = first.runs.get().tasks.get()
        task.run = second.runs.get()
        with self.assertRaises(ValidationError):
            task.clean()

    def test_movement_does_not_modify_maintenance_or_due_date(self):
        maintenance = create_maintenance(self)
        before = list(maintenance.runs.get().participants.values())
        move_device(
            actor=self.technician,
            device_id=self.device.pk,
            destination_id=self.destination.pk,
            expected_version=self.device.version,
            reason="Mover equipo pendiente",
            effective_at=timezone.now(),
            confirm_warning=True,
        )
        self.assertEqual(list(maintenance.runs.get().participants.values()), before)
        self.assertFalse(maintenance.runs.get().tasks.filter(completed=True).exists())

    @override_settings(DEBUG=True)
    def test_demo_requires_explicit_confirmation_and_development(self):
        with self.assertRaises(CommandError):
            call_command("seed_maintenance_demo", stdout=StringIO())
        with override_settings(DEBUG=False), self.assertRaises(CommandError):
            call_command("seed_maintenance_demo", confirm_demo=True, stdout=StringIO())

    @override_settings(DEBUG=True)
    def test_demo_is_idempotent_and_never_completes_work(self):
        self.admin.username = "demo_admin"
        self.admin.save()
        Device.objects.filter(pk=self.device.pk).update(name="PC de demostración")
        Device.objects.filter(pk=self.router.pk).update(name="Router de demostración")
        call_command("seed_maintenance_demo", confirm_demo=True, stdout=StringIO())
        before = list(Maintenance.objects.values())
        call_command("seed_maintenance_demo", confirm_demo=True, stdout=StringIO())
        self.assertEqual(list(Maintenance.objects.values()), before)
        self.assertEqual(Maintenance.objects.count(), 2)
        self.assertEqual(MaintenanceRun.objects.filter(state="PENDIENTE_ATENCION").count(), 2)
        self.assertFalse(MaintenanceTaskResult.objects.filter(completed=True).exists())
