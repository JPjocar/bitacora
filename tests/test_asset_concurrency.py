from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection, connections, transaction
from django.test import TransactionTestCase
from django.utils import timezone

from apps.assets.models import Movement
from apps.assets.services import move_device, save_device
from apps.locations.models import Location
from apps.locations.services import save_location

from .asset_helpers import device_data, setup_assets


class AssetConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.assertEqual(connection.vendor, "postgresql")
        setup_assets(self)

    def run_operations(self, operations, expected=("saved", "rejected")):
        barrier = Barrier(len(operations), timeout=15)

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

        with ThreadPoolExecutor(max_workers=len(operations)) as executor:
            results = list(executor.map(worker, operations))
        self.assertEqual(len({pid for _, pid in results}), len(operations))
        self.assertCountEqual([result for result, _ in results], expected)

    def move(self, destination_id, device=None):
        device = device or self.device
        return move_device(
            actor=self.technician,
            device_id=device.pk,
            destination_id=destination_id,
            expected_version=1,
            reason="Traslado simultáneo",
            effective_at=timezone.now(),
        )

    def test_two_incompatible_movements_only_one_succeeds(self):
        self.run_operations(
            [lambda: self.move(self.destination.pk), lambda: self.move(self.other.pk)]
        )
        self.device.refresh_from_db()
        movement = self.device.movements.get()
        self.assertEqual(movement.origin, self.origin)
        self.assertEqual(movement.destination, self.device.location)
        self.assertEqual(self.device.version, 2)
        self.assertEqual(self.device.events.count(), 2)

    def test_movement_and_device_edit_do_not_overwrite_each_other(self):
        self.run_operations(
            [
                lambda: self.move(self.destination.pk),
                lambda: save_device(
                    actor=self.admin,
                    device_id=self.device.pk,
                    expected_version=1,
                    data={"name": "Edición simultánea"},
                ),
            ]
        )
        self.device.refresh_from_db()
        if self.device.movements.exists():
            self.assertEqual(self.device.name, "Equipo de prueba")
            self.assertEqual(self.device.location, self.destination)
        else:
            self.assertEqual(self.device.name, "Edición simultánea")
            self.assertEqual(self.device.location, self.origin)

    def test_two_devices_can_swap_locations_without_fk_deadlock(self):
        second = save_device(
            actor=self.admin, data=device_data(self, location_id=self.destination.pk)
        )
        save = Movement.save
        both_destinations_locked = Barrier(2, timeout=15)

        def synchronized_save(movement, *args, **kwargs):
            both_destinations_locked.wait()
            return save(movement, *args, **kwargs)

        with patch.object(Movement, "save", synchronized_save):
            self.run_operations(
                [lambda: self.move(self.destination.pk), lambda: self.move(self.origin.pk, second)],
                expected=("saved", "saved"),
            )
        self.device.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(self.device.location, self.destination)
        self.assertEqual(second.location, self.origin)

    def test_destination_deactivation_serializes_with_movement(self):
        destination_locked = Barrier(2, timeout=15)

        def deactivate():
            with transaction.atomic():
                Location.objects.select_for_update().get(pk=self.destination.pk)
                destination_locked.wait()
                save_location(
                    actor=self.admin,
                    location_id=self.destination.pk,
                    expected_version=1,
                    data={"is_active": False},
                )

        def move_after_deactivation_started():
            destination_locked.wait()
            self.move(self.destination.pk)

        self.run_operations([deactivate, move_after_deactivation_started])
        self.device.refresh_from_db()
        self.assertEqual(self.device.location, self.origin)
        self.assertEqual(self.device.movements.count(), 0)
