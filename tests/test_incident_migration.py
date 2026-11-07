from unittest.mock import patch

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from apps.notifications.models import Notification

from .asset_helpers import setup_assets
from .execution_helpers import make_run
from .incident_helpers import report


class IncidentMigrationTests(TransactionTestCase):
    def test_existing_maintenance_notifications_survive_new_incident_source(self):
        setup_assets(self)
        latest = MigrationExecutor(connection).loader.graph.leaf_nodes()
        try:
            executor = MigrationExecutor(connection)
            executor.migrate([("incidents", None)])
            old_target = [("notifications", "0001_initial")]
            old = MigrationExecutor(connection).loader.project_state(old_target).apps
            with patch("apps.notifications.services.handle_maintenance_event"):
                run = make_run(self)
            OldNotification = old.get_model("notifications", "Notification")
            notice = OldNotification.objects.create(
                recipient_id=self.technician.pk,
                event_id=run.events.get().pk,
                event_key="event:legacy",
                kind="AVAILABLE",
                title="Disponible previo",
                description="Aviso conservado",
            )
            before = OldNotification.objects.filter(pk=notice.pk).values().get()
            MigrationExecutor(connection).migrate(latest)
            self.assertEqual(
                Notification.objects.filter(pk=notice.pk).values(*before).get(), before
            )
            self.assertIsNone(Notification.objects.get(pk=notice.pk).incident_event_id)
            incident = report(self)
            self.assertEqual(
                Notification.objects.filter(incident_event__incident=incident).count(), 2
            )
            self.assertEqual(run.events.count(), 1)
        finally:
            MigrationExecutor(connection).migrate(latest)
