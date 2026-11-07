from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase

from apps.maintenance.execution import release_maintenance, take_maintenance
from apps.notifications.models import Notification
from apps.notifications.services import generate_for_maintenance, mark_read

from .asset_helpers import setup_assets
from .execution_helpers import make_run, operate


class NotificationConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.assertEqual(connection.vendor, "postgresql")
        setup_assets(self)

    def race(self, first, second):
        barrier = Barrier(2, timeout=15)

        def worker(operation):
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '10s'")
                    cursor.execute("SELECT pg_backend_pid()")
                    pid = cursor.fetchone()[0]
                barrier.wait()
                operation()
                return pid
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            pids = list(pool.map(worker, [first, second]))
        self.assertEqual(len(set(pids)), 2)

    def test_two_commands_do_not_duplicate_due_or_available_notices(self):
        run = make_run(self)
        self.race(
            lambda: generate_for_maintenance(run.maintenance_id),
            lambda: generate_for_maintenance(run.maintenance_id),
        )
        self.assertEqual(Notification.objects.filter(event__run=run).count(), 2)
        self.assertEqual(
            Notification.objects.filter(target__maintenance=run.maintenance).count(), 2
        )

    def test_command_and_take_cannot_leave_available_notice_current(self):
        run = make_run(self)
        self.race(
            lambda: generate_for_maintenance(run.maintenance_id),
            lambda: operate(take_maintenance, self, run),
        )
        self.assertFalse(Notification.objects.filter(event__run=run, resolved_at=None).exists())

    def test_command_and_release_keep_one_fresh_release_per_recipient(self):
        run = make_run(self)
        operate(take_maintenance, self, run)
        self.race(
            lambda: generate_for_maintenance(run.maintenance_id),
            lambda: operate(release_maintenance, self, run, reason="Prueba concurrente"),
        )
        notices = Notification.objects.filter(event__run=run, resolved_at=None)
        self.assertEqual(notices.count(), 2)
        self.assertEqual(notices.filter(kind="RELEASED").count(), 2)

    def test_concurrent_mark_read_keeps_one_timestamp(self):
        make_run(self)
        notice = Notification.objects.get(recipient=self.technician)
        self.race(
            lambda: mark_read(actor=self.technician, notice_id=notice.pk),
            lambda: mark_read(actor=self.technician, notice_id=notice.pk),
        )
        notice.refresh_from_db()
        self.assertIsNotNone(notice.read_at)
