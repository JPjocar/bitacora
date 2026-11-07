from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase
from django.utils import timezone

from apps.assets.services import save_device
from apps.maintenance.execution import close_maintenance, complete_device
from apps.maintenance.models import MaintenanceRun
from apps.maintenance.recurrence import create_next_run
from apps.maintenance.services import save_maintenance, template_data

from .asset_helpers import device_data, setup_assets
from .execution_helpers import current_version, operate, progress, start_run
from .recurrence_helpers import cancel_run, recurring_run


class RecurrenceConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.assertEqual(connection.vendor, "postgresql")
        setup_assets(self)

    def race(self, operations, expected=None):
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
        statuses = [result for result, _ in results]
        if expected:
            self.assertCountEqual(statuses, expected)
        return statuses

    def create(self, previous, targets):
        return create_next_run(
            actor=self.technician,
            maintenance_id=previous.maintenance_id,
            expected_version=1,
            previous_run_id=previous.pk,
            target_ids=targets,
            reason="Selección anticipada para prueba de concurrencia",
        )

    def test_duplicate_creations_create_one_run_and_one_event(self):
        previous = recurring_run(self)
        cancel_run(self, previous)
        target = previous.maintenance.targets.get()
        self.race(
            [
                lambda: self.create(previous, [target.pk]),
                lambda: self.create(previous, [target.pk]),
            ],
            expected=["saved", "rejected"],
        )
        self.assertEqual(previous.maintenance.runs.count(), 2)
        current = previous.maintenance.runs.first()
        self.assertEqual(current.events.filter(action="RUN_CREATED").count(), 1)
        self.assertEqual(current.number, 2)

    def test_even_disjoint_selections_do_not_open_two_concurrent_runs(self):
        other = save_device(actor=self.admin, data=device_data(self))
        previous = recurring_run(self, [self.device, other])
        cancel_run(self, previous)
        targets = list(previous.maintenance.targets.values_list("pk", flat=True))
        self.race(
            [
                lambda: self.create(previous, [targets[0]]),
                lambda: self.create(previous, [targets[1]]),
            ],
            expected=["saved", "rejected"],
        )
        self.assertEqual(previous.maintenance.runs.first().participants.count(), 1)
        self.assertEqual(previous.maintenance.runs.filter(state="PENDIENTE_ATENCION").count(), 1)

    def test_configuration_change_either_rejects_creation_or_preserves_its_original_copy(self):
        previous = recurring_run(self)
        cancel_run(self, previous)
        maintenance = previous.maintenance
        target = maintenance.targets.get()
        statuses = self.race(
            [
                lambda: self.create(previous, [target.pk]),
                lambda: save_maintenance(
                    actor=self.admin,
                    maintenance_id=maintenance.pk,
                    expected_version=1,
                    data={"name": "Nombre futuro"},
                    device_ids=[self.device.pk],
                    tasks=template_data(maintenance),
                    reason="Edición simultánea",
                ),
            ]
        )
        self.assertEqual(statuses[1], "saved")
        if statuses[0] == "saved":
            self.assertEqual(maintenance.runs.first().configuration["name"], "Preventivo de prueba")
        else:
            self.assertEqual(maintenance.runs.count(), 1)
        maintenance.refresh_from_db()
        self.assertEqual(maintenance.name, "Nombre futuro")

    def test_device_deactivation_is_serialized_with_selection(self):
        previous = recurring_run(self)
        cancel_run(self, previous)
        target = previous.maintenance.targets.get()
        statuses = self.race(
            [
                lambda: self.create(previous, [target.pk]),
                lambda: save_device(
                    actor=self.admin,
                    device_id=self.device.pk,
                    expected_version=self.device.version,
                    data={"is_active": False},
                ),
            ]
        )
        self.assertEqual(statuses[1], "saved")
        self.device.refresh_from_db()
        self.assertFalse(self.device.is_active)
        if statuses[0] == "saved":
            participant = previous.maintenance.runs.first().participants.get()
            self.assertEqual(participant.result, "SIN_FINALIZAR")
            self.assertEqual(participant.target.device_id, self.device.pk)
        else:
            self.assertEqual(previous.maintenance.runs.count(), 1)

    def test_close_and_next_creation_cannot_leave_two_open_or_skip_a_cycle(self):
        previous = start_run(self, recurring_run(self))
        participant = previous.participants.get()
        progress(self, previous, participant)
        operate(
            complete_device,
            self,
            previous,
            participant_id=participant.pk,
            device_executed_on=timezone.localdate(),
            verified=True,
            completion_summary="Verificado",
        )
        progress(self, previous)
        version = current_version(previous)
        target = previous.maintenance.targets.get()
        statuses = self.race(
            [
                lambda: self.create(previous, [target.pk]),
                lambda: close_maintenance(
                    actor=self.technician, run_id=previous.pk, expected_version=version
                ),
            ]
        )
        self.assertEqual(statuses[1], "saved")
        previous.refresh_from_db()
        self.assertEqual(previous.state, MaintenanceRun.State.COMPLETED)
        self.assertEqual(previous.maintenance.runs.count(), 2 if statuses[0] == "saved" else 1)
