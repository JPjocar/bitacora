from uuid import NAMESPACE_URL, uuid5

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.assets.models import Device
from apps.maintenance.models import Maintenance
from apps.maintenance.services import save_maintenance


class Command(BaseCommand):
    help = "Crea dos mantenimientos preventivos sintéticos, sin ejecutar tareas."

    def add_arguments(self, parser):
        parser.add_argument("--confirm-demo", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG or not options["confirm_demo"]:
            raise CommandError("Requiere DEBUG=True y --confirm-demo.")
        actor = User.objects.filter(username="demo_admin", is_active=True).first()
        devices = list(
            Device.objects.filter(
                name__in=["PC de demostración", "Router de demostración"], is_active=True
            ).order_by("pk")
        )
        if not actor or len(devices) != 2:
            raise CommandError(
                "Primero ejecute sync_roles, seed_demo y seed_assets_demo con --confirm-demo."
            )
        today = timezone.localdate()
        for recurring in (False, True):
            key = uuid5(NAMESPACE_URL, f"bitacora/demo/maintenance/{recurring}/v1")
            if Maintenance.objects.filter(creation_key=key).exists():
                continue
            data = {
                "name": "Preventivo periódico de demostración"
                if recurring
                else "Preventivo único de demostración",
                "description": (
                    "Datos sintéticos. Primera ejecución pendiente; no acredita trabajo realizado."
                ),
                "is_recurring": recurring,
                "planned_date": None if recurring else today,
                "base_date": today if recurring else None,
                "interval_value": 2 if recurring else None,
                "interval_unit": "MESES" if recurring else "",
            }
            save_maintenance(
                actor=actor,
                data=data,
                device_ids=[device.pk for device in devices] if recurring else [devices[0].pk],
                tasks=[
                    {
                        "name": "Revisar conexiones y limpieza exterior",
                        "scope": "DISPOSITIVO",
                        "required": True,
                    },
                    {"name": "Preparar materiales", "scope": "GRUPAL", "required": True},
                ],
                creation_key=key,
            )
        self.stdout.write(
            self.style.SUCCESS(
                "Demo preventiva disponible. Se conservan los mantenimientos ya existentes."
            )
        )
