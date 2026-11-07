from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.http.request import validate_host

from apps.accounts.models import User
from apps.accounts.roles import ADMINISTRATOR, ROLE_PERMISSIONS


class Command(BaseCommand):
    help = "Comprueba configuración, migraciones, roles, estáticos y privilegios. No escribe."

    def add_arguments(self, parser):
        parser.add_argument("--allow-demo", action="store_true")

    def handle(self, *args, **options):
        if settings.DEBUG:
            raise CommandError("El piloto requiere DEBUG=False.")
        call_command("check", deploy=True, fail_level="WARNING", stdout=self.stdout)
        if "*" in settings.ALLOWED_HOSTS:
            raise CommandError("ALLOWED_HOSTS debe contener nombres explícitos.")
        origin = settings.BITACORA_PUBLIC_URL.rstrip("/")
        if not validate_host(urlsplit(origin).hostname, settings.ALLOWED_HOSTS):
            raise CommandError("El origen público no pertenece a ALLOWED_HOSTS.")
        if origin not in settings.CSRF_TRUSTED_ORIGINS:
            raise CommandError("Incluya el origen HTTPS del piloto en CSRF_TRUSTED_ORIGINS.")
        executor = MigrationExecutor(connection)
        if executor.migration_plan(executor.loader.graph.leaf_nodes()):
            raise CommandError("Hay migraciones pendientes; aplíquelas con la cuenta de migración.")
        for name, labels in ROLE_PERMISSIONS.items():
            group = Group.objects.filter(name=name).first()
            actual = (
                set()
                if group is None
                else {
                    f"{permission.content_type.app_label}.{permission.codename}"
                    for permission in group.permissions.select_related("content_type")
                }
            )
            if actual != labels:
                raise CommandError(
                    f"Revise el grupo {name}; ejecute sync_roles con la cuenta de gestión."
                )
        if not User.objects.filter(is_active=True, groups__name=ADMINISTRATOR).exists():
            raise CommandError("Cree un administrador de negocio activo antes del piloto.")
        if (
            not options["allow_demo"]
            and User.objects.filter(is_active=True, username__startswith="demo_").exists()
        ):
            raise CommandError(
                "Hay cuentas demo activas; --allow-demo solo corresponde al piloto sintético."
            )
        for asset in [
            "vendor/bootstrap.min.css",
            "vendor/htmx.min.js",
            "vendor/html5-qrcode.min.js",
            "js/app.js",
        ]:
            if not (settings.STATIC_ROOT / asset).is_file():
                raise CommandError("Faltan estáticos recolectados; ejecute collectstatic.")
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT rolsuper, rolcreatedb, rolcreaterole "
                "FROM pg_roles WHERE rolname=current_user"
            )
            if any(cursor.fetchone()):
                raise CommandError(
                    "La cuenta PostgreSQL de ejecución no debe ser superusuario "
                    "ni crear bases/roles."
                )
        self.stdout.write(
            self.style.SUCCESS(
                "Piloto: configuración y precondiciones verificadas; sin cambios de datos."
            )
        )
