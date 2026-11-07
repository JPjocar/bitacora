from unittest.mock import patch

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from apps.maintenance.models import MaintenanceEvent, MaintenanceRun
from apps.notifications.models import Notification
from apps.notifications.services import generate_for_maintenance

from .asset_helpers import setup_assets
from .execution_helpers import make_run


class NotificationMigrationTests(TransactionTestCase):
    def test_existing_runs_tasks_events_and_due_dates_survive_then_backfill_works(self):
        setup_assets(self)
        latest = MigrationExecutor(connection).loader.graph.leaf_nodes()
        try:
            MigrationExecutor(connection).migrate([("notifications", None)])
            with patch("apps.notifications.services.handle_maintenance_event"):
                run = make_run(self, recurring=True)
            before = {
                "run": list(MaintenanceRun.objects.filter(pk=run.pk).values()),
                "participants": list(run.participants.values()),
                "tasks": list(run.tasks.values()),
                "events": list(MaintenanceEvent.objects.values()),
            }
            MigrationExecutor(connection).migrate(latest)
            self.assertEqual(list(MaintenanceRun.objects.filter(pk=run.pk).values()), before["run"])
            self.assertEqual(list(run.participants.values()), before["participants"])
            self.assertEqual(list(run.tasks.values()), before["tasks"])
            self.assertEqual(list(MaintenanceEvent.objects.values()), before["events"])
            self.assertFalse(Notification.objects.exists())
            generate_for_maintenance(run.maintenance_id)
            self.assertEqual(Notification.objects.filter(event__run=run).count(), 2)
            self.assertEqual(generate_for_maintenance(run.maintenance_id), 0)
        finally:
            MigrationExecutor(connection).migrate(latest)
