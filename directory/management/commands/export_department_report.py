"""Write a privacy-safe aggregate department report to CSV."""

import csv
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from directory.models import Alumnus
from directory.report_exports import export_rows
from directory.stats import build_report


class Command(BaseCommand):
    help = "Export aggregate department report data to a new CSV file."

    def add_arguments(self, parser):
        parser.add_argument(
            "--breakdown",
            choices=(
                "full", "country", "city", "district", "field", "employment",
                "employer", "study_country", "study_institution", "batch",
                "adoption", "missing_data",
            ),
            default="full",
        )
        parser.add_argument("--output", help="Output CSV path.")
        parser.add_argument("--batch-from", default="")
        parser.add_argument("--batch-to", default="")
        parser.add_argument("--field-of-study", default="")
        parser.add_argument("--country", default="")
        parser.add_argument("--employment-status", default="")

    def handle(self, *args, **options):
        queryset = Alumnus.objects.all()
        if options["batch_from"]:
            queryset = queryset.filter(batch__gte=options["batch_from"])
        if options["batch_to"]:
            queryset = queryset.filter(batch__lte=options["batch_to"])
        if options["field_of_study"]:
            queryset = queryset.filter(field_of_study=options["field_of_study"])
        if options["country"]:
            queryset = queryset.filter(current_country=options["country"])
        if options["employment_status"]:
            queryset = queryset.filter(employment_status=options["employment_status"])

        output = options["output"]
        if not output:
            output = (
                Path(settings.BASE_DIR)
                / "exports"
                / f"department-report-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{options['breakdown']}.csv"
            )
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists():
            raise CommandError(f"Refusing to overwrite existing file: {output}")

        rows = export_rows(build_report(queryset), options["breakdown"])
        with output.open("x", newline="", encoding="utf-8") as handle:
            csv.writer(handle).writerows(rows)
        self.stdout.write(self.style.SUCCESS(f"Wrote {len(rows) - 1:,} aggregate rows to {output}"))
