"""Create reviewable conflict records for scoped duplicate roll identities."""

from itertools import combinations

from django.core.management.base import BaseCommand
from django.db.models import Count

from directory.models import Alumnus, DataConflict


class Command(BaseCommand):
    help = "Scan for duplicate batch/program/roll identities and create DataConflict records."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Report conflicts without creating them.")

    def handle(self, *args, **options):
        groups = Alumnus.objects.exclude(batch="").exclude(roll_number_canonical="").values(
            "batch", "roll_scope_canonical", "roll_number_canonical"
        ).annotate(total=Count("id")).filter(total__gt=1)
        found = created = 0
        for group in groups:
            records = list(Alumnus.objects.filter(
                batch=group["batch"],
                roll_scope_canonical=group["roll_scope_canonical"],
                roll_number_canonical=group["roll_number_canonical"],
            ).order_by("pk"))
            for first, second in combinations(records, 2):
                found += 1
                if options["dry_run"]:
                    continue
                _conflict, was_created = DataConflict.objects.get_or_create(
                    record_a=first,
                    record_b=second,
                    field_name="scoped roll identity",
                    defaults={
                        "value_a": f"{first.batch}/{first.roll_scope_canonical}/{first.roll_number_canonical}",
                        "value_b": f"{second.batch}/{second.roll_scope_canonical}/{second.roll_number_canonical}",
                    },
                )
                created += int(was_created)
        self.stdout.write(self.style.SUCCESS(f"Potential conflicts found: {found}; records created: {created}."))
