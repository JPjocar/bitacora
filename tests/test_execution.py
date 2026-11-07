from datetime import UTC, date, datetime, timedelta
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.roles import TECHNICIAN
from apps.assets.selectors import movement_warning
from apps.assets.services import move_device, save_device
from apps.maintenance.execution import (
    cancel_maintenance,
    close_maintenance,
    complete_device,
    omit_device,
    release_maintenance,
    start_maintenance,
    take_maintenance,
)
from apps.maintenance.models import (
    MaintenanceEvent,
    MaintenanceRun,
    MaintenanceRunDevice,
    MaintenanceTaskResult,
)
from apps.maintenance.services import save_maintenance, template_data

from .asset_helpers import device_data, setup_assets
from .execution_helpers import current_version, make_run, operate, progress, start_run
from .helpers import create_user


class ExecutionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        setup_assets(cls)
        cls.second = save_device(actor=cls.admin, data=device_data(cls, name="Segundo equipo"))
        cls.third = save_device(actor=cls.admin, data=device_data(cls, name="Tercer equipo"))
        cls.other_technician = create_user("otro-tecnico", TECHNICIAN)

    def complete(self, run, participant, **kwargs):
        return operate(
            complete_device,
            self,
            run,
            **{
                "participant_id": participant.pk,
                "device_executed_on": timezone.localdate(),
                "verified": True,
                "completion_summary": "Verificado: limpieza y conexiones correctas",
                **kwargs,
            },
        )

    def test_take_assigns_only_technician_without_starting(self):
        run = make_run(self)
        for actor in (self.admin, self.teacher):
            with self.assertRaises(PermissionDenied):
                operate(take_maintenance, self, run, actor=actor)
        operate(take_maintenance, self, run)
        run.refresh_from_db()
        self.assertEqual(run.state, MaintenanceRun.State.ASSIGNED)
        self.assertEqual(run.responsible, self.technician)
        self.assertIsNone(run.started_at)
        self.assertEqual(run.events.filter(action="TAKEN").count(), 1)

    def test_start_is_explicit_and_duplicate_request_is_rejected(self):
        run = make_run(self)
        with self.assertRaises(ValidationError):
            operate(
                start_maintenance, self, run, actor=self.admin, reason="Intervención autorizada"
            )
        operate(take_maintenance, self, run)
        operate(start_maintenance, self, run)
        run.refresh_from_db()
        first = run.started_at
        with self.assertRaises(ValidationError):
            operate(start_maintenance, self, run)
        run.refresh_from_db()
        self.assertEqual(run.started_at, first)
        self.assertEqual(run.events.filter(action="STARTED").count(), 1)

    def test_release_from_assigned_does_not_invent_start(self):
        run = make_run(self)
        operate(take_maintenance, self, run)
        operate(
            release_maintenance,
            self,
            run,
            reason="Sin trabajo iniciado; se libera por disponibilidad",
        )
        run.refresh_from_db()
        self.assertIsNone(run.started_at)
        self.assertIsNone(run.responsible)
        self.assertEqual(run.state, MaintenanceRun.State.PENDING)

    def test_release_retains_checks_notes_and_first_start_for_another_technician(self):
        run = start_run(self, make_run(self))
        participant = run.participants.get()
        first = run.started_at
        progress(self, run, participant, notes="Revisión parcial conservada")
        progress(self, run, notes="Materiales listos")
        operate(
            release_maintenance,
            self,
            run,
            reason="Conexiones revisadas; libero por cambio de turno",
        )
        run.refresh_from_db()
        self.assertIsNone(run.responsible)
        self.assertEqual(run.started_at, first)
        self.assertEqual(run.notes, "Materiales listos")
        self.assertTrue(run.tasks.filter(participant=participant, completed=True).exists())
        participant.refresh_from_db()
        self.assertEqual(participant.notes, "Revisión parcial conservada")
        operate(take_maintenance, self, run, actor=self.other_technician)
        with self.assertRaises(ValidationError):
            progress(self, run, participant, actor=self.other_technician)
        operate(start_maintenance, self, run, actor=self.other_technician)
        run.refresh_from_db()
        self.assertEqual(run.started_at, first)
        self.assertEqual(run.responsible, self.other_technician)
        self.assertEqual(run.events.filter(action="RESUMED").count(), 1)

    def test_multiple_releases_are_separate_immutable_events(self):
        run = start_run(self, make_run(self))
        for reason in ("Trabajo parcial y cambio de turno", "Trabajo conservado y falta de tiempo"):
            operate(release_maintenance, self, run, reason=reason)
            operate(take_maintenance, self, run)
            operate(start_maintenance, self, run)
        self.assertEqual(run.events.filter(action="RELEASED").count(), 2)
        self.assertEqual(run.events.filter(action="RESUMED").count(), 2)

    def test_release_requires_note_and_rejects_oversize_note(self):
        run = start_run(self, make_run(self))
        for reason in ("", " ", "x" * 301):
            with self.assertRaises(ValidationError):
                operate(release_maintenance, self, run, reason=reason)
        self.assertFalse(run.events.filter(action="RELEASED").exists())

    def test_wrong_owner_cannot_start_progress_omit_complete_release_or_close(self):
        run = start_run(self, make_run(self))
        participant = run.participants.get()
        for service, values in (
            (start_maintenance, {}),
            (release_maintenance, {"reason": "Cambio"}),
            (omit_device, {"participant_id": participant.pk, "reason": "No revisado"}),
            (close_maintenance, {}),
            (cancel_maintenance, {"reason": "Cancelar"}),
        ):
            with self.subTest(service=service.__name__), self.assertRaises(PermissionDenied):
                operate(service, self, run, actor=self.other_technician, **values)
        with self.assertRaises(PermissionDenied):
            progress(self, run, participant, actor=self.other_technician)
        with self.assertRaises(PermissionDenied):
            self.complete(run, participant, actor=self.other_technician)

    def test_admin_override_requires_reason_and_audits_real_actor(self):
        run = start_run(self, make_run(self))
        with self.assertRaises(ValidationError):
            progress(self, run, actor=self.admin)
        progress(self, run, actor=self.admin, reason="Apoyo administrativo autorizado")
        event = run.events.get(action="PROGRESS")
        self.assertEqual(event.actor, self.admin)
        self.assertEqual(event.changes["reason"]["después"], "Apoyo administrativo autorizado")

    def test_inactive_actor_with_cached_permissions_is_denied(self):
        run = start_run(self, make_run(self))
        self.assertTrue(self.technician.has_perm("maintenance.execute_maintenance"))
        User.objects.filter(pk=self.technician.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            progress(self, run)

    def test_admin_can_release_inactive_owner_for_another_technician(self):
        run = start_run(self, make_run(self))
        User.objects.filter(pk=self.technician.pk).update(is_active=False)
        operate(
            release_maintenance,
            self,
            run,
            actor=self.admin,
            reason="Trabajo conservado; responsable desactivado",
        )
        operate(take_maintenance, self, run, actor=self.other_technician)
        run.refresh_from_db()
        self.assertEqual(run.responsible, self.other_technician)

    def test_progress_is_forbidden_before_start_or_after_release(self):
        run = make_run(self)
        participant = run.participants.get()
        for phase in range(3):
            with self.assertRaises(ValidationError):
                progress(self, run, participant)
            if phase == 0:
                operate(take_maintenance, self, run)
            elif phase == 1:
                operate(start_maintenance, self, run)
                operate(
                    release_maintenance,
                    self,
                    run,
                    reason="Sin avances; se conserva para otro turno",
                )

    def test_task_checks_are_independent_and_record_actor_time_observation(self):
        run = start_run(self, make_run(self, devices=[self.device, self.second]))
        first, second = list(run.participants.all())
        tasks = {
            task.pk: {"completed": True, "observation": "Conexión verificada"}
            for task in first.tasks.all()
        }
        progress(self, run, first, tasks=tasks)
        self.assertFalse(second.tasks.filter(completed=True).exists())
        self.assertFalse(run.tasks.filter(participant__isnull=True, completed=True).exists())
        for task in first.tasks.all():
            self.assertEqual(task.changed_by, self.technician)
            self.assertTrue(timezone.is_aware(task.changed_at))
            self.assertEqual(task.observation, "Conexión verificada")

    def test_reopening_task_requires_reason_and_retains_history(self):
        run = start_run(self, make_run(self))
        participant = run.participants.get()
        progress(self, run, participant)
        with self.assertRaises(ValidationError):
            progress(self, run, participant, completed=False)
        progress(
            self, run, participant, completed=False, reason="Marcado por error; falta verificar"
        )
        self.assertFalse(participant.tasks.filter(completed=True).exists())
        self.assertEqual(run.events.filter(action="PROGRESS").count(), 2)

    def test_noop_progress_does_not_duplicate_events_or_versions(self):
        run = start_run(self, make_run(self))
        progress(self, run)
        version = current_version(run)
        progress(self, run)
        self.assertEqual(current_version(run), version)
        self.assertEqual(run.events.filter(action="PROGRESS").count(), 1)

    def test_progress_rejects_foreign_missing_or_invalid_task_values(self):
        run = start_run(self, make_run(self))
        participant = run.participants.get()
        own = {task.pk: {"completed": False, "observation": ""} for task in participant.tasks.all()}
        group_task = run.tasks.get(participant__isnull=True)
        for tasks in (
            {},
            {group_task.pk: {"completed": True, "observation": ""}},
            {pk: {"completed": "true", "observation": ""} for pk in own},
            {pk: {"completed": True, "observation": "x" * 501} for pk in own},
        ):
            with self.assertRaises(ValidationError):
                progress(self, run, participant, tasks=tasks)
        self.assertFalse(participant.tasks.filter(completed=True).exists())

    def test_complete_requires_mandatory_tasks_verification_and_summary(self):
        run = start_run(self, make_run(self))
        participant = run.participants.get()
        with self.assertRaisesMessage(ValidationError, "Verificar conexiones"):
            self.complete(run, participant)
        progress(self, run, participant)
        for values in (
            {"verified": False},
            {"verified": 1},
            {"completion_summary": ""},
            {"completion_summary": "x" * 301},
        ):
            with self.assertRaises(ValidationError):
                self.complete(run, participant, **values)

    def test_optional_task_does_not_block_completion(self):
        run = start_run(self, make_run(self))
        participant = run.participants.get()
        tasks = {
            task.pk: {"completed": task.required, "observation": ""}
            for task in participant.tasks.all()
        }
        progress(self, run, participant, tasks=tasks)
        self.complete(run, participant)
        participant.refresh_from_db()
        self.assertEqual(participant.result, MaintenanceRunDevice.Result.COMPLETED)
        self.assertEqual(participant.finalized_by, self.technician)
        self.assertIsNone(participant.next_due_date)

    def test_complete_does_not_complete_other_devices_or_general_tasks(self):
        run = start_run(self, make_run(self, devices=[self.device, self.second]))
        first, second = list(run.participants.all())
        progress(self, run, first)
        self.complete(run, first)
        second.refresh_from_db()
        run.refresh_from_db()
        self.assertEqual(second.result, MaintenanceRunDevice.Result.UNFINISHED)
        self.assertEqual(run.state, MaintenanceRun.State.RUNNING)
        self.assertIsNone(run.completed_at)

    def test_completed_or_omitted_device_cannot_be_reopened_or_changed(self):
        run = start_run(self, make_run(self, devices=[self.device, self.second]))
        first, second = list(run.participants.all())
        progress(self, run, first)
        self.complete(run, first)
        operate(omit_device, self, run, participant_id=second.pk, reason="Equipo no disponible")
        for participant in (first, second):
            with self.assertRaises(ValidationError):
                progress(self, run, participant, completed=False, reason="Intento de reversión")
            with self.assertRaises(ValidationError):
                self.complete(run, participant)

    def test_future_or_non_civil_execution_date_is_rejected(self):
        run = start_run(self, make_run(self))
        participant = run.participants.get()
        progress(self, run, participant)
        for value in (timezone.localdate() + timedelta(days=1), timezone.now(), "2026-11-06", None):
            with self.assertRaises(ValidationError):
                self.complete(run, participant, device_executed_on=value)

    def test_backdating_requires_explicit_permission_and_reason(self):
        run = start_run(self, make_run(self))
        participant = run.participants.get()
        progress(self, run, participant)
        yesterday = timezone.localdate() - timedelta(days=1)
        with self.assertRaises(PermissionDenied):
            self.complete(
                run, participant, device_executed_on=yesterday, reason="Registro extemporáneo"
            )
        self.technician.user_permissions.add(
            Permission.objects.get(codename="backdate_maintenance")
        )
        with self.assertRaises(ValidationError):
            self.complete(run, participant, device_executed_on=yesterday)
        self.complete(
            run,
            participant,
            device_executed_on=yesterday,
            reason="Registro extemporáneo autorizado",
        )
        participant.refresh_from_db()
        self.assertEqual(participant.device_executed_on, yesterday)

    @patch("django.utils.timezone.now", return_value=datetime(2026, 11, 30, 17, tzinfo=UTC))
    def test_periodic_completion_has_individual_due_dates_and_omission_retains_original(
        self, mock_now
    ):
        run = start_run(
            self,
            make_run(
                self,
                devices=[self.device, self.second, self.third],
                recurring=True,
                base_date=date(2026, 10, 1),
            ),
        )
        first, second, omitted = list(run.participants.all())
        original = omitted.due_date
        self.assertEqual(original, date(2026, 12, 1))
        for participant, actual, expected in (
            (first, date(2026, 11, 25), date(2027, 1, 25)),
            (second, date(2026, 11, 28), date(2027, 1, 28)),
        ):
            progress(self, run, participant)
            self.complete(
                run,
                participant,
                actor=self.admin,
                reason="Registro extemporáneo verificado",
                device_executed_on=actual,
            )
            participant.refresh_from_db()
            self.assertEqual(participant.next_due_date, expected)
        operate(
            omit_device, self, run, participant_id=omitted.pk, reason="Equipo fuera del ambiente"
        )
        omitted.refresh_from_db()
        self.assertEqual(omitted.due_date, original)
        self.assertIsNone(omitted.next_due_date)
        self.assertIsNone(omitted.device_executed_on)

    def test_omission_requires_reason_and_is_preserved_after_move(self):
        run = start_run(self, make_run(self))
        participant = run.participants.get()
        with self.assertRaises(ValidationError):
            operate(omit_device, self, run, participant_id=participant.pk, reason="")
        operate(
            omit_device,
            self,
            run,
            participant_id=participant.pk,
            reason="Se atenderá en otra intervención",
        )
        before = list(run.participants.values())
        move_device(
            actor=self.technician,
            device_id=self.device.pk,
            destination_id=self.destination.pk,
            expected_version=self.device.version,
            reason="Regreso físico",
            effective_at=timezone.now(),
        )
        self.assertEqual(list(run.participants.values()), before)

    def test_full_close_requires_all_devices_and_general_tasks(self):
        run = start_run(self, make_run(self, devices=[self.device, self.second]))
        with self.assertRaisesMessage(ValidationError, "sin finalizar"):
            operate(close_maintenance, self, run)
        for participant in run.participants.all():
            progress(self, run, participant)
            self.complete(run, participant)
        with self.assertRaisesMessage(ValidationError, "generales obligatorias"):
            operate(close_maintenance, self, run)
        progress(self, run)
        operate(close_maintenance, self, run)
        run.refresh_from_db()
        self.assertEqual(run.state, MaintenanceRun.State.COMPLETED)
        self.assertTrue(timezone.is_aware(run.completed_at))
        self.assertEqual(run.closed_by, self.technician)
        self.assertIsNone(run.cancelled_at)

    def test_partial_close_requires_a_completed_device_and_no_unfinished(self):
        run = start_run(self, make_run(self, devices=[self.device, self.second]))
        first, second = list(run.participants.all())
        progress(self, run, first)
        self.complete(run, first)
        operate(omit_device, self, run, participant_id=second.pk, reason="No disponible")
        progress(self, run)
        operate(close_maintenance, self, run)
        run.refresh_from_db()
        self.assertEqual(run.state, MaintenanceRun.State.PARTIAL)

    def test_all_omitted_cannot_be_partial_and_can_be_cancelled(self):
        run = start_run(self, make_run(self))
        operate(
            omit_device,
            self,
            run,
            participant_id=run.participants.get().pk,
            reason="Sin acceso al equipo",
        )
        with self.assertRaisesMessage(ValidationError, "todos fueron omitidos"):
            operate(close_maintenance, self, run)
        operate(cancel_maintenance, self, run, reason="No se atendió ningún equipo")
        run.refresh_from_db()
        self.assertEqual(run.state, MaintenanceRun.State.CANCELLED)
        self.assertIsNone(run.completed_at)
        self.assertIsNotNone(run.cancelled_at)

    def test_cancel_pending_requires_admin_and_never_creates_work(self):
        run = make_run(self)
        with self.assertRaises(PermissionDenied):
            operate(cancel_maintenance, self, run, reason="Cancelar")
        with self.assertRaises(ValidationError):
            operate(cancel_maintenance, self, run, actor=self.admin, reason="")
        operate(
            cancel_maintenance,
            self,
            run,
            actor=self.admin,
            reason="Configuración duplicada: se conserva historia",
        )
        run.refresh_from_db()
        self.assertIsNone(run.started_at)
        self.assertIsNone(run.responsible)
        self.assertFalse(run.tasks.filter(completed=True).exists())

    def test_cancel_is_forbidden_if_any_device_is_completed(self):
        run = start_run(self, make_run(self))
        participant = run.participants.get()
        progress(self, run, participant)
        self.complete(run, participant)
        with self.assertRaises(ValidationError):
            operate(cancel_maintenance, self, run, reason="No debe falsear trabajo")

    def test_closed_run_rejects_all_operational_writes(self):
        run = start_run(self, make_run(self))
        operate(cancel_maintenance, self, run, reason="Cancelar intervención sin equipos completos")
        for service, values in (
            (take_maintenance, {}),
            (start_maintenance, {}),
            (release_maintenance, {"reason": "Intento"}),
            (close_maintenance, {}),
            (cancel_maintenance, {"reason": "Reintento"}),
        ):
            with self.assertRaises(ValidationError):
                operate(service, self, run, **values)
        with self.assertRaises(ValidationError):
            progress(self, run)

    def test_audit_failure_rolls_back_progress_and_version(self):
        run = start_run(self, make_run(self))
        participant = run.participants.get()
        version = current_version(run)
        with (
            patch.object(MaintenanceEvent.objects, "create", side_effect=RuntimeError("audit")),
            self.assertRaises(RuntimeError),
        ):
            progress(self, run, participant, notes="No debe persistir")
        self.assertFalse(participant.tasks.filter(completed=True).exists())
        participant.refresh_from_db()
        self.assertEqual(participant.notes, "")
        self.assertEqual(current_version(run), version)

    def test_stale_version_and_forged_snapshot_fields_are_rejected(self):
        run = make_run(self)
        operate(take_maintenance, self, run)
        with self.assertRaises(ValidationError):
            start_maintenance(actor=self.technician, run_id=run.pk, expected_version=1)
        run.refresh_from_db()
        run.configuration = {"name": "forged"}
        with self.assertRaises(ValidationError):
            run.save(update_fields=["configuration"])
        with self.assertRaises(ValidationError):
            run.tasks.update(completed=True)

    def test_configuration_edits_preserve_operational_progress_and_use_future_interval(self):
        run = start_run(self, make_run(self, recurring=True))
        participant = run.participants.get()
        progress(self, run, participant)
        maintenance = run.maintenance
        original = run.configuration.copy()
        save_maintenance(
            actor=self.admin,
            maintenance_id=maintenance.pk,
            expected_version=maintenance.version,
            data={"interval_value": 3},
            device_ids=[self.device.pk],
            tasks=template_data(maintenance),
            reason="Frecuencia futura autorizada",
        )
        self.complete(run, participant)
        run.refresh_from_db()
        participant.refresh_from_db()
        self.assertEqual(run.configuration, original)
        self.assertEqual(
            participant.next_due_date.month, ((timezone.localdate().month + 2) % 12) + 1
        )

    def test_move_during_execution_warns_and_preserves_every_operational_value(self):
        run = start_run(self, make_run(self))
        participant = run.participants.get()
        progress(self, run, participant)
        before = list(run.participants.values()), list(run.tasks.values())
        self.assertIn("preventivo pendiente", movement_warning(self.device))
        move_device(
            actor=self.technician,
            device_id=self.device.pk,
            destination_id=self.destination.pk,
            expected_version=self.device.version,
            reason="Traslado durante trabajo",
            effective_at=timezone.now(),
            confirm_warning=True,
        )
        self.assertEqual((list(run.participants.values()), list(run.tasks.values())), before)

    def test_database_rejects_inconsistent_owner_results_and_task_audit(self):
        run = make_run(self)
        with self.assertRaises(IntegrityError), transaction.atomic():
            run.state = MaintenanceRun.State.RUNNING
            run.save(update_fields=["state"])
        participant = run.participants.get()
        with self.assertRaises(IntegrityError), transaction.atomic():
            participant.result = MaintenanceRunDevice.Result.COMPLETED
            participant.save(update_fields=["result"])
        task = MaintenanceTaskResult.objects.filter(run=run).first()
        with self.assertRaises(IntegrityError), transaction.atomic():
            task.completed = True
            task.save(update_fields=["completed"])
