"""Validate an alumni source before writing anything to the database."""

import csv
import json
from collections import Counter
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from directory.choices import normalize_field_of_study, normalize_roll_scope, normalize_roll_serial
from directory.management.commands.import_alumni import (
    dedupe_key,
    normalize_batch,
    split_name,
)
from directory.models import Alumnus


def _value(row, *keys):
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return ""


class Command(BaseCommand):
    help = "Validate alumni CSV/JSON sources without changing the database."

    def add_arguments(self, parser):
        parser.add_argument("--csv", help="CSV source to validate.")
        parser.add_argument("--json", help="Reference JSON source to validate.")
        parser.add_argument("--format", choices=("text", "json"), default="text")
        parser.add_argument(
            "--fail-on-issues",
            action="store_true",
            help="Return a non-zero status when any issue is found.",
        )

    def handle(self, *args, **options):
        csv_path = options.get("csv")
        json_path = options.get("json")
        if not csv_path and not json_path:
            data_dir = Path(settings.BASE_DIR) / "data"
            csv_path = data_dir / "list_for_alumni.csv"
            json_path = data_dir / "doece_dump.json"

        records = []
        issues = Counter()
        if csv_path:
            self._read_csv(csv_path, records, issues)
        if json_path:
            self._read_json(json_path, records, issues)

        identity_keys = [row["identity"] for row in records if row["identity"]]
        roll_keys = [
            (row["batch"], row["scope"], normalize_roll_serial(row["roll"]))
            for row in records
            if row["roll"] and row["scope"] and row["batch"]
        ]
        identity_counts = Counter(identity_keys)
        roll_counts = Counter(roll_keys)
        issues["duplicate_identity"] += sum(
            count - 1 for count in identity_counts.values() if count > 1
        )
        issues["duplicate_roll"] += sum(
            count - 1 for count in roll_counts.values() if count > 1
        )

        existing = {
            (
                field,
                batch,
                (first or "").strip().lower(),
                (last or "").strip().lower(),
            )
            for field, batch, first, last in Alumnus.objects.values_list(
                "field_of_study", "batch", "first_name", "last_name"
            )
        }
        issues["already_in_database"] = sum(
            1
            for row in records
            if row["identity"]
            and (
                row["field"],
                row["batch"],
                row["first"],
                row["last"],
            )
            in existing
        )
        result = {
            "rows_read": len(records),
            "issues": dict(issues),
            "ready": not any(issues.values()),
        }
        if options["format"] == "json":
            self.stdout.write(json.dumps(result, indent=2, sort_keys=True))
        else:
            self.stdout.write(f"Rows read: {result['rows_read']:,}")
            if issues:
                for key, value in sorted(issues.items()):
                    if value:
                        self.stdout.write(self.style.WARNING(f"{key}: {value:,}"))
            else:
                self.stdout.write(self.style.SUCCESS("No validation issues found."))
        if options["fail_on_issues"] and any(issues.values()):
            raise CommandError("The source contains validation issues.")

    def _append(self, raw, records, issues):
        first, middle, last = split_name(
            _value(raw, "name", "full_name", "student_name")
        )
        first = _value(raw, "first_name", "firstname") or first
        last = _value(raw, "last_name", "lastname", "surname") or last
        field = normalize_field_of_study(
            _value(raw, "field_of_study", "department", "program", "faculty")
        )
        batch = normalize_batch(_value(raw, "batch", "year", "be_batch_bs"))
        roll = _value(raw, "class_roll_no", "roll_number", "roll", "ioe_roll_number")
        if not first:
            issues["missing_first_name"] += 1
        if not last:
            issues["missing_last_name"] += 1
        if not batch:
            issues["missing_batch"] += 1
        identity = dedupe_key(field, batch, first, last) if first or last else ""
        records.append(
            {
                "identity": identity,
                "field": field,
                "batch": batch,
                "first": first.lower(),
                "last": last.lower(),
                "roll": roll,
                "scope": normalize_roll_scope(roll, field),
            }
        )

    def _read_csv(self, path, records, issues):
        source = Path(path)
        if not source.exists():
            issues["missing_csv"] += 1
            return
        with source.open(newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                self._append(row, records, issues)

    def _read_json(self, path, records, issues):
        source = Path(path)
        if not source.exists():
            issues["missing_json"] += 1
            return
        try:
            objects = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise CommandError(f"Could not parse {source}: {exc}") from exc
        for obj in objects:
            if obj.get("model") != "records.student":
                continue
            fields = obj.get("fields", {})
            self._append(fields, records, issues)
