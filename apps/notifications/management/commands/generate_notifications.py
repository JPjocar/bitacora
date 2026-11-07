from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.maintenance.models import Maintenance
from apps.notifications.services import generate_for_maintenance


class Command(BaseCommand):
    help = "Genera avisos internos idempotentes de disponibilidad y vencimientos (hora de Lima)."

    def handle(self, *args, **options):
        created, errors = 0, []
        for pk in Maintenance.objects.order_by("pk").values_list("pk", flat=True).iterator():
            try:
                created += generate_for_maintenance(pk)
            except ValidationError as exc:
                errors.append(pk)
                self.stderr.write(f"Mantenimiento {pk}: {exc}")
        self.stdout.write(f"Notificaciones nuevas: {created}.")
        if errors:
            raise CommandError(f"Revise configuraciones inválidas: {errors}.")
