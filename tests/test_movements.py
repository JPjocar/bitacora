from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Model
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.utils import timezone

from apps.assets.models import Device, Movement
from apps.assets.services import move_device, save_device
from apps.locations.services import save_location

from .asset_helpers import setup_assets


class MovementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        setup_assets(cls)

    def move(self, **overrides):
        args = {
            "actor": self.technician,
            "device_id": self.device.pk,
            "destination_id": self.destination.pk,
            "expected_version": 1,
            "reason": "Traslado físico",
            "effective_at": timezone.now() - timedelta(minutes=1),
        }
        return move_device(**(args | overrides))

    def test_movement_records_real_origin_actor_dates_and_updates_location(self):
        movement = self.move()
        self.device.refresh_from_db()
        self.assertEqual(movement.origin, self.origin)
        self.assertEqual(movement.destination, self.destination)
        self.assertEqual(movement.actor, self.technician)
        self.assertGreater(movement.recorded_at, movement.effective_at)
        self.assertEqual(self.device.location, self.destination)
        self.assertEqual(self.device.status, Device.Status.OPERATIONAL)
        self.assertEqual(self.device.version, 2)
        self.assertEqual(self.device.events.first().action, "Traslado")

    def test_next_origin_comes_from_current_database_location(self):
        first = self.move()
        second = self.move(destination_id=self.other.pk, expected_version=2)
        first.refresh_from_db()
        self.assertEqual(first.origin, self.origin)
        self.assertEqual(first.destination, self.destination)
        self.assertEqual(second.origin, self.destination)

    def test_same_missing_and_inactive_destination_rejected(self):
        self.destination.is_active = False
        self.destination.save()
        for destination in (self.origin.pk, self.destination.pk, 999999):
            with self.assertRaises(ValidationError):
                self.move(destination_id=destination)
        self.assertEqual(self.device.movements.count(), 0)

    def test_inactive_origin_can_be_left(self):
        save_location(
            actor=self.admin,
            location_id=self.origin.pk,
            expected_version=1,
            data={"is_active": False},
        )
        self.move()
        self.device.refresh_from_db()
        self.assertEqual(self.device.location, self.destination)

    def test_reason_required_and_bounded(self):
        for reason in ("", "   ", "x" * 301):
            with self.assertRaises(ValidationError):
                self.move(reason=reason)

    def test_dates_future_naive_and_out_of_order_rejected(self):
        for value in (timezone.now() + timedelta(days=1), timezone.now().replace(tzinfo=None)):
            with self.assertRaises(ValidationError):
                self.move(effective_at=value)
        first = self.move()
        with self.assertRaises(ValidationError):
            self.move(
                destination_id=self.other.pk,
                expected_version=2,
                effective_at=first.effective_at - timedelta(minutes=1),
            )

    def test_duplicate_post_and_stale_version_do_not_create_second_movement(self):
        self.move()
        with self.assertRaises(ValidationError):
            self.move()
        self.assertEqual(self.device.movements.count(), 1)
        self.assertEqual(self.device.events.count(), 2)

    def test_out_of_service_warning_is_confirmed_without_repairing_device(self):
        device = save_device(
            actor=self.admin,
            device_id=self.device.pk,
            expected_version=1,
            data={"status": Device.Status.OUT_OF_SERVICE},
            reason="Sin energía",
        )
        for confirm in (False, "true"):
            with self.assertRaises(ValidationError):
                self.move(expected_version=device.version, confirm_warning=confirm)
        self.move(expected_version=device.version, confirm_warning=True)
        self.device.refresh_from_db()
        self.assertEqual(self.device.status, Device.Status.OUT_OF_SERVICE)

    def test_archived_device_can_move_with_acknowledgement(self):
        device = save_device(
            actor=self.admin,
            device_id=self.device.pk,
            expected_version=1,
            data={"is_active": False},
        )
        with self.assertRaises(ValidationError):
            self.move(expected_version=device.version)
        self.move(expected_version=device.version, confirm_warning=True)
        self.device.refresh_from_db()
        self.assertFalse(self.device.is_active)

    def test_teacher_and_inactive_actor_denied(self):
        with self.assertRaises(PermissionDenied):
            self.move(actor=self.teacher)
        self.technician.is_active = False
        self.technician.save()
        with self.assertRaises(PermissionDenied):
            self.move()

    def test_audit_failure_rolls_back_movement_and_current_location(self):
        with (
            patch("apps.assets.services.DeviceEvent.objects.create", side_effect=RuntimeError),
            self.assertRaises(RuntimeError),
        ):
            self.move()
        self.device.refresh_from_db()
        self.assertEqual(self.device.location, self.origin)
        self.assertEqual(self.device.version, 1)
        self.assertEqual(Movement.objects.count(), 0)

    def test_movement_is_immutable_and_references_protected(self):
        movement = self.move()
        for operation in (
            movement.save,
            movement.delete,
            lambda: Movement.objects.all().delete(),
            lambda: Movement.objects.all().update(reason="Alterado"),
            lambda: Movement.objects.bulk_update([movement], ["reason"]),
        ):
            with self.assertRaises(ValidationError):
                operation()
        for obj in (self.origin, self.destination, self.device, self.technician):
            with self.assertRaises(ProtectedError):
                Model.delete(obj)

    def test_database_rejects_same_location_empty_reason_and_duplicate_version(self):
        movement = self.move()
        for change in (
            {"origin": self.destination, "device_version": movement.device_version + 1},
            {"reason": " ", "device_version": movement.device_version + 1},
            {},
        ):
            data = {
                "device": self.device,
                "origin": self.origin,
                "destination": self.destination,
                "reason": "Prueba",
                "effective_at": timezone.now(),
                "actor": self.admin,
                "device_version": movement.device_version,
            }
            with self.assertRaises(IntegrityError), transaction.atomic():
                Movement.objects.create(**(data | change))
