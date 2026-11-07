from django.core.management.base import BaseCommand

from apps.core.pilot_backup import verify_backup


class Command(BaseCommand):
    help = "Restaura y verifica un backup en una BD aleatoria nueva; nunca sobrescribe la fuente."

    def add_arguments(self, parser):
        parser.add_argument("directory")
        parser.add_argument("--pg-bin")

    def handle(self, *args, **options):
        manifest = verify_backup(options["directory"], pg_bin=options["pg_bin"])
        self.stdout.write(
            f"Restauración verificada: {len(manifest['tables'])} tablas idénticas, "
            "restricciones/secuencias y media correctas. BD temporal eliminada; fuente intacta."
        )
