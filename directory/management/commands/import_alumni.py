"""Import alumni data from the provided data sources.

Two complementary sources are used so every filter has real data to work with:

* a JSON dump from the reference DOECE app — rich records for Computer &
  Electronics alumni: employer, current city, current country, further study.
* a campus-wide CSV roster — used for every *other* field of study (Civil,
  Electrical, Mechanical, Architecture, ...), giving the directory its breadth.
  DOECE rows are skipped here to avoid duplicating the richer JSON records.

The full data sources are large and not committed; place them under ``data/``
(see the README) and run this command. For a quick out-of-the-box dataset,
load the bundled demo fixture instead: ``python manage.py loaddata demo``.

Usage:
    python manage.py import_alumni                       # reads data/*.csv,*.json
    python manage.py import_alumni --flush               # wipe unclaimed first
    python manage.py import_alumni --csv path --json path
"""

import csv
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from directory.choices import (
    FIELD_COMPUTER,
    FIELD_ELECTRONICS,
    normalize_field_of_study,
    normalize_gender,
)
from directory.models import Alumnus

# Map the reference dump's BE program codes to canonical fields of study.
_BE_PROGRAM_FIELD = {
    "BCT": FIELD_COMPUTER,
    "BEX": FIELD_ELECTRONICS,
    "BEI": FIELD_ELECTRONICS,
}

# Map messy free-text country names in the CSV to ISO codes.
_COUNTRY_NAME_TO_CODE = {
    "nepal": "NP",
    "india": "IN",
    "usa": "US",
    "myanmar": "MM",
}


def split_name(full_name):
    parts = (full_name or "").split()
    if not parts:
        return "", "", ""
    if len(parts) == 1:
        return parts[0], "", ""
    if len(parts) == 2:
        return parts[0], "", parts[1]
    return parts[0], " ".join(parts[1:-1]), parts[-1]


def country_code_from_name(name):
    return _COUNTRY_NAME_TO_CODE.get((name or "").strip().lower(), "")


class Command(BaseCommand):
    help = "Import alumni records from the CSV roster and the DOECE JSON dump."

    def add_arguments(self, parser):
        # Point at the full data sources placed under data/ (not committed;
        # see the README). For instant demo data use `loaddata demo` instead.
        data_dir = Path(settings.BASE_DIR) / "data"
        parser.add_argument("--csv", default=str(data_dir / "list_for_alumni.csv"))
        parser.add_argument("--json", default=str(data_dir / "doece_dump.json"))
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete existing unclaimed records before importing.",
        )

    def handle(self, *args, **opts):
        if opts["flush"]:
            deleted, _ = Alumnus.objects.filter(user_account__isnull=True).delete()
            self.stdout.write(self.style.WARNING(f"Flushed {deleted} unclaimed records."))

        json_count = self._import_json(opts["json"])
        csv_count = self._import_csv(opts["csv"])

        total = Alumnus.objects.count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {json_count} DOECE records and {csv_count} roster records. "
                f"Directory now holds {total} alumni."
            )
        )

    # -- JSON (rich DOECE records) ------------------------------------------
    def _import_json(self, path):
        p = Path(path)
        if not p.exists():
            self.stdout.write(self.style.WARNING(f"JSON not found at {p}; skipping."))
            return 0

        objects = json.loads(p.read_text(encoding="utf-8"))
        students = {o["pk"]: o["fields"] for o in objects if o["model"] == "records.student"}

        # Group addresses and further-academic records by student pk.
        addresses = {}
        further = {}
        for o in objects:
            if o["model"] == "records.address":
                addresses.setdefault(o["fields"]["student"], []).append(o["fields"])
            elif o["model"] == "records.furtheracademicstatus":
                further.setdefault(o["fields"]["student"], []).append(o["fields"])

        created = 0
        with transaction.atomic():
            for pk, s in students.items():
                field = _BE_PROGRAM_FIELD.get(s.get("be_program") or "", "")
                if not field:
                    # Fall back to program-type text if BE program is missing.
                    field = normalize_field_of_study(s.get("msc_program") or "")

                current_city = current_country = ""
                perm_district = perm_country = ""
                for addr in addresses.get(pk, []):
                    place = addr.get("city") or addr.get("vdc_municipality") or addr.get("district") or ""
                    if addr.get("address_type") == "Current":
                        current_city = place
                        current_country = addr.get("country") or ""
                    elif addr.get("address_type") == "Permanent":
                        perm_district = addr.get("district") or place
                        perm_country = addr.get("country") or ""

                fa = (further.get(pk) or [None])[0]

                batch = (s.get("be_batch_bs") or s.get("msc_batch_bs") or "") or ""
                roll = s.get("be_ioe_roll_number") or s.get("be_roll_number") or ""

                Alumnus.objects.create(
                    first_name=(s.get("first_name") or "").strip(),
                    middle_name=(s.get("middle_name") or "").strip(),
                    last_name=(s.get("last_name") or "").strip(),
                    gender=normalize_gender(s.get("gender")),
                    date_of_birth_bs=(s.get("dob_bs") or "").strip(),
                    field_of_study=field,
                    department_raw="Electronics & Computer Engineering (DOECE)",
                    batch=str(batch).strip(),
                    class_roll_no=str(roll).strip(),
                    current_city=current_city.strip() if current_city else "",
                    current_country=current_country or "",
                    permanent_district=perm_district.strip() if perm_district else "",
                    permanent_country=perm_country or "",
                    employment_status=(s.get("employment_status") or "").strip(),
                    employer_organization=(s.get("currently_employed_organization") or "").strip(),
                    job_title=(s.get("current_post_in_organization") or "").strip(),
                    further_study_institution=(fa.get("institution") if fa else "") or "",
                    further_study_country=(fa.get("country") if fa else "") or "",
                    email=(s.get("email") or "").strip(),
                    contact_number=(s.get("contact_number") or "").strip(),
                    linkedin_url=self._clean_url(s.get("linked_in_id")),
                    website=self._clean_url(s.get("website")),
                )
                created += 1
        return created

    # -- CSV (breadth across all faculties) ---------------------------------
    def _import_csv(self, path):
        p = Path(path)
        if not p.exists():
            self.stdout.write(self.style.WARNING(f"CSV not found at {p}; skipping."))
            return 0

        created = 0
        with p.open(newline="", encoding="utf-8") as fh, transaction.atomic():
            for row in csv.DictReader(fh):
                field = normalize_field_of_study(row.get("facultyName"))
                # DOECE fields already come from the richer JSON source.
                if field in {FIELD_COMPUTER, FIELD_ELECTRONICS}:
                    continue

                first, middle, last = split_name(row.get("fullName"))
                if not first:
                    continue
                country = country_code_from_name(row.get("countryName"))

                Alumnus.objects.create(
                    first_name=first,
                    middle_name=middle,
                    last_name=last,
                    gender=normalize_gender(row.get("gender")),
                    date_of_birth_bs=(row.get("dobBs") or "").strip(),
                    field_of_study=field,
                    department_raw=(row.get("facultyName") or "").strip(),
                    batch=(row.get("batch") or "").strip(),
                    class_roll_no=(row.get("classRollNo") or "").strip(),
                    # The roster records home addresses, so treat them as
                    # permanent; current location is left for alumni to fill in.
                    current_city=(row.get("district") or "").strip(),
                    current_country=country,
                    permanent_district=(row.get("district") or "").strip(),
                    permanent_country=country,
                )
                created += 1
        return created

    @staticmethod
    def _clean_url(value):
        if not value:
            return ""
        value = value.strip()
        if value and not value.startswith(("http://", "https://")):
            return "https://" + value
        return value
