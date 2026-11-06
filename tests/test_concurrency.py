from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase

from apps.accounts.models import User
from apps.accounts.roles import ADMINISTRATOR, TEACHER
from apps.accounts.services import save_user
from apps.locations.models import Location
from apps.locations.services import save_location

from .helpers import create_user, setup_users, user_data


class ConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.assertEqual(
            connection.vendor, "postgresql", "Estas pruebas requieren PostgreSQL real."
        )
        setup_users(self)

    def run_concurrently(self, operations):
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
        self.assertCountEqual([result for result, _ in results], ["saved", "rejected"])

    def test_two_location_edits_cannot_silently_overwrite(self):
        location = save_location(
            actor=self.admin, data={"name": "Original", "kind": Location.Kind.LABORATORY}
        )
        self.run_concurrently(
            [
                lambda: save_location(
                    actor=self.admin,
                    location_id=location.pk,
                    expected_version=1,
                    data={"name": "Cambio A"},
                ),
                lambda: save_location(
                    actor=self.admin,
                    location_id=location.pk,
                    expected_version=1,
                    data={"name": "Cambio B"},
                ),
            ]
        )
        location.refresh_from_db()
        self.assertEqual(location.version, 2)
        self.assertEqual(location.events.count(), 2)

    def test_two_user_edits_cannot_silently_overwrite(self):
        self.run_concurrently(
            [
                lambda: save_user(
                    actor=self.admin,
                    user_id=self.technician.pk,
                    expected_version=1,
                    data=user_data(self.technician, first_name="Cambio A"),
                ),
                lambda: save_user(
                    actor=self.admin,
                    user_id=self.technician.pk,
                    expected_version=1,
                    data=user_data(self.technician, first_name="Cambio B"),
                ),
            ]
        )
        self.technician.refresh_from_db()
        self.assertEqual(self.technician.version, 2)
        self.assertEqual(self.technician.events.count(), 1)

    def test_two_admin_demotions_keep_one_active_administrator(self):
        second = create_user("admin2", ADMINISTRATOR)
        root = create_user("root", is_superuser=True, is_staff=True)
        self.run_concurrently(
            [
                lambda: save_user(
                    actor=root,
                    user_id=self.admin.pk,
                    expected_version=1,
                    data=user_data(self.admin, role=TEACHER),
                ),
                lambda: save_user(
                    actor=root,
                    user_id=second.pk,
                    expected_version=1,
                    data=user_data(second, role=TEACHER),
                ),
            ]
        )
        self.assertEqual(User.objects.filter(groups__name=ADMINISTRATOR, is_active=True).count(), 1)

    def test_simultaneous_duplicate_location_creation(self):
        self.run_concurrently(
            [
                lambda: save_location(
                    actor=self.admin,
                    data={"name": "Única", "code": "UNO", "kind": Location.Kind.STORAGE},
                ),
                lambda: save_location(
                    actor=self.admin,
                    data={"name": "Única", "code": "UNO", "kind": Location.Kind.STORAGE},
                ),
            ]
        )
        self.assertEqual(Location.objects.filter(code="UNO").count(), 1)
