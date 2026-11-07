from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase

from apps.incidents.models import Incident
from apps.incidents.services import add_note, close_incident, release_incident, take_incident
from apps.notifications.models import Notification

from .asset_helpers import setup_assets
from .helpers import TECHNICIAN, create_user
from .incident_helpers import act, report


class IncidentConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.assertEqual(connection.vendor, "postgresql")
        setup_assets(self)

    def race(self, first, second, expected):
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
            results = list(pool.map(worker, [first, second]))
        self.assertEqual(len({pid for _, pid in results}), 2)
        self.assertCountEqual([status for status, _ in results], expected)

    def test_duplicate_reports_create_one_incident_event_and_notifications(self):
        key = uuid4()
        self.race(
            lambda: report(self, creation_key=key),
            lambda: report(self, creation_key=key),
            ["saved", "saved"],
        )
        incident = Incident.objects.get()
        self.assertEqual(incident.events.count(), 1)
        self.assertEqual(Notification.objects.count(), 2)

    def test_two_technicians_cannot_take_same_incident(self):
        incident = report(self)
        other = create_user("segundo", TECHNICIAN)
        self.race(
            lambda: take_incident(
                actor=self.technician, incident_id=incident.pk, expected_version=1
            ),
            lambda: take_incident(actor=other, incident_id=incident.pk, expected_version=1),
            ["saved", "rejected"],
        )
        self.assertEqual(incident.events.filter(action="INC_TAKEN").count(), 1)

    def test_duplicate_release_creates_one_release_event_and_one_new_notice_per_recipient(self):
        incident = report(self)
        act(self, take_incident, incident)

        def operation():
            return release_incident(
                actor=self.technician,
                incident_id=incident.pk,
                expected_version=2,
                reason="Pendiente",
                summary="Red comprobada",
            )

        self.race(operation, operation, ["saved", "rejected"])
        self.assertEqual(incident.events.filter(action="INC_RELEASED").count(), 1)
        self.assertEqual(Notification.objects.filter(kind="INC_RELEASED").count(), 2)

    def test_double_close_creates_one_result_and_reporter_notification(self):
        incident = report(self)
        act(self, take_incident, incident)

        def operation():
            return close_incident(
                actor=self.technician,
                incident_id=incident.pk,
                expected_version=2,
                outcome="SOLUCIONADA",
                summary="Conexión verificada",
            )

        self.race(operation, operation, ["saved", "rejected"])
        self.assertEqual(incident.events.filter(action="INC_CLOSED").count(), 1)
        self.assertEqual(Notification.objects.filter(kind="INC_CLOSED").count(), 1)

    def test_note_and_release_never_lose_a_saved_note(self):
        incident = report(self)
        act(self, take_incident, incident)
        self.race(
            lambda: add_note(
                actor=self.technician,
                incident_id=incident.pk,
                expected_version=2,
                note="Trabajo conservado",
            ),
            lambda: release_incident(
                actor=self.technician,
                incident_id=incident.pk,
                expected_version=2,
                reason="Pendiente",
                summary="Red comprobada",
            ),
            ["saved", "rejected"],
        )
        incident.refresh_from_db()
        if incident.state == Incident.State.ATTENDING:
            self.assertEqual(incident.events.filter(action="INC_NOTE").count(), 1)
        else:
            self.assertEqual(incident.state, Incident.State.PENDING)
            self.assertEqual(incident.events.filter(action="INC_NOTE").count(), 0)

    def test_release_and_close_cannot_both_apply_to_same_version(self):
        incident = report(self)
        act(self, take_incident, incident)
        self.race(
            lambda: close_incident(
                actor=self.technician,
                incident_id=incident.pk,
                expected_version=2,
                outcome="SOLUCIONADA",
                summary="Verificado",
            ),
            lambda: release_incident(
                actor=self.technician,
                incident_id=incident.pk,
                expected_version=2,
                reason="Pendiente",
                summary="Trabajo incompleto",
            ),
            ["saved", "rejected"],
        )
        self.assertEqual(
            incident.events.filter(action__in=["INC_RELEASED", "INC_CLOSED"]).count(), 1
        )
