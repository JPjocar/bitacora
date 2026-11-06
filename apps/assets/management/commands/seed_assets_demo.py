from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.assets.models import Category, Device
from apps.assets.services import move_device, save_device
from apps.locations.models import Location


class Command(BaseCommand):
    help = "Agrega dispositivos y un traslado sintéticos a la demo existente."

    def add_arguments(self, parser):
        parser.add_argument("--confirm-demo", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG or not options["confirm_demo"]:
            raise CommandError("Requiere DEBUG=True y --confirm-demo.")
        actor = User.objects.filter(username="demo_admin", is_active=True).first()
        origin = Location.objects.filter(code="DEMO-LAB", is_active=True).first()
        destination = Location.objects.filter(code="DEMO-TAL", is_active=True).first()
        if not actor or not origin or not destination:
            raise CommandError("Primero ejecute seed_demo --confirm-demo y sync_roles.")
        for name, kind, details in [
            (
                "PC de demostración",
                Category.Kind.PC,
                "RAM: 8 GB; almacenamiento: 256 GB. Datos ficticios.",
            ),
            ("Router de demostración", Category.Kind.ROUTER, "4 puertos LAN. Datos ficticios."),
        ]:
            if Device.objects.filter(name=name).exists():
                continue
            category = Category.objects.filter(kind=kind, is_active=True).first()
            if not category:
                raise CommandError("Faltan categorías activas PC o Router.")
            device = save_device(
                actor=actor,
                data={
                    "name": name,
                    "category_id": category.pk,
                    "location_id": origin.pk,
                    "technical_details": details,
                },
            )
            if kind == Category.Kind.PC:
                move_device(
                    actor=actor,
                    device_id=device.pk,
                    destination_id=destination.pk,
                    expected_version=device.version,
                    reason="Demostración de traslado físico",
                    effective_at=timezone.now(),
                )
        self.stdout.write(
            self.style.SUCCESS(
                "Demo de dispositivos disponible; no se alteraron equipos existentes."
            )
        )
