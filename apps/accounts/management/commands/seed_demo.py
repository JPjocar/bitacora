import secrets

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import User, UserEvent
from apps.accounts.roles import ADMINISTRATOR, TEACHER, TECHNICIAN, sync_roles
from apps.accounts.services import save_user
from apps.locations.models import Location
from apps.locations.services import save_location


class Command(BaseCommand):
    help = "Crea datos ficticios únicamente en desarrollo, con contraseñas aleatorias."

    def add_arguments(self, parser):
        parser.add_argument("--confirm-demo", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG or not options["confirm_demo"]:
            raise CommandError(
                "Requiere DEBUG=True y --confirm-demo. Nunca ejecutar en producción."
            )
        sync_roles()
        if User.objects.filter(username__startswith="demo_").exists():
            raise CommandError("Ya existen cuentas demo; no se alteraron sus contraseñas ni datos.")
        password = secrets.token_urlsafe(18)
        admin = User.objects.create_user(
            username="demo_admin", password=password, first_name="Administración demo"
        )
        admin.groups.add(Group.objects.get(name=ADMINISTRATOR))
        UserEvent.objects.create(actor=admin, subject=admin, action="Creación demo")
        credentials = [(admin.username, password)]
        for username, role in [("demo_tecnico", TECHNICIAN), ("demo_docente", TEACHER)]:
            password = secrets.token_urlsafe(18)
            save_user(
                actor=admin,
                data={"username": username, "role": role, "is_active": True},
                password=password,
            )
            credentials.append((username, password))
        for name, code, kind in [
            ("Laboratorio de demostración", "DEMO-LAB", Location.Kind.LABORATORY),
            ("Almacén de demostración", "DEMO-ALM", Location.Kind.STORAGE),
            ("Taller de demostración", "DEMO-TAL", Location.Kind.MAINTENANCE),
        ]:
            if not Location.objects.filter(code=code).exists():
                save_location(actor=admin, data={"name": name, "code": code, "kind": kind})
        self.stdout.write("Datos sintéticos creados. Cambie las contraseñas desde Mi perfil:")
        for username, password in credentials:
            self.stdout.write(f"{username}: {password}")
