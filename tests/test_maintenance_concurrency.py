from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase

from apps.assets.services import save_device
from apps.maintenance.models import Maintenance, MaintenanceRun
from apps.maintenance.services import save_maintenance

from .asset_helpers import device_data, setup_assets
from .maintenance_helpers import create_maintenance, task_data


class MaintenanceConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.assertEqual(connection.vendor, "postgresql")
        setup_assets(self)

    def race(self, operations, expected):
        barrier = Barrier(2, timeout=15)

        def worker(operation):
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '10s'")
                    cursor.execute("SELECT pg_backend_pid()")
                    pid = cursor.fetchone()[0]
                barrier.wait()
                try:
                    operation()
                    return "saved", pid
                except ValidationError:
                    return "rejected", pid
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(worker, operations))
        self.assertEqual(len({pid for _, pid in results}), 2)
        self.assertCountEqual([status for status, _ in results], expected)

    def test_simultaneous_retries_create_only_one_initial_execution(self):
        key = uuid4()
        self.race(
            [
                lambda: create_maintenance(self, creation_key=key),
                lambda: create_maintenance(self, creation_key=key),
            ],
            ["saved", "saved"],
        )
        self.assertEqual(Maintenance.objects.count(), 1)
        run = MaintenanceRun.objects.get()
        self.assertEqual(run.tasks.count(), 1)
        self.assertEqual(run.events.count(), 1)

    def test_same_key_different_device_sets_cannot_create_two_definitions(self):
        key = uuid4()
        other = save_device(actor=self.admin, data=device_data(self))
        self.race(
            [
                lambda: create_maintenance(self, creation_key=key),
                lambda: create_maintenance(self, creation_key=key, device_ids=[other.pk]),
            ],
            ["saved", "rejected"],
        )
        self.assertEqual(Maintenance.objects.count(), 1)
        self.assertEqual(MaintenanceRun.objects.get().participants.count(), 1)

    def test_two_edits_cannot_overwrite_tasks_or_duplicate_history(self):
        maintenance = create_maintenance(self)

        def edit(name):
            save_maintenance(
                actor=self.admin,
                maintenance_id=maintenance.pk,
                expected_version=1,
                data={"name": name},
                device_ids=[self.device.pk],
                tasks=[task_data(name=name)],
                reason="Cambiar configuración futura",
            )

        self.race(
            [lambda: edit("Primera edición"), lambda: edit("Segunda edición")],
            ["saved", "rejected"],
        )
        maintenance.refresh_from_db()
        self.assertEqual(maintenance.version, 2)
        self.assertEqual(maintenance.events.count(), 2)
        self.assertEqual(maintenance.task_templates.get(is_active=True).name, maintenance.name)
        self.assertEqual(maintenance.runs.get().tasks.get().name, "Verificar conexiones")
