from django.core.management.base import BaseCommand

from apps.core.pilot_backup import create_backup


class Command(BaseCommand):
    help = "Respalda PostgreSQL y media con snapshot consistente y manifiesto de integridad."

    def add_arguments(self, parser):
        parser.add_argument("directory")
        parser.add_argument("--pg-bin")

    def handle(self, *args, **options):
        manifest = create_backup(options["directory"], pg_bin=options["pg_bin"])
        self.stdout.write(
            f"Backup creado: {len(manifest['tables'])} tablas, "
            f"{len(manifest['media_files'])} archivos media. "
            "Verifique la restauración antes de aceptarlo."
        )
