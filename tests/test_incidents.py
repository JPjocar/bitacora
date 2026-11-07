from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.assets.models import Device
from apps.incidents.models import Incident, IncidentEvent
from apps.incidents.services import (
    add_note,
    close_incident,
    release_incident,
    take_incident,
)
from apps.notifications.models import Notification
from apps.notifications.services import handle_incident_event, mark_read

from .asset_helpers import setup_assets
from .helpers import TECHNICIAN, create_user
from .incident_helpers import act, report
from .recurrence_helpers import recurring_run


class IncidentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        setup_assets(cls)

    def test_roles_can_report_and_do_not_change_device_status(self):
        for actor in [self.teacher, self.admin, self.technician]:
            incident = report(self, actor=actor)
            self.assertEqual(incident.state, Incident.State.PENDING)
            self.assertEqual(incident.reporter_id, actor.pk)
            self.assertIsNone(incident.responsible_id)
            self.assertEqual(incident.events.count(), 1)
            self.assertEqual(
                Notification.objects.filter(incident_event__incident=incident).count(), 2
            )
        self.device.refresh_from_db()
        self.assertEqual(self.device.status, Device.Status.OPERATIONAL)

    def test_report_retry_returns_same_record_event_and_notices(self):
        key = uuid4()
        incident = report(self, creation_key=key)
        self.assertEqual(report(self, creation_key=key).pk, incident.pk)
        self.assertEqual(Incident.objects.count(), 1)
        self.assertEqual(incident.events.count(), 1)
        self.assertEqual(Notification.objects.count(), 2)
        with self.assertRaises(ValidationError):
            report(self, creation_key=key, symptoms="Un reporte distinto")
        with self.assertRaises(PermissionDenied):
            report(self, actor=self.admin, creation_key=key)

    def test_input_validation(self):
        for values in [
            {"symptoms": " "},
            {"symptoms": "x" * 3001},
            {"symptoms": None},
            {"creation_key": "inválido"},
            {"device_id": True},
            {"device_id": 999999},
        ]:
            with self.subTest(values=list(values)), self.assertRaises(ValidationError):
                report(self, **values)
        self.assertFalse(Incident.objects.exists())

    def test_archive_and_withdrawal_reject_new_reports_for_all_roles(self):
        self.device.is_active = False
        self.device.save(update_fields=["is_active"])
        for actor in [self.teacher, self.admin]:
            with self.assertRaises(ValidationError):
                report(self, actor=actor)
        self.device.is_active = True
        self.device.status = Device.Status.WITHDRAWN
        self.device.save(update_fields=["is_active", "status"])
        with self.assertRaises(ValidationError):
            report(self, actor=self.admin)

    def test_inactive_actor_and_missing_permission_rejected(self):
        self.teacher.is_active = False
        self.teacher.save(update_fields=["is_active"])
        with self.assertRaises(PermissionDenied):
            report(self)
        outsider = create_user("sin_permiso")
        with self.assertRaises(PermissionDenied):
            report(self, actor=outsider)

    def test_taking_assigns_technician_and_resolves_availability(self):
        incident = report(self)
        act(self, take_incident, incident)
        incident.refresh_from_db()
        self.assertEqual(incident.state, Incident.State.ATTENDING)
        self.assertEqual(incident.responsible_id, self.technician.pk)
        self.assertFalse(
            Notification.objects.filter(
                incident_event__incident=incident, resolved_at=None
            ).exists()
        )
        self.assertIsNone(incident.closed_at)

    def test_admin_and_teacher_cannot_take(self):
        incident = report(self)
        for actor in [self.admin, self.teacher]:
            with self.assertRaises(PermissionDenied):
                act(self, take_incident, incident, actor=actor)

    def test_take_twice_and_stale_version_are_rejected(self):
        incident = report(self)
        act(self, take_incident, incident)
        with self.assertRaises(ValidationError):
            act(self, take_incident, incident)
        with self.assertRaises(ValidationError):
            add_note(
                actor=self.technician,
                incident_id=incident.pk,
                expected_version=1,
                note="No se pierde",
            )

    def test_note_and_release_require_attention_and_responsibility(self):
        incident = report(self)
        with self.assertRaises(ValidationError):
            act(self, add_note, incident, actor=self.admin, note="No inició", reason="Supervisión")
        act(self, take_incident, incident)
        other = create_user("segundo", TECHNICIAN)
        with self.assertRaises(PermissionDenied):
            act(self, add_note, incident, actor=other, note="No autorizado")
        with self.assertRaises(PermissionDenied):
            act(self, release_incident, incident, actor=other, reason="Otro", summary="Otro")

    def test_release_keeps_notes_and_each_release_notifies_again(self):
        incident = report(self)
        for number in range(2):
            act(self, take_incident, incident)
            act(self, add_note, incident, note=f"Comprobación técnica {number}")
            act(
                self,
                release_incident,
                incident,
                reason="Pendiente de repuesto",
                summary="Se verificó la red",
            )
            incident.refresh_from_db()
            self.assertEqual(incident.state, Incident.State.PENDING)
            self.assertIsNone(incident.responsible_id)
            self.assertEqual(incident.events.filter(action="INC_NOTE").count(), number + 1)
            self.assertEqual(
                Notification.objects.filter(
                    incident_event__incident=incident, kind="INC_RELEASED"
                ).count(),
                (number + 1) * 2,
            )
            self.assertEqual(
                Notification.objects.filter(
                    incident_event__incident=incident, resolved_at=None
                ).count(),
                2,
            )

    def test_release_requires_reason_and_summary(self):
        incident = report(self)
        act(self, take_incident, incident)
        for reason, summary in [
            ("", "Revisado"),
            ("Pendiente", ""),
            ("x" * 301, "Revisado"),
            ("Pendiente", "x" * 1001),
        ]:
            with self.assertRaises(ValidationError):
                act(self, release_incident, incident, reason=reason, summary=summary)
        self.assertFalse(incident.events.filter(action="INC_RELEASED").exists())

    def test_another_technician_can_take_and_continue_existing_history(self):
        incident = report(self)
        act(self, take_incident, incident)
        act(self, add_note, incident, note="Prueba inicial conservada")
        act(
            self,
            release_incident,
            incident,
            reason="Fin de turno",
            summary="Comprobación incompleta",
        )
        other = create_user("relevo", TECHNICIAN)
        act(self, take_incident, incident, actor=other)
        act(self, add_note, incident, actor=other, note="Continúa comprobación")
        incident.refresh_from_db()
        self.assertEqual(incident.responsible_id, other.pk)
        self.assertEqual(incident.events.filter(action="INC_NOTE").count(), 2)

    def test_admin_override_requires_reason_and_is_audited(self):
        incident = report(self)
        act(self, take_incident, incident)
        with self.assertRaises(ValidationError):
            act(self, add_note, incident, actor=self.admin, note="Supervisión")
        act(
            self,
            add_note,
            incident,
            actor=self.admin,
            note="Supervisión",
            reason="Prueba autorizada",
        )
        event = incident.events.first()
        self.assertEqual(event.actor_id, self.admin.pk)
        self.assertEqual(event.changes["reason"]["después"], "Prueba autorizada")

    def test_solved_close_notifies_reporter_once_and_preserves_closed_responsible(self):
        incident = report(self)
        act(self, take_incident, incident)
        act(
            self,
            close_incident,
            incident,
            outcome="SOLUCIONADA",
            summary="Conexión restablecida y probada",
        )
        incident.refresh_from_db()
        self.assertEqual(incident.state, Incident.State.CLOSED)
        self.assertEqual(incident.responsible_id, self.technician.pk)
        self.assertIsNotNone(incident.closed_at)
        self.assertEqual(incident.closed_by_id, self.technician.pk)
        notice = Notification.objects.get(kind="INC_CLOSED")
        self.assertEqual(notice.recipient_id, self.teacher.pk)
        self.assertEqual(notice.get_absolute_url(), incident.get_absolute_url())
        mark_read(actor=self.teacher, notice_id=notice.pk)
        self.assertEqual(handle_incident_event(incident.events.first()), 0)
        self.assertEqual(Notification.objects.filter(kind="INC_CLOSED").count(), 1)

    def test_unrepairable_requires_permission_and_reason(self):
        incident = report(self)
        act(self, take_incident, incident)
        with self.assertRaises(PermissionDenied):
            act(
                self,
                close_incident,
                incident,
                outcome="NO_REPARABLE",
                summary="Placa dañada",
                reason="Diagnóstico documentado",
            )
        with self.assertRaises(ValidationError):
            act(
                self,
                close_incident,
                incident,
                actor=self.admin,
                outcome="NO_REPARABLE",
                summary="Placa dañada",
            )
        act(
            self,
            close_incident,
            incident,
            actor=self.admin,
            outcome="NO_REPARABLE",
            summary="Placa dañada, falla permanece",
            reason="Daño técnico verificado",
        )
        incident.refresh_from_db()
        self.assertEqual(incident.outcome, "NO_REPARABLE")
        self.assertIn("No reparable", Notification.objects.get(kind="INC_CLOSED").description)

    def test_explicit_unrepairable_permission_can_authorize_owner(self):
        permission = Permission.objects.get(
            content_type__app_label="incidents", codename="close_unrepairable_incident"
        )
        self.technician.user_permissions.add(permission)
        incident = report(self)
        act(self, take_incident, incident)
        act(
            self,
            close_incident,
            incident,
            outcome="NO_REPARABLE",
            summary="Diagnóstico final",
            reason="Falla irreparable",
        )
        self.assertTrue(incident.events.filter(action="INC_CLOSED").exists())

    def test_admin_can_discard_invalid_pending_report_without_assigning_someone(self):
        incident = report(self)
        act(
            self,
            close_incident,
            incident,
            actor=self.admin,
            outcome="INVALIDA_DUPLICADA",
            summary="Reporte repetido",
            reason="Revisión del reporte",
        )
        incident.refresh_from_db()
        self.assertIsNone(incident.responsible_id)
        self.assertEqual(incident.outcome, "INVALIDA_DUPLICADA")

    def test_pending_cannot_be_closed_as_solved_and_outcome_summary_are_validated(self):
        incident = report(self)
        with self.assertRaises(ValidationError):
            act(
                self,
                close_incident,
                incident,
                actor=self.admin,
                outcome="SOLUCIONADA",
                summary="No hubo atención",
                reason="Supervisión",
            )
        act(self, take_incident, incident)
        for outcome, summary in [
            ("inventado", "Texto"),
            ("SOLUCIONADA", ""),
            ("SOLUCIONADA", "x" * 3001),
        ]:
            with self.assertRaises(ValidationError):
                act(self, close_incident, incident, outcome=outcome, summary=summary)

    def test_closed_incident_cannot_be_reopened_or_mutated(self):
        incident = report(self)
        act(self, take_incident, incident)
        act(self, close_incident, incident, outcome="SOLUCIONADA", summary="Solución verificada")
        for service, kwargs in [
            (take_incident, {}),
            (add_note, {"note": "Cambiar"}),
            (release_incident, {"reason": "Cambiar", "summary": "Cambiar"}),
            (close_incident, {"outcome": "SOLUCIONADA", "summary": "Cambiar"}),
        ]:
            with self.subTest(service=service.__name__), self.assertRaises(ValidationError):
                act(self, service, incident, **kwargs)

    def test_inactive_reporter_is_not_notified_but_incident_can_be_closed(self):
        incident = report(self)
        act(self, take_incident, incident)
        self.teacher.is_active = False
        self.teacher.save(update_fields=["is_active"])
        act(self, close_incident, incident, outcome="SOLUCIONADA", summary="Verificado")
        self.assertFalse(Notification.objects.filter(kind="INC_CLOSED").exists())

    def test_reporting_and_closing_do_not_change_preventive_dates_or_tasks(self):
        run = recurring_run(self)
        before = (list(run.participants.values()), list(run.tasks.values()))
        incident = report(self)
        act(self, take_incident, incident)
        act(self, close_incident, incident, outcome="SOLUCIONADA", summary="Conexión reparada")
        self.assertEqual((list(run.participants.values()), list(run.tasks.values())), before)
        self.device.refresh_from_db()
        self.assertEqual(self.device.status, Device.Status.OPERATIONAL)

    def test_retention_immutable_report_and_database_state_constraints(self):
        incident = report(self)
        event = incident.events.first()
        with self.assertRaises(ValidationError):
            Incident.objects.filter(pk=incident.pk).update(symptoms="Cambiar")
        incident.symptoms = "Cambiar"
        with self.assertRaises(ValidationError):
            incident.save()
        for instance in [incident, event]:
            with self.assertRaises(ValidationError):
                instance.delete()
        with self.assertRaises(ValidationError):
            IncidentEvent.objects.filter(pk=event.pk).update(action="Cambiar")
        with self.assertRaises(IntegrityError), transaction.atomic():
            incident.state = Incident.State.ATTENDING
            incident.save(update_fields=["state"])

    def test_audit_or_notification_failure_rolls_back_creation(self):
        for target in [
            "apps.incidents.services.IncidentEvent.objects.create",
            "apps.notifications.services.handle_incident_event",
        ]:
            with (
                self.subTest(target=target),
                patch(target, side_effect=RuntimeError("Fallo sintético")),
            ):
                with self.assertRaises(RuntimeError):
                    report(self)
            self.assertFalse(Incident.objects.exists())
            self.assertFalse(IncidentEvent.objects.exists())
            self.assertFalse(Notification.objects.exists())

    def test_notification_failure_rolls_back_take_state_version_and_resolution(self):
        incident = report(self)
        with patch(
            "apps.notifications.services.handle_incident_event",
            side_effect=RuntimeError("Fallo sintético"),
        ):
            with self.assertRaises(RuntimeError):
                act(self, take_incident, incident)
        incident.refresh_from_db()
        self.assertEqual(incident.state, Incident.State.PENDING)
        self.assertEqual(incident.version, 1)
        self.assertEqual(incident.events.count(), 1)
        self.assertEqual(Notification.objects.filter(resolved_at=None).count(), 2)
