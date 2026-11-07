from uuid import uuid4

from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone

from apps.maintenance.models import MaintenanceRun
from apps.maintenance.recurrence import create_next_run

from .asset_helpers import setup_assets


class RecurrenceMigrationTests(TransactionTestCase):
    def test_closed_execution_and_tasks_survive_then_new_run_is_possible(self):
        setup_assets(self)
        old_target = [("maintenance", "0002_execution_workflow")]
        latest = MigrationExecutor(connection).loader.graph.leaf_nodes()
        try:
            executor = MigrationExecutor(connection)
            executor.migrate(old_target)
            old = executor.loader.project_state(old_target).apps
            maintenance = old.get_model("maintenance", "Maintenance").objects.create(
                name="Periódico previo",
                is_recurring=True,
                base_date=timezone.localdate(),
                interval_value=2,
                interval_unit="MESES",
                created_by_id=self.admin.pk,
                creation_key=uuid4(),
                creation_signature="0" * 64,
            )
            target = old.get_model("maintenance", "MaintenanceTarget").objects.create(
                maintenance_id=maintenance.pk, device_id=self.device.pk
            )
            template = old.get_model("maintenance", "MaintenanceTaskTemplate").objects.create(
                maintenance_id=maintenance.pk, name="Tarea previa", scope="DISPOSITIVO", order=1
            )
            run = old.get_model("maintenance", "MaintenanceRun").objects.create(
                maintenance_id=maintenance.pk,
                state="CANCELADO",
                cancelled_at=timezone.now(),
                closed_by_id=self.admin.pk,
                cancellation_reason="Prueba conservada",
                configuration={"name": "Periódico previo", "version": 1},
            )
            participant = old.get_model("maintenance", "MaintenanceRunDevice").objects.create(
                run_id=run.pk,
                target_id=target.pk,
                device_name=self.device.name,
                category_id=self.category.pk,
                category_name=self.category.name,
                due_date=timezone.localdate(),
            )
            old.get_model("maintenance", "MaintenanceTaskResult").objects.create(
                run_id=run.pk,
                participant_id=participant.pk,
                template_id=template.pk,
                name="Tarea previa",
                scope="DISPOSITIVO",
                order=1,
            )
            MigrationExecutor(connection).migrate(latest)
            preserved = MaintenanceRun.objects.get(pk=run.pk)
            before = (
                list(preserved.participants.values()),
                list(preserved.tasks.values()),
                preserved.configuration.copy(),
            )
            current = create_next_run(
                actor=self.technician,
                maintenance_id=maintenance.pk,
                expected_version=1,
                previous_run_id=run.pk,
                target_ids=[target.pk],
                reason="Prueba anticipada",
            )
            self.assertEqual(current.number, 2)
            self.assertEqual(
                (
                    list(preserved.participants.values()),
                    list(preserved.tasks.values()),
                    preserved.configuration,
                ),
                before,
            )
            self.assertEqual(current.tasks.get().name, "Tarea previa")
            with self.assertRaises(IntegrityError), transaction.atomic():
                MaintenanceRun.objects.create(
                    maintenance_id=maintenance.pk, number=3, configuration={}
                )
        finally:
            MigrationExecutor(connection).migrate(latest)
