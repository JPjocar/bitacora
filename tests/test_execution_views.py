from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.roles import TECHNICIAN
from apps.maintenance.execution import take_maintenance
from apps.maintenance.models import MaintenanceEvent, MaintenanceRun, MaintenanceRunDevice

from .asset_helpers import setup_assets
from .execution_helpers import make_run, operate, progress, start_run
from .helpers import create_user


class ExecutionViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        setup_assets(cls)
        cls.execution = make_run(cls)
        cls.other = create_user("otro-ejecutor", TECHNICIAN)

    def action_url(self, action):
        return reverse("maintenance:run_action", args=[self.execution.pk, action])

    def version(self):
        self.execution.refresh_from_db()
        return {"version": self.execution.version}

    def start(self):
        start_run(self, self.execution)
        self.client.force_login(self.technician)

    def test_anonymous_and_teacher_are_denied_all_operational_routes(self):
        participant = self.execution.participants.get()
        paths = [
            self.action_url("tomar"),
            self.action_url("liberar"),
            reverse("maintenance:device_progress", args=[self.execution.pk, participant.pk]),
            reverse("maintenance:complete_device", args=[self.execution.pk, participant.pk]),
        ]
        for path in paths:
            self.assertEqual(self.client.get(path).status_code, 302)
        self.client.force_login(self.teacher)
        for path in paths:
            self.assertEqual(self.client.get(path).status_code, 403)
            self.assertEqual(self.client.post(path, {"version": 1}).status_code, 403)

    def test_get_confirmation_does_not_take_and_post_returns_to_detail(self):
        self.client.force_login(self.technician)
        events = self.execution.events.count()
        self.assertContains(self.client.get(self.action_url("tomar")), "Tomar mantenimiento")
        self.execution.refresh_from_db()
        self.assertIsNone(self.execution.responsible)
        self.assertEqual(self.execution.events.count(), events)
        response = self.client.post(
            self.action_url("tomar"),
            {"version": 1, "responsible": self.other.pk, "state": "COMPLETADO"},
        )
        self.assertRedirects(
            response, reverse("maintenance:detail", args=[self.execution.maintenance_id])
        )
        self.execution.refresh_from_db()
        self.assertEqual(self.execution.responsible, self.technician)
        self.assertIsNone(self.execution.started_at)
        self.assertEqual(self.execution.state, MaintenanceRun.State.ASSIGNED)

    def test_admin_cannot_take_and_outsider_cannot_release(self):
        self.client.force_login(self.admin)
        self.assertEqual(
            self.client.post(self.action_url("tomar"), {"version": 1}).status_code, 403
        )
        operate(take_maintenance, self, self.execution)
        self.client.force_login(self.other)
        self.assertEqual(
            self.client.post(
                self.action_url("liberar"), {**self.version(), "reason": "Ajeno"}
            ).status_code,
            403,
        )

    def test_take_start_progress_complete_general_close_http_flow(self):
        self.client.force_login(self.technician)
        self.assertEqual(
            self.client.post(self.action_url("tomar"), self.version()).status_code, 302
        )
        self.assertEqual(
            self.client.post(self.action_url("iniciar"), self.version()).status_code, 302
        )
        participant = self.execution.participants.get()
        path = reverse("maintenance:device_progress", args=[self.execution.pk, participant.pk])
        data = {
            **self.version(),
            "notes": "Trabajo verificado",
            **{f"task_{task.pk}": "on" for task in participant.tasks.all()},
        }
        self.assertContains(self.client.get(path), 'name="notes"')
        self.assertEqual(self.client.post(path, data).status_code, 302)
        complete = reverse("maintenance:complete_device", args=[self.execution.pk, participant.pk])
        self.assertEqual(
            self.client.post(
                complete,
                {
                    **self.version(),
                    "verified": "on",
                    "completion_summary": "Verificación final correcta",
                },
            ).status_code,
            302,
        )
        self.assertEqual(
            self.client.post(self.action_url("cerrar"), self.version()).status_code, 200
        )
        group = reverse("maintenance:group_progress", args=[self.execution.pk])
        group_data = {
            **self.version(),
            "notes": "Materiales retirados",
            **{
                f"task_{task.pk}": "on"
                for task in self.execution.tasks.filter(participant__isnull=True)
            },
        }
        self.assertEqual(self.client.post(group, group_data).status_code, 302)
        self.assertEqual(
            self.client.post(self.action_url("cerrar"), self.version()).status_code, 302
        )
        self.execution.refresh_from_db()
        self.assertEqual(self.execution.state, MaintenanceRun.State.COMPLETED)

    def test_progress_is_denied_before_explicit_start(self):
        operate(take_maintenance, self, self.execution)
        self.client.force_login(self.technician)
        path = reverse("maintenance:group_progress", args=[self.execution.pk])
        response = self.client.post(path, {**self.version(), "notes": "No debe guardarse"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "iniciar o reanudar")
        self.execution.refresh_from_db()
        self.assertEqual(self.execution.notes, "")

    def test_stale_or_missing_version_preserves_inputs_and_does_not_write(self):
        self.start()
        path = reverse("maintenance:group_progress", args=[self.execution.pk])
        for data in ({"notes": "Conservar texto"}, {"version": 1, "notes": "Conservar texto"}):
            response = self.client.post(path, data)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Conservar texto")
        self.execution.refresh_from_db()
        self.assertEqual(self.execution.notes, "")

    def test_reopen_checkbox_requires_reason_and_preserves_completed_value(self):
        self.start()
        participant = self.execution.participants.get()
        progress(self, self.execution, participant)
        path = reverse("maintenance:device_progress", args=[self.execution.pk, participant.pk])
        response = self.client.post(path, {**self.version(), "notes": ""})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Explique la rectificación")
        self.assertTrue(participant.tasks.filter(completed=True).exists())

    def test_cannot_post_task_from_another_participant_or_run(self):
        self.start()
        participant = self.execution.participants.get()
        group_task = self.execution.tasks.get(participant__isnull=True)
        path = reverse("maintenance:device_progress", args=[self.execution.pk, participant.pk])
        response = self.client.post(
            path, {**self.version(), f"task_{group_task.pk}": "on", "notes": ""}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "tareas ajenas")
        another_run = make_run(self)
        forged = reverse(
            "maintenance:device_progress",
            args=[self.execution.pk, another_run.participants.get().pk],
        )
        self.assertEqual(self.client.get(forged).status_code, 404)

    def test_complete_without_mandatory_tasks_shows_which_are_missing(self):
        self.start()
        path = reverse(
            "maintenance:complete_device",
            args=[self.execution.pk, self.execution.participants.get().pk],
        )
        response = self.client.post(
            path, {**self.version(), "verified": "on", "completion_summary": "Intento"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Verificar conexiones")
        self.assertIsNone(self.execution.participants.get().device_executed_on)

    def test_technician_date_is_server_today_despite_forged_date(self):
        self.start()
        participant = self.execution.participants.get()
        progress(self, self.execution, participant)
        path = reverse("maintenance:complete_device", args=[self.execution.pk, participant.pk])
        response = self.client.post(
            path,
            {
                **self.version(),
                "verified": "on",
                "completion_summary": "Verificado",
                "device_executed_on": "2000-01-01",
                "finalized_by": self.admin.pk,
            },
        )
        self.assertEqual(response.status_code, 302)
        participant.refresh_from_db()
        self.assertEqual(participant.device_executed_on, timezone.localdate())
        self.assertEqual(participant.finalized_by, self.technician)

    def test_admin_intervention_requires_reason_in_the_form(self):
        self.start()
        self.client.force_login(self.admin)
        response = self.client.post(self.action_url("liberar"), self.version())
        self.assertEqual(response.status_code, 200)
        self.assertIn("reason", response.context["form"].errors)
        response = self.client.post(
            self.action_url("liberar"),
            {**self.version(), "reason": "Trabajo parcial; libera por ausencia del responsable"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.execution.events.get(action="RELEASED").actor, self.admin)

    def test_omit_reason_and_cancel_all_omitted_through_http(self):
        self.start()
        participant = self.execution.participants.get()
        path = reverse("maintenance:omit_device", args=[self.execution.pk, participant.pk])
        self.assertEqual(self.client.post(path, self.version()).status_code, 200)
        self.assertEqual(
            self.client.post(path, {**self.version(), "reason": "Equipo inaccesible"}).status_code,
            302,
        )
        self.assertEqual(
            self.client.post(self.action_url("cerrar"), self.version()).status_code, 200
        )
        self.assertEqual(
            self.client.post(
                self.action_url("cancelar"), {**self.version(), "reason": "Ningún equipo atendido"}
            ).status_code,
            302,
        )
        participant.refresh_from_db()
        self.assertEqual(participant.result, MaintenanceRunDevice.Result.OMITTED)

    def test_detail_buttons_follow_state_and_owner_and_resume_label(self):
        detail = reverse("maintenance:detail", args=[self.execution.maintenance_id])
        self.client.force_login(self.technician)
        self.assertContains(self.client.get(detail), "Tomar mantenimiento")
        self.start()
        self.assertContains(self.client.get(detail), "Registrar avance")
        self.assertNotContains(self.client.get(detail), "Tomar mantenimiento")
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(detail), "Registrar avance")
        self.client.force_login(self.technician)
        self.client.post(
            self.action_url("liberar"),
            {**self.version(), "reason": "Trabajo conservado; cambio de turno"},
        )
        self.client.force_login(self.other)
        self.client.post(self.action_url("tomar"), self.version())
        self.assertContains(self.client.get(detail), "Reanudar mantenimiento")

    def test_state_filter_htmx_and_history_show_actual_spanish_events(self):
        self.start()
        response = self.client.get(
            reverse("maintenance:list"), {"state": "EN_EJECUCION"}, HTTP_HX_REQUEST="true"
        )
        self.assertContains(response, "En ejecución")
        self.assertNotContains(response, "<!doctype")
        empty = self.client.get(reverse("maintenance:list"), {"state": "COMPLETADO"})
        self.assertContains(empty, "No se encontraron")
        history = self.client.get(
            reverse("maintenance:history", args=[self.execution.maintenance_id])
        )
        self.assertContains(history, "Mantenimiento tomado")
        self.assertContains(history, "Trabajo iniciado")

    def test_notes_and_observations_are_escaped_and_responses_are_private(self):
        self.start()
        participant = self.execution.participants.get()
        text = "<script>alert(1)</script>"
        progress(
            self,
            self.execution,
            participant,
            notes=text,
            tasks={
                task.pk: {"completed": True, "observation": text}
                for task in participant.tasks.all()
            },
        )
        response = self.client.get(
            reverse("maintenance:detail", args=[self.execution.maintenance_id])
        )
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, text)
        self.assertIn("no-store", response["Cache-Control"])

    def test_csrf_is_required_and_valid_token_allows_take(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.technician)
        self.assertEqual(client.post(self.action_url("tomar"), {"version": 1}).status_code, 403)
        client.get(self.action_url("tomar"))
        response = client.post(
            self.action_url("tomar"),
            {"version": 1, "csrfmiddlewaretoken": client.cookies["csrftoken"].value},
        )
        self.assertEqual(response.status_code, 302)

    def test_unsupported_methods_actions_and_next_cycles_are_unavailable(self):
        self.client.force_login(self.technician)
        self.assertEqual(self.client.delete(self.action_url("tomar")).status_code, 405)
        for action in ("siguiente", "reasignar", "completar"):
            self.assertEqual(
                self.client.post(self.action_url(action), {"version": 1}).status_code, 404
            )

    def test_closed_confirmation_and_duplicate_post_do_not_duplicate_history(self):
        self.start()
        data = {**self.version(), "reason": "Cancelar sin trabajo completado"}
        self.assertEqual(self.client.post(self.action_url("cancelar"), data).status_code, 302)
        count = MaintenanceEvent.objects.count()
        response = self.client.post(self.action_url("cancelar"), data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "cerrada")
        self.assertEqual(MaintenanceEvent.objects.count(), count)
