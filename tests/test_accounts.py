from io import StringIO
from unittest.mock import patch

from django.contrib.auth import authenticate
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User, UserEvent
from apps.accounts.roles import ROLE_PERMISSIONS, TEACHER, TECHNICIAN, sync_roles
from apps.accounts.services import change_password, reset_password, save_user

from .helpers import PASSWORD, create_user, setup_users, user_data


class AccountTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        setup_users(cls)

    def test_role_matrix_exact_and_idempotent(self):
        sync_roles()
        sync_roles()
        self.assertEqual(Group.objects.count(), 3)
        for role, labels in ROLE_PERMISSIONS.items():
            group = Group.objects.get(name=role)
            self.assertSetEqual(
                {
                    f"{p.content_type.app_label}.{p.codename}"
                    for p in group.permissions.select_related("content_type")
                },
                labels,
            )
        self.assertFalse(self.admin.is_staff)
        self.assertFalse(self.admin.is_superuser)

    def test_create_hashes_password_and_ignores_privilege_injection(self):
        user = save_user(
            actor=self.admin,
            data={"username": "nueva", "role": TEACHER, "is_superuser": True, "is_staff": True},
            password=PASSWORD,
        )
        self.assertTrue(user.check_password(PASSWORD))
        self.assertFalse(user.is_staff or user.is_superuser)
        self.assertEqual(user.business_role.name, TEACHER)
        self.assertEqual(user.events.count(), 1)
        self.assertNotIn(PASSWORD, str(user.events.first().changes))

    def test_weak_password_rolls_back(self):
        with self.assertRaises(ValidationError):
            save_user(actor=self.admin, data={"username": "nueva", "role": TEACHER}, password="123")
        self.assertFalse(User.objects.filter(username="nueva").exists())

    def test_missing_password_rejected(self):
        with self.assertRaises(ValidationError):
            save_user(actor=self.admin, data={"username": "nueva", "role": TEACHER})

    def test_case_insensitive_username_uniqueness_in_db(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create(username="TECNICO")

    def test_service_validates_duplicate_username(self):
        with self.assertRaises(ValidationError):
            save_user(
                actor=self.admin, data={"username": "TECNICO", "role": TEACHER}, password=PASSWORD
            )

    def test_invalid_role_rejected(self):
        with self.assertRaises(ValidationError):
            save_user(
                actor=self.admin,
                data={"username": "nueva", "role": "Superadmin"},
                password=PASSWORD,
            )

    def test_service_denies_technician_teacher_and_stale_inactive_actor(self):
        for actor in (self.technician, self.teacher):
            with self.subTest(actor=actor.username), self.assertRaises(PermissionDenied):
                save_user(
                    actor=actor, data={"username": "nueva", "role": TEACHER}, password=PASSWORD
                )
        self.assertTrue(self.admin.has_perm("accounts.add_user"))
        User.objects.filter(pk=self.admin.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            save_user(
                actor=self.admin, data={"username": "nueva", "role": TEACHER}, password=PASSWORD
            )

    def test_role_assignment_requires_its_permission(self):
        actor = create_user("delegado")
        actor.user_permissions.add(
            Permission.objects.get(codename="change_user", content_type__app_label="accounts")
        )
        with self.assertRaises(PermissionDenied):
            save_user(
                actor=actor,
                user_id=self.technician.pk,
                expected_version=1,
                data=user_data(self.technician, role=TEACHER),
            )

    def test_edit_role_and_deactivate_preserves_identity_and_history(self):
        old_pk = self.technician.pk
        user = save_user(
            actor=self.admin,
            user_id=old_pk,
            expected_version=1,
            data=user_data(self.technician, role=TEACHER, is_active=False),
        )
        self.assertEqual(user.pk, old_pk)
        self.assertFalse(user.is_active)
        self.assertEqual(user.business_role.name, TEACHER)
        self.assertIsNone(authenticate(username=user.username, password=PASSWORD))
        self.assertEqual(user.events.count(), 1)

    def test_no_self_deactivation_or_role_change(self):
        for data in (user_data(self.admin, is_active=False), user_data(self.admin, role=TEACHER)):
            with self.assertRaises(ValidationError):
                save_user(actor=self.admin, user_id=self.admin.pk, expected_version=1, data=data)

    def test_active_flag_must_be_boolean_even_in_service_calls(self):
        with self.assertRaises(ValidationError):
            save_user(
                actor=self.admin,
                user_id=self.admin.pk,
                expected_version=1,
                data=user_data(self.admin, is_active="False"),
            )

    def test_last_administrator_protected(self):
        root = create_user("root", is_superuser=True, is_staff=True)
        with self.assertRaisesMessage(ValidationError, "al menos un administrador"):
            save_user(
                actor=root,
                user_id=self.admin.pk,
                expected_version=1,
                data=user_data(self.admin, is_active=False),
            )

    def test_superuser_cannot_be_edited_or_reset_in_business_service(self):
        root = create_user("root", is_superuser=True, is_staff=True)
        with self.assertRaises(PermissionDenied):
            save_user(actor=self.admin, user_id=root.pk, expected_version=1, data={"role": TEACHER})
        with self.assertRaises(PermissionDenied):
            reset_password(actor=self.admin, user_id=root.pk, password=PASSWORD)

    def test_stale_edit_and_duplicate_submission(self):
        data = user_data(self.technician, first_name="Cambio")
        save_user(actor=self.admin, user_id=self.technician.pk, expected_version=1, data=data)
        with self.assertRaises(ValidationError):
            save_user(actor=self.admin, user_id=self.technician.pk, expected_version=1, data=data)
        self.assertEqual(self.technician.events.count(), 1)

    def test_noop_does_not_add_event(self):
        save_user(
            actor=self.admin,
            user_id=self.technician.pk,
            expected_version=1,
            data=user_data(self.technician),
        )
        self.assertEqual(self.technician.events.count(), 0)

    def test_audit_failure_rolls_back_user(self):
        with (
            patch("apps.accounts.services.UserEvent.objects.create", side_effect=RuntimeError),
            self.assertRaises(RuntimeError),
        ):
            save_user(
                actor=self.admin,
                user_id=self.technician.pk,
                expected_version=1,
                data=user_data(self.technician, first_name="Cambio"),
            )
        self.technician.refresh_from_db()
        self.assertEqual(self.technician.first_name, "")

    def test_user_and_audit_cannot_be_deleted_or_audit_edited(self):
        event = UserEvent.objects.create(actor=self.admin, subject=self.technician, action="Prueba")
        for operation in [
            self.technician.delete,
            lambda: User.objects.filter(pk=self.technician.pk).delete(),
            event.delete,
            lambda: UserEvent.objects.all().update(action="Cambio"),
            event.save,
        ]:
            with self.assertRaises(ValidationError):
                operation()

    def test_reset_password_invalidates_existing_session(self):
        client = Client()
        client.force_login(self.technician)
        new_password = "Otra-Clave-Segura-239!"
        reset_password(actor=self.admin, user_id=self.technician.pk, password=new_password)
        self.assertEqual(client.get(reverse("accounts:profile")).status_code, 302)
        self.technician.refresh_from_db()
        self.assertTrue(self.technician.check_password(new_password))
        self.assertEqual(self.technician.events.first().changes, {})

    def test_personal_change_requires_current_password(self):
        with self.assertRaises(ValidationError):
            change_password(actor=self.technician, old_password="incorrecta", password=PASSWORD)

    def test_login_redirects_safely_and_logout_is_post_only(self):
        response = self.client.post(
            reverse("accounts:login"),
            {
                "username": self.technician.username,
                "password": PASSWORD,
                "next": "https://example.org/",
            },
        )
        self.assertRedirects(response, reverse("home"))
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
        self.assertEqual(self.client.post(reverse("accounts:logout")).status_code, 302)

    def test_inactive_login_denied(self):
        self.technician.is_active = False
        self.technician.save()
        response = self.client.post(
            reverse("accounts:login"), {"username": self.technician.username, "password": PASSWORD}
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_anonymous_and_direct_url_permission_checks(self):
        urls = [
            reverse("accounts:list"),
            reverse("accounts:roles"),
            reverse("accounts:create"),
            reverse("accounts:detail", args=[self.admin.pk]),
            reverse("accounts:edit", args=[self.admin.pk]),
            reverse("accounts:password_reset", args=[self.admin.pk]),
        ]
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 302)
        for actor in (self.teacher, self.technician):
            self.client.force_login(actor)
            for url in urls:
                with self.subTest(url=url, actor=actor):
                    self.assertEqual(self.client.get(url).status_code, 403)
                    self.assertEqual(self.client.post(url, HTTP_HX_REQUEST="true").status_code, 403)

    def test_admin_pages_render(self):
        self.client.force_login(self.admin)
        for name, args in [
            ("home", []),
            ("accounts:list", []),
            ("accounts:roles", []),
            ("accounts:create", []),
            ("accounts:profile", []),
            ("accounts:password_change", []),
            ("accounts:edit", [self.technician.pk]),
            ("accounts:detail", [self.technician.pk]),
            ("accounts:password_reset", [self.technician.pk]),
        ]:
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 200)

    def test_form_create_validation_and_success(self):
        self.client.force_login(self.admin)
        url = reverse("accounts:create")
        bad = self.client.post(
            url, {"username": "nueva", "role": TEACHER, "password1": PASSWORD, "password2": "otra"}
        )
        self.assertContains(bad, "Las contraseñas no coinciden")
        self.assertFalse(User.objects.filter(username="nueva").exists())
        good = self.client.post(
            url,
            {
                "username": "nueva",
                "role": TEACHER,
                "password1": PASSWORD,
                "password2": PASSWORD,
                "is_active": "on",
            },
        )
        self.assertEqual(good.status_code, 302)
        self.assertTrue(User.objects.get(username="nueva").check_password(PASSWORD))

    def test_personal_password_change_retains_current_session(self):
        self.client.force_login(self.technician)
        response = self.client.post(
            reverse("accounts:password_change"),
            {
                "old_password": PASSWORD,
                "new_password1": "Cambio-Seguro-9471!",
                "new_password2": "Cambio-Seguro-9471!",
            },
        )
        self.assertRedirects(response, reverse("accounts:profile"))
        self.assertEqual(self.technician.events.count(), 1)

    def test_csrf_login_logout_and_user_mutations(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post(reverse("accounts:login"), {}).status_code, 403)
        client.force_login(self.admin)
        for url in [
            reverse("accounts:logout"),
            reverse("accounts:create"),
            reverse("accounts:edit", args=[self.technician.pk]),
            reverse("accounts:password_change"),
        ]:
            self.assertEqual(client.post(url, {}).status_code, 403)

    def test_user_filters_and_htmx(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("accounts:list"), {"q": " TEC ", "role": TECHNICIAN}, HTTP_HX_REQUEST="true"
        )
        self.assertContains(response, "tecnico")
        self.assertNotContains(response, "<!doctype html>")
        self.assertEqual(response.context["page_obj"].paginator.count, 1)
        self.assertIn("HX-Request", response["Vary"])

    def test_demo_requires_explicit_confirmation_and_debug(self):
        with self.assertRaises(CommandError):
            call_command("seed_demo", stdout=StringIO())
        with override_settings(DEBUG=False), self.assertRaises(CommandError):
            call_command("seed_demo", confirm_demo=True, stdout=StringIO())

    @override_settings(DEBUG=True)
    def test_demo_synthetic_accounts_no_superuser_and_no_overwrite(self):
        output = StringIO()
        call_command("seed_demo", confirm_demo=True, stdout=output)
        self.assertEqual(
            User.objects.filter(
                username__startswith="demo_", is_superuser=False, is_staff=False
            ).count(),
            3,
        )
        with self.assertRaises(CommandError):
            call_command("seed_demo", confirm_demo=True, stdout=StringIO())
        self.assertIn("demo_docente:", output.getvalue())
