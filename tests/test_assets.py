import uuid
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.db.models import Model
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.utils import timezone

from apps.assets.models import Category, Device
from apps.assets.services import save_category, save_device
from apps.locations.services import save_location

from .asset_helpers import device_data, setup_assets


class DeviceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        setup_assets(cls)

    def test_create_with_and_without_serial_all_types(self):
        for kind in Category.Kind.values:
            category = save_category(
                actor=self.admin, data={"name": f"Prueba {kind}", "kind": kind}
            )
            for serial in ("", "Serie no universal"):
                device = save_device(
                    actor=self.admin,
                    data=device_data(self, category_id=category.pk, serial_number=serial),
                )
                self.assertEqual(device.serial_number, serial)
                self.assertEqual(device.created_by, self.admin)
                self.assertEqual(device.events.count(), 1)
                self.assertRegex(device.code, r"^EQ-[ABCDEFGHJKMNPQRSTUVWXYZ23456789]{8}$")
                self.assertIsInstance(device.public_id, uuid.UUID)

    def test_code_collision_is_retried(self):
        with patch(
            "apps.assets.services.generate_device_code",
            side_effect=[self.device.code, "EQ-ABCDEFGH"],
        ) as generate:
            device = save_device(actor=self.admin, data=device_data(self))
        self.assertEqual(device.code, "EQ-ABCDEFGH")
        self.assertEqual(generate.call_count, 2)
        self.assertEqual(device.events.count(), 1)

    def test_collision_retry_limit_rolls_back(self):
        count = Device.objects.count()
        with (
            patch("apps.assets.services.generate_device_code", return_value=self.device.code),
            self.assertRaises(ValidationError),
        ):
            save_device(actor=self.admin, data=device_data(self))
        self.assertEqual(Device.objects.count(), count)

    def test_identifiers_immutable_on_save_and_queryset(self):
        for field, value in [("code", "EQ-ABCDEFGH"), ("public_id", uuid.uuid4())]:
            device = Device.objects.get(pk=self.device.pk)
            setattr(device, field, value)
            with self.assertRaises(ValidationError):
                device.save()
            with self.assertRaises(ValidationError):
                Device.objects.filter(pk=device.pk).update(**{field: value})
            with self.assertRaises(ValidationError):
                Device.objects.bulk_update([device], [field])

    def test_cannot_inject_identity_actor_or_location_when_editing(self):
        device = save_device(
            actor=self.admin,
            device_id=self.device.pk,
            expected_version=1,
            data={
                "name": "Editado",
                "code": "EQ-ABCDEFGH",
                "public_id": uuid.uuid4(),
                "created_by_id": self.teacher.pk,
            },
        )
        self.assertEqual(device.code, self.device.code)
        self.assertEqual(device.created_by, self.admin)
        with self.assertRaises(ValidationError):
            save_device(
                actor=self.admin,
                device_id=device.pk,
                expected_version=2,
                data={"location_id": self.destination.pk},
            )

    def test_creation_denies_inactive_or_missing_catalog_entries(self):
        self.category.is_active = False
        self.category.save()
        with self.assertRaises(ValidationError):
            save_device(actor=self.admin, data=device_data(self))
        self.category.is_active = True
        self.category.save()
        self.origin.is_active = False
        self.origin.save()
        for overrides in ({}, {"category_id": 999999}, {"location_id": 999999}):
            with self.assertRaises(ValidationError):
                save_device(actor=self.admin, data=device_data(self, **overrides))

    def test_existing_inactive_catalog_assignment_can_be_kept(self):
        self.category.is_active = False
        self.category.save()
        save_location(
            actor=self.admin,
            location_id=self.origin.pk,
            expected_version=1,
            data={"is_active": False},
        )
        device = save_device(
            actor=self.admin, device_id=self.device.pk, expected_version=1, data={"brand": "Marca"}
        )
        self.assertEqual(device.location_id, self.origin.pk)
        self.assertEqual(device.category_id, self.category.pk)

    def test_switch_to_inactive_category_rejected(self):
        other = save_category(
            actor=self.admin, data={"name": "Inactiva", "kind": "OTROS", "is_active": False}
        )
        with self.assertRaises(ValidationError):
            save_device(
                actor=self.admin,
                device_id=self.device.pk,
                expected_version=1,
                data={"category_id": other.pk},
            )

    def test_dates_blank_future_and_order_validation(self):
        today = timezone.localdate()
        self.assertIsNone(self.device.acquired_on)
        for data in (
            {"acquired_on": today + timedelta(days=1)},
            {"commissioned_on": today + timedelta(days=1)},
            {"acquired_on": today, "commissioned_on": today - timedelta(days=1)},
        ):
            with self.assertRaises(ValidationError):
                save_device(actor=self.admin, data=device_data(self, **data))
        device = save_device(
            actor=self.admin,
            data=device_data(self, acquired_on=today - timedelta(days=2), commissioned_on=today),
        )
        self.assertEqual(device.commissioned_on, today)
        self.assertIsInstance(device.events.get().changes["acquired_on"]["después"], str)

    def test_invalid_fields_and_state_rejected(self):
        for data in (
            {"name": " "},
            {"name": "x" * 121},
            {"status": "EN_MANTENIMIENTO"},
            {"technical_details": "x" * 4001},
            {"is_active": "False"},
        ):
            with self.assertRaises(ValidationError):
                save_device(actor=self.admin, data=device_data(self, **data))

    def test_db_constraints_without_full_clean(self):
        for data in (
            {"status": "INVALIDO"},
            {"name": " "},
            {
                "acquired_on": timezone.localdate(),
                "commissioned_on": timezone.localdate() - timedelta(days=1),
            },
        ):
            with self.assertRaises(IntegrityError), transaction.atomic():
                Device.objects.filter(pk=self.device.pk).update(**data)
        duplicate = Device(
            name="Duplicado",
            category=self.category,
            location=self.origin,
            created_by=self.admin,
            code=self.device.code,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            duplicate.save()

    def test_status_change_requires_reason_and_records_it(self):
        with self.assertRaises(ValidationError):
            save_device(
                actor=self.technician,
                device_id=self.device.pk,
                expected_version=1,
                data={"status": Device.Status.OUT_OF_SERVICE},
            )
        device = save_device(
            actor=self.technician,
            device_id=self.device.pk,
            expected_version=1,
            data={"status": Device.Status.OUT_OF_SERVICE},
            reason="No enciende",
        )
        self.assertEqual(device.events.first().changes["reason"]["después"], "No enciende")

    def test_technician_update_is_limited_and_teacher_cannot_write(self):
        for actor in (self.technician, self.teacher):
            with self.assertRaises(PermissionDenied):
                save_device(actor=actor, data=device_data(self))
        for data in (
            {"name": "Alterado"},
            {"is_active": False},
            {"location_id": self.destination.pk},
            {"technical_details": "Otro"},
        ):
            with self.assertRaises(PermissionDenied):
                save_device(
                    actor=self.technician, device_id=self.device.pk, expected_version=1, data=data
                )
        with self.assertRaises(PermissionDenied):
            save_device(
                actor=self.teacher,
                device_id=self.device.pk,
                expected_version=1,
                data={"observations": "Otra"},
            )
        device = save_device(
            actor=self.technician,
            device_id=self.device.pk,
            expected_version=1,
            data={"observations": "Revisar cable"},
        )
        self.assertEqual(device.observations, "Revisar cable")

    def test_deactivation_reactivation_preserves_history_and_identity(self):
        for version, active in [(1, False), (2, True)]:
            device = save_device(
                actor=self.admin,
                device_id=self.device.pk,
                expected_version=version,
                data={"is_active": active},
            )
            self.assertEqual(device.code, self.device.code)
            self.assertEqual(device.public_id, self.device.public_id)
        self.assertEqual(device.events.count(), 3)

    def test_stale_edit_and_noop(self):
        save_device(
            actor=self.admin,
            device_id=self.device.pk,
            expected_version=1,
            data={"name": self.device.name},
        )
        self.assertEqual(self.device.events.count(), 1)
        save_device(
            actor=self.admin,
            device_id=self.device.pk,
            expected_version=1,
            data={"name": "Nuevo nombre"},
        )
        with self.assertRaises(ValidationError):
            save_device(
                actor=self.admin,
                device_id=self.device.pk,
                expected_version=1,
                data={"name": "Anterior"},
            )

    def test_audit_failure_rolls_back_creation_and_edit(self):
        count = Device.objects.count()
        with patch("apps.assets.services.DeviceEvent.objects.create", side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                save_device(actor=self.admin, data=device_data(self))
            with self.assertRaises(RuntimeError):
                save_device(
                    actor=self.admin,
                    device_id=self.device.pk,
                    expected_version=1,
                    data={"name": "Cambio"},
                )
        self.device.refresh_from_db()
        self.assertEqual(self.device.name, "Equipo de prueba")
        self.assertEqual(Device.objects.count(), count)

    def test_deletion_and_related_objects_protected(self):
        with self.assertRaises(ValidationError):
            self.device.delete()
        with self.assertRaises(ValidationError):
            Device.objects.all().delete()
        for obj in (self.origin, self.category, self.device, self.admin):
            with self.assertRaises(ProtectedError):
                Model.delete(obj)

    def test_category_management_permissions_uniqueness_and_history(self):
        for actor in (self.technician, self.teacher):
            with self.assertRaises(PermissionDenied):
                save_category(actor=actor, data={"name": "Nueva", "kind": "OTROS"})
        with self.assertRaises(ValidationError):
            save_category(
                actor=self.admin, data={"name": "  categoría DE PRUEBA ", "kind": "OTROS"}
            )
        category = save_category(
            actor=self.admin,
            category_id=self.category.pk,
            expected_version=1,
            data={"is_active": False},
        )
        self.assertEqual(category.events.count(), 2)
        self.assertEqual(self.device.category_id, category.pk)
        with self.assertRaises(ValidationError):
            save_category(
                actor=self.admin,
                category_id=category.pk,
                expected_version=1,
                data={"is_active": True},
            )

    def test_demo_requires_explicit_confirmation(self):
        with self.assertRaises(CommandError):
            call_command("seed_assets_demo", stdout=StringIO())
