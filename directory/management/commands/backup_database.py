"""Create a consistent, non-overwriting database backup."""

import sqlite3
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Back up the SQLite database to a new file."

    def add_arguments(self, parser):
        parser.add_argument("--output", help="Backup path; defaults to backups/*.sqlite3.")

    def handle(self, *args, **options):
        database = settings.DATABASES["default"]
        if database.get("ENGINE") != "django.db.backends.sqlite3":
            raise CommandError(
                "This command is for SQLite. Use your database provider's "
                "native backup or pg_dump for production PostgreSQL."
            )
        source = Path(database["NAME"])
        if not source.exists():
            raise CommandError(f"Database file does not exist: {source}")
        output = options.get("output")
        if not output:
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            output = Path(settings.BASE_DIR) / "backups" / f"alumni-{stamp}.sqlite3"
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists():
            raise CommandError(f"Refusing to overwrite existing backup: {output}")

        source_connection = sqlite3.connect(source)
        target_connection = sqlite3.connect(output)
        try:
            source_connection.backup(target_connection)
        finally:
            target_connection.close()
            source_connection.close()
        self.stdout.write(self.style.SUCCESS(f"Database backup written to {output}"))
