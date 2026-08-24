"""Show row-level import issues without writing to the database."""

import csv
import json
from collections import Counter
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from directory.choices import normalize_field_of_study, normalize_roll_scope, normalize_roll_serial
from directory.management.commands.import_alumni import dedupe_key, normalize_batch, split_name
from directory.models import Alumnus


def _value(row, *keys):
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return ""


class Command(BaseCommand):
    help = "Preview CSV import rows and report row-level validation issues without changing the database."

    def add_arguments(self, parser):
        parser.add_argument("--csv", required=True, help="CSV file to preview.")
        parser.add_argument("--format", choices=("text", "json"), default="text")
        parser.add_argument("--limit", type=int, default=0, help="Only inspect the first N data rows.")

    def handle(self, *args, **options):
        path = Path(options["csv"])
        issues = []
        rows = []
        if not path.exists():
            issues.append({"row": 0, "issues": [f"File not found: {path}"]})
        else:
            with path.open(newline="", encoding="utf-8-sig") as handle:
                for row_number, raw in enumerate(csv.DictReader(handle), start=2):
                    if options["limit"] and len(rows) >= options["limit"]:
                        break
                    first, _middle, last = split_name(_value(raw, "name", "full_name", "student_name"))
                    first = _value(raw, "first_name", "firstname") or first
                    last = _value(raw, "last_name", "lastname", "surname") or last
                    field = normalize_field_of_study(_value(raw, "field_of_study", "department", "program", "faculty"))
                    batch = normalize_batch(_value(raw, "batch", "year", "be_batch_bs"))
                    roll = _value(raw, "class_roll_no", "roll_number", "roll", "ioe_roll_number")
                    row = {"number": row_number, "first": first.lower(), "last": last.lower(), "field": field, "batch": batch, "roll": roll, "scope": normalize_roll_scope(roll, field)}
                    row_issues = []
                    if not first:
                        row_issues.append("missing first name")
                    if not last:
                        row_issues.append("missing last name")
                    if not batch:
                        row_issues.append("missing batch")
                    if not roll:
                        row_issues.append("missing roll number")
                    rows.append(row)
                    if row_issues:
                        issues.append({"row": row_number, "issues": row_issues})

        identity_counts = Counter(dedupe_key(row["field"], row["batch"], row["first"], row["last"]) for row in rows)
        roll_counts = Counter((row["batch"], row["scope"], normalize_roll_serial(row["roll"])) for row in rows if row["batch"] and row["scope"] and row["roll"])
        for row in rows:
            identity = dedupe_key(row["field"], row["batch"], row["first"], row["last"])
            roll_key = (row["batch"], row["scope"], normalize_roll_serial(row["roll"]))
            if identity_counts[identity] > 1:
                issues.append({"row": row["number"], "issues": ["duplicate name identity in file"]})
            if row["roll"] and roll_counts[roll_key] > 1:
                issues.append({"row": row["number"], "issues": ["duplicate scoped roll number in file"]})

        existing = {
            (field, batch, (first or "").strip().lower(), (last or "").strip().lower())
            for field, batch, first, last in Alumnus.objects.values_list(
                "field_of_study", "batch", "first_name", "last_name"
            )
        }
        for row in rows:
            if (row["field"], row["batch"], row["first"], row["last"]) in existing:
                issues.append({"row": row["number"], "issues": ["matching identity already exists in database"]})
        result = {"file": str(path), "rows_read": len(rows), "issue_count": len(issues), "issues": issues}
        if options["format"] == "json":
            self.stdout.write(json.dumps(result, indent=2))
        else:
            self.stdout.write(f"Rows read: {len(rows):,}")
            self.stdout.write(f"Rows with issues: {len({item['row'] for item in issues}):,}")
            for item in issues[:100]:
                self.stdout.write(self.style.WARNING(f"Row {item['row']}: {', '.join(item['issues'])}"))
