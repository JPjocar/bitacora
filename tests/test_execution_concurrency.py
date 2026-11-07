from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase
from django.utils import timezone

from apps.accounts.roles import TECHNICIAN
from apps.assets.services import move_device
from apps.maintenance.dates import add_interval
from apps.maintenance.execution import (
    close_maintenance,
    complete_device,
    omit_device,
    release_maintenance,
    save_progress,
    start_maintenance,
    take_maintenance,
)
from apps.maintenance.models import MaintenanceRun, MaintenanceRunDevice
from apps.maintenance.services import save_maintenance, template_data

from .asset_helpers import setup_assets
from .execution_helpers import current_version, make_run, operate, progress, start_run
from .helpers import create_user


class ExecutionConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.assertEqual(connection.vendor, "postgresql")
        setup_assets(self)
        self.other = create_user("otro-tecnico-concurrente", TECHNICIAN)

    def race(self, operations, expected=("saved", "rejected")):
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
        self.assertCountEqual([result for result, _ in results], expected)

    def test_two_technicians_cannot_take_same_execution(self):
        run = make_run(self)
        self.race(
            [
                lambda: take_maintenance(actor=self.technician, run_id=run.pk, expected_version=1),
                lambda: take_maintenance(actor=self.other, run_id=run.pk, expected_version=1),
            ]
        )
        run.refresh_from_db()
        self.assertIn(run.responsible_id, [self.technician.pk, self.other.pk])
        self.assertEqual(run.events.filter(action="TAKEN").count(), 1)
        self.assertEqual(run.version, 2)
        self.assertIsNone(run.started_at)

    def test_two_starts_record_first_start_only_once(self):
        run = make_run(self)
        operate(take_maintenance, self, run)
        version = current_version(run)
        self.race(
            [
                lambda: start_maintenance(
                    actor=self.technician, run_id=run.pk, expected_version=version
                ),
                lambda: start_maintenance(
                    actor=self.technician, run_id=run.pk, expected_version=version
                ),
            ]
        )
        run.refresh_from_db()
        self.assertIsNotNone(run.started_at)
        self.assertEqual(run.events.filter(action="STARTED").count(), 1)

    def test_release_against_progress_never_loses_or_partially_applies_work(self):
        run = start_run(self, make_run(self))
        participant = run.participants.get()
        version = current_version(run)
        tasks = {
            task.pk: {"completed": True, "observation": ""} for task in participant.tasks.all()
        }
        self.race(
            [
                lambda: release_maintenance(
                    actor=self.technician,
                    run_id=run.pk,
                    expected_version=version,
                    reason="Se conserva trabajo; cambio de turno",
                ),
                lambda: save_progress(
                    actor=self.technician,
                    run_id=run.pk,
                    expected_version=version,
                    participant_id=participant.pk,
                    tasks=tasks,
                    notes="Avance concurrente",
                ),
            ]
        )
        run.refresh_from_db()
        participant.refresh_from_db()
        if run.state == MaintenanceRun.State.PENDING:
            self.assertEqual(participant.notes, "")
            self.assertFalse(participant.tasks.filter(completed=True).exists())
        else:
            self.assertEqual(run.state, MaintenanceRun.State.RUNNING)
            self.assertEqual(participant.notes, "Avance concurrente")
            self.assertFalse(participant.tasks.filter(completed=False).exists())

    def test_complete_against_omit_has_only_one_valid_result(self):
        run = start_run(self, make_run(self))
        participant = run.participants.get()
        progress(self, run, participant)
        version = current_version(run)
        self.race(
            [
                lambda: complete_device(
                    actor=self.technician,
                    run_id=run.pk,
                    participant_id=participant.pk,
                    expected_version=version,
                    verified=True,
                    completion_summary="Verificación completa",
                    device_executed_on=timezone.localdate(),
                ),
                lambda: omit_device(
                    actor=self.technician,
                    run_id=run.pk,
                    participant_id=participant.pk,
                    expected_version=version,
                    reason="Equipo no disponible",
                ),
            ]
        )
        participant.refresh_from_db()
        actions = run.events.filter(action__in=["DEVICE_COMPLETED", "DEVICE_OMITTED"])
        self.assertEqual(actions.count(), 1)
        if participant.result == MaintenanceRunDevice.Result.COMPLETED:
            self.assertIsNotNone(participant.device_executed_on)
            self.assertEqual(participant.omission_reason, "")
        else:
            self.assertEqual(participant.result, MaintenanceRunDevice.Result.OMITTED)
            self.assertIsNone(participant.device_executed_on)

    def test_close_against_reopening_required_general_task_is_consistent(self):
        run = start_run(self, make_run(self))
        participant = run.participants.get()
        progress(self, run, participant)
        operate(
            complete_device,
            self,
            run,
            participant_id=participant.pk,
            verified=True,
            completion_summary="Verificado",
            device_executed_on=timezone.localdate(),
        )
        progress(self, run)
        version = current_version(run)
        tasks = {
            task.pk: {"completed": False, "observation": ""}
            for task in run.tasks.filter(participant__isnull=True)
        }
        self.race(
            [
                lambda: close_maintenance(
                    actor=self.technician, run_id=run.pk, expected_version=version
                ),
                lambda: save_progress(
                    actor=self.technician,
                    run_id=run.pk,
                    expected_version=version,
                    tasks=tasks,
                    notes="",
                    reason="Rectificación de tarea general",
                ),
            ]
        )
        run.refresh_from_db()
        unfinished_general = run.tasks.filter(
            participant__isnull=True, required=True, completed=False
        ).exists()
        self.assertEqual(unfinished_general, run.state == MaintenanceRun.State.RUNNING)
        if run.state == MaintenanceRun.State.COMPLETED:
            self.assertIsNotNone(run.completed_at)

    def test_configuration_edit_and_completion_serialize_future_interval(self):
        run = start_run(self, make_run(self, recurring=True))
        participant = run.participants.get()
        progress(self, run, participant)
        version = current_version(run)
        maintenance = run.maintenance
        self.race(
            [
                lambda: save_maintenance(
                    actor=self.admin,
                    maintenance_id=maintenance.pk,
                    expected_version=maintenance.version,
                    data={"interval_value": 3},
                    device_ids=[self.device.pk],
                    tasks=template_data(maintenance),
                    reason="Intervalo futuro actualizado",
                ),
                lambda: complete_device(
                    actor=self.technician,
                    run_id=run.pk,
                    participant_id=participant.pk,
                    expected_version=version,
                    verified=True,
                    completion_summary="Verificado",
                    device_executed_on=timezone.localdate(),
                ),
            ],
            expected=("saved", "saved"),
        )
        participant.refresh_from_db()
        edited = maintenance.events.get(action="Configuración actualizada")
        completed = maintenance.events.get(action="DEVICE_COMPLETED")
        self.assertEqual(
            participant.next_due_date,
            add_interval(timezone.localdate(), 3 if edited.pk < completed.pk else 2, "MESES"),
        )
        self.assertEqual(run.configuration["interval_value"], 2)

    def test_movement_and_progress_are_independent_without_deadlock(self):
        run = start_run(self, make_run(self))
        participant = run.participants.get()
        version = current_version(run)
        tasks = {
            task.pk: {"completed": True, "observation": ""} for task in participant.tasks.all()
        }
        self.race(
            [
                lambda: move_device(
                    actor=self.technician,
                    device_id=self.device.pk,
                    destination_id=self.destination.pk,
                    expected_version=self.device.version,
                    reason="Traslado físico",
                    effective_at=timezone.now(),
                    confirm_warning=True,
                ),
                lambda: save_progress(
                    actor=self.technician,
                    run_id=run.pk,
                    participant_id=participant.pk,
                    expected_version=version,
                    tasks=tasks,
                    notes="Trabajo conservado",
                ),
            ],
            expected=("saved", "saved"),
        )
        self.device.refresh_from_db()
        participant.refresh_from_db()
        self.assertEqual(self.device.location, self.destination)
        self.assertEqual(participant.notes, "Trabajo conservado")
        self.assertEqual(participant.result, MaintenanceRunDevice.Result.UNFINISHED)
