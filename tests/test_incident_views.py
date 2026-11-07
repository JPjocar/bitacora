from uuid import uuid4

from django.contrib.auth.models import Permission
from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.incidents.models import Incident
from apps.incidents.services import add_note, close_incident, release_incident, take_incident
from apps.notifications.models import Notification

from .asset_helpers import setup_assets
from .helpers import TEACHER, TECHNICIAN, create_user
from .incident_helpers import act, report
from .recurrence_helpers import recurring_run


class IncidentViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        setup_assets(cls)
        cls.other_teacher = create_user("otro_docente", TEACHER)
        cls.other_technician = create_user("otro_tecnico", TECHNICIAN)

    def url(self, name, incident=None, action=None):
        if name == "report":
            return reverse("incidents:report", args=[self.device.public_id])
        args = [incident.pk] if incident else []
        if action:
            args.append(action)
        return reverse(f"incidents:{name}", args=args)

    def test_all_roles_report_from_device_with_server_owned_fields(self):
        for actor in [self.teacher, self.technician, self.admin]:
            self.client.force_login(actor)
            response = self.client.post(
                self.url("report"),
                {
                    "creation_key": uuid4(),
                    "symptoms": "No conecta a internet",
                    "reporter": self.other_teacher.pk,
                    "responsible": actor.pk,
                    "state": "CERRADA",
                    "closed_by": actor.pk,
                },
            )
            incident = Incident.objects.first()
            self.assertRedirects(response, incident.get_absolute_url())
            self.assertEqual(incident.reporter_id, actor.pk)
            self.assertEqual(incident.state, Incident.State.PENDING)
            self.assertIsNone(incident.responsible_id)

    def test_invalid_report_is_explained_and_no_row_is_written(self):
        self.client.force_login(self.teacher)
        response = self.client.post(self.url("report"), {"symptoms": ""})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertFalse(Incident.objects.exists())

    def test_teacher_sees_only_own_reports_in_list_detail_and_htmx(self):
        mine = report(self, symptoms="Mi falla visible")
        other = report(self, actor=self.other_teacher, symptoms="Reporte ajeno reservado")
        self.client.force_login(self.teacher)
        for headers in [{}, {"HTTP_HX_REQUEST": "true"}]:
            response = self.client.get(self.url("list"), **headers)
            self.assertContains(response, "Mi falla visible")
            self.assertNotContains(response, "Reporte ajeno reservado")
        self.assertEqual(self.client.get(other.get_absolute_url()).status_code, 404)
        self.assertEqual(self.client.get(mine.get_absolute_url()).status_code, 200)

    def test_teacher_cannot_perform_any_attention_action(self):
        incident = report(self)
        self.client.force_login(self.teacher)
        for action in ["tomar", "nota", "liberar", "cerrar"]:
            url = self.url("action", incident, action)
            self.assertEqual(self.client.get(url).status_code, 403)
            self.assertEqual(self.client.post(url, {"version": 1}).status_code, 403)

    def test_foreign_technician_cannot_update_owner_work(self):
        incident = report(self)
        act(self, take_incident, incident)
        self.client.force_login(self.other_technician)
        for action in ["nota", "liberar", "cerrar"]:
            self.assertEqual(
                self.client.post(self.url("action", incident, action), {"version": 2}).status_code,
                403,
            )

    def test_complete_http_workflow_and_repeated_post_is_rejected(self):
        incident = report(self)
        self.client.force_login(self.technician)
        self.assertRedirects(
            self.client.post(self.url("action", incident, "tomar"), {"version": 1}),
            incident.get_absolute_url(),
        )
        self.assertRedirects(
            self.client.post(
                self.url("action", incident, "nota"),
                {"version": 2, "note": "Comprobación de puertos"},
            ),
            incident.get_absolute_url(),
        )
        self.assertRedirects(
            self.client.post(
                self.url("action", incident, "liberar"),
                {"version": 3, "reason": "Continuar mañana", "summary": "Puertos comprobados"},
            ),
            incident.get_absolute_url(),
        )
        self.assertRedirects(
            self.client.post(self.url("action", incident, "tomar"), {"version": 4}),
            incident.get_absolute_url(),
        )
        values = {"version": 5, "outcome": "SOLUCIONADA", "summary": "Conectividad verificada"}
        self.assertRedirects(
            self.client.post(self.url("action", incident, "cerrar"), values),
            incident.get_absolute_url(),
        )
        response = self.client.post(self.url("action", incident, "cerrar"), values)
        self.assertContains(response, "La incidencia cambió")
        self.assertEqual(incident.events.filter(action="INC_CLOSED").count(), 1)

    def test_no_unrepairable_option_or_permission_for_default_technician(self):
        incident = report(self)
        act(self, take_incident, incident)
        self.client.force_login(self.technician)
        response = self.client.get(self.url("action", incident, "cerrar"))
        self.assertNotContains(response, 'value="NO_REPARABLE"')
        response = self.client.post(
            self.url("action", incident, "cerrar"),
            {
                "version": 2,
                "outcome": "NO_REPARABLE",
                "summary": "Daño confirmado",
                "reason": "Diagnóstico",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        incident.refresh_from_db()
        self.assertEqual(incident.state, Incident.State.ATTENDING)

    def test_admin_can_close_unrepairable_with_audited_justification(self):
        incident = report(self)
        act(self, take_incident, incident)
        self.client.force_login(self.admin)
        response = self.client.post(
            self.url("action", incident, "cerrar"),
            {
                "version": 2,
                "outcome": "NO_REPARABLE",
                "summary": "Falla no reparable",
                "reason": "Daño técnico verificado",
            },
        )
        self.assertRedirects(response, incident.get_absolute_url())
        self.assertEqual(
            incident.events.first().changes["reason"]["después"], "Daño técnico verificado"
        )

    def test_teacher_gets_public_progress_and_closure_but_not_internal_notes(self):
        incident = report(self)
        act(self, take_incident, incident)
        act(self, add_note, incident, note="Nota técnica interna reservada")
        act(
            self,
            release_incident,
            incident,
            summary="Prueba interna privada",
            reason="Motivo interno privado",
        )
        act(self, take_incident, incident)
        act(
            self,
            close_incident,
            incident,
            summary="Solución pública verificada",
            outcome="SOLUCIONADA",
        )
        self.client.force_login(self.teacher)
        response = self.client.get(incident.get_absolute_url())
        self.assertContains(response, "Solución pública verificada")
        for private in [
            "Nota técnica interna reservada",
            "Prueba interna privada",
            "Motivo interno privado",
        ]:
            self.assertNotContains(response, private)
        self.client.force_login(self.admin)
        response = self.client.get(incident.get_absolute_url())
        self.assertContains(response, "Nota técnica interna reservada")
        self.assertContains(response, "Prueba interna privada")

    def test_archived_device_report_remains_accessible_to_its_teacher(self):
        incident = report(self)
        self.device.is_active = False
        self.device.save(update_fields=["is_active"])
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.get(incident.get_absolute_url()).status_code, 200)
        self.assertEqual(
            self.client.get(reverse("assets:detail", args=[self.device.public_id])).status_code, 404
        )
        self.assertEqual(self.client.get(self.url("report")).status_code, 404)

    def test_device_sheet_integrates_incidents_and_preventives_with_role_scope(self):
        incident = report(self, symptoms="Mi reporte de ficha")
        other = report(self, actor=self.other_teacher, symptoms="Reporte privado de otro docente")
        recurring_run(self)
        device_url = reverse("assets:detail", args=[self.device.public_id])
        self.client.force_login(self.teacher)
        response = self.client.get(device_url)
        self.assertContains(response, "Reportar incidencia")
        self.assertContains(response, "Mi reporte de ficha")
        self.assertNotContains(response, "Reporte privado de otro docente")
        self.assertNotContains(response, "Historial preventivo del equipo")
        self.client.force_login(self.admin)
        response = self.client.get(device_url)
        self.assertContains(response, other.get_absolute_url())
        self.assertContains(response, incident.get_absolute_url())
        self.assertContains(response, "Historial preventivo del equipo")
        self.assertContains(response, "Ejecución 1")

    def test_counter_and_inbox_for_teacher_include_only_authorized_incident_sources(self):
        incident = report(self)
        act(self, take_incident, incident)
        act(self, close_incident, incident, outcome="SOLUCIONADA", summary="Verificación final")
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("notifications:counter"))
        self.assertContains(response, "1 sin leer")
        notice = Notification.objects.get(kind="INC_CLOSED")
        self.assertRedirects(
            self.client.post(reverse("notifications:read", args=[notice.pk])),
            incident.get_absolute_url(),
        )
        self.assertContains(self.client.get(reverse("notifications:counter")), "0 sin leer")
        self.client.force_login(self.other_teacher)
        self.assertEqual(
            self.client.post(reverse("notifications:read", args=[notice.pk])).status_code, 404
        )

    def test_revoked_full_access_hides_old_staff_incident_notices(self):
        report(self, actor=self.other_teacher)
        notice = Notification.objects.get(kind="INC_NEW", recipient=self.technician)
        # The recipient is still active and can follow own reports, but no longer all reports.
        self.technician.groups.clear()
        for code, app in [
            ("view_own_incident", "incidents"),
            ("view_notification", "notifications"),
        ]:
            self.technician.user_permissions.add(
                Permission.objects.get(content_type__app_label=app, codename=code)
            )
        self.client.force_login(self.technician)
        self.assertContains(self.client.get(reverse("notifications:counter")), "0 sin leer")
        self.assertEqual(
            self.client.post(reverse("notifications:read", args=[notice.pk])).status_code, 404
        )

    def test_filters_pagination_and_empty_errors(self):
        for number in range(21):
            report(self, symptoms=f"Síntoma {number}")
        self.client.force_login(self.teacher)
        response = self.client.get(self.url("list"))
        self.assertEqual(len(response.context["page_obj"]), 20)
        self.assertTrue(response.context["page_obj"].has_next())
        for filters in [
            {"q": self.device.code.lower()},
            {"location": self.origin.pk},
            {"kind": "PC"},
            {"state": "PENDIENTE_ATENCION"},
        ]:
            self.assertEqual(
                self.client.get(self.url("list"), filters).context["page_obj"].paginator.count, 21
            )
        self.assertEqual(
            self.client.get(self.url("list"), {"outcome": "SOLUCIONADA"})
            .context["page_obj"]
            .paginator.count,
            0,
        )
        response = self.client.get(self.url("list"), {"start": "2026-12-01", "end": "2026-01-01"})
        self.assertContains(response, "Revise los filtros")
        self.assertEqual(response.context["page_obj"].paginator.count, 0)

    def test_htmx_restoration_returns_full_document(self):
        self.client.force_login(self.teacher)
        response = self.client.get(self.url("list"), HTTP_HX_REQUEST="true")
        self.assertContains(response, 'id="incident-results"', count=1)
        self.assertNotContains(response, "<!doctype")
        response = self.client.get(
            self.url("list"), HTTP_HX_REQUEST="true", HTTP_HX_HISTORY_RESTORE_REQUEST="true"
        )
        self.assertContains(response, "<!doctype")

    def test_csrf_methods_and_gets_do_not_mutate(self):
        incident = report(self)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.technician)
        action_url = self.url("action", incident, "tomar")
        self.assertEqual(client.post(action_url, {"version": 1}).status_code, 403)
        self.assertEqual(client.get(action_url).status_code, 200)
        token = client.cookies["csrftoken"].value
        self.assertEqual(client.put(action_url, HTTP_X_CSRFTOKEN=token).status_code, 405)
        with CaptureQueriesContext(connection) as queries:
            self.assertEqual(self.client.get(self.url("list")).status_code, 302)
            self.assertEqual(client.get(action_url).status_code, 200)
        self.assertFalse(
            any(
                query["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
                for query in queries
            )
        )
        self.assertEqual(
            client.post(action_url, {"version": 1, "csrfmiddlewaretoken": token}).status_code, 302
        )

    def test_xss_not_rendered_in_report_or_notes_and_no_store(self):
        incident = report(self, symptoms="<script>alert('fallo')</script>")
        act(self, take_incident, incident)
        act(self, add_note, incident, note="<img src=x onerror=alert(1)>")
        self.client.force_login(self.admin)
        response = self.client.get(incident.get_absolute_url())
        self.assertNotContains(response, "<script>alert('fallo')</script>")
        self.assertNotContains(response, "<img src=x onerror=alert(1)>")
        self.assertContains(response, "&lt;script&gt;")
        self.assertIn("no-store", response["Cache-Control"])

    def test_unknown_action_is_404_and_inactive_session_redirects(self):
        incident = report(self)
        self.client.force_login(self.technician)
        self.assertEqual(
            self.client.get(self.url("action", incident, "reasignar")).status_code, 404
        )
        self.technician.is_active = False
        self.technician.save(update_fields=["is_active"])
        self.assertEqual(self.client.get(incident.get_absolute_url()).status_code, 302)

    def test_teacher_cannot_read_a_maintenance_notice_even_if_it_was_addressed_to_them(self):
        run = recurring_run(self)
        notice = Notification.objects.create(
            recipient=self.teacher,
            kind="AVAILABLE",
            event=run.events.first(),
            event_key="legacy:test",
            title="Aviso técnico restringido",
            description="No visible",
        )
        self.client.force_login(self.teacher)
        self.assertContains(self.client.get(reverse("notifications:counter")), "0 sin leer")
        self.assertNotContains(
            self.client.get(reverse("notifications:inbox")), "Aviso técnico restringido"
        )
        self.assertEqual(
            self.client.post(reverse("notifications:read", args=[notice.pk])).status_code, 404
        )

    def test_teacher_filter_does_not_disclose_unrelated_locations(self):
        report(self)
        self.client.force_login(self.teacher)
        response = self.client.get(self.url("list"))
        self.assertContains(response, self.origin.name)
        self.assertNotContains(response, self.destination.name)
        self.assertNotContains(response, self.other.name)
