from uuid import uuid4

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone

from apps.maintenance.execution import take_maintenance
from apps.maintenance.models import MaintenanceRun

from .asset_helpers import setup_assets


class ExecutionMigrationTests(TransactionTestCase):
    def test_existing_pending_configuration_and_snapshots_survive_migration(self):
        setup_assets(self)
        old_target = [("maintenance", "0001_initial")]
        latest = [("maintenance", "0002_execution_workflow")]
        executor = MigrationExecutor(connection)
        try:
            executor.migrate(old_target)
            old = executor.loader.project_state(old_target).apps
            maintenance = old.get_model("maintenance", "Maintenance").objects.create(
                name="Preventivo anterior",
                planned_date=timezone.localdate(),
                created_by_id=self.admin.pk,
                creation_key=uuid4(),
                creation_signature="0" * 64,
            )
            target = old.get_model("maintenance", "MaintenanceTarget").objects.create(
                maintenance_id=maintenance.pk, device_id=self.device.pk
            )
            template = old.get_model("maintenance", "MaintenanceTaskTemplate").objects.create(
                maintenance_id=maintenance.pk, name="Tarea conservada", order=1, scope="DISPOSITIVO"
            )
            run = old.get_model("maintenance", "MaintenanceRun").objects.create(
                maintenance_id=maintenance.pk,
                configuration={"name": "Preventivo anterior", "version": 1},
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
                name="Tarea conservada",
                order=1,
                scope="DISPOSITIVO",
            )
            MigrationExecutor(connection).migrate(latest)
            current = MaintenanceRun.objects.get(pk=run.pk)
            self.assertEqual(current.configuration, run.configuration)
            self.assertIsNone(current.responsible)
            self.assertIsNone(current.started_at)
            self.assertEqual(current.version, 1)
            self.assertEqual(current.tasks.get().name, "Tarea conservada")
            self.assertIsNone(current.tasks.get().changed_at)
            self.assertEqual(current.participants.get().due_date, participant.due_date)
            take_maintenance(actor=self.technician, run_id=current.pk, expected_version=1)
            current.refresh_from_db()
            self.assertEqual(current.responsible, self.technician)
        finally:
            MigrationExecutor(connection).migrate(latest)
