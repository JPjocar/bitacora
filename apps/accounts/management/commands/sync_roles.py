from django.core.management.base import BaseCommand

from apps.accounts.roles import sync_roles


class Command(BaseCommand):
    help = "Sincroniza únicamente los tres roles y sus permisos de esta versión."

    def handle(self, *args, **options):
        sync_roles()
        self.stdout.write(self.style.SUCCESS("Roles sincronizados."))
