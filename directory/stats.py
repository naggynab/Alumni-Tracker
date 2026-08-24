"""Database-backed aggregate counts for the department-only report.

The report intentionally counts every record, including unclaimed and private
records, because it is an internal departmental planning tool. Callers must
keep the resulting queryset behind ``department_required``. Each breakdown is
computed with database grouping or conditional aggregates rather than walking
the 11,698 alumni rows in Python.
"""

from django.db.models import Count, Q
from django_countries import Countries

from .choices import (
    EMPLOYMENT_STATUS_CHOICES,
    FIELD_OF_STUDY_CHOICES,
    GENDER_CHOICES,
    PROGRAM_CHOICES,
)
from .models import FollowUp


FIELD_LABELS = dict(FIELD_OF_STUDY_CHOICES)
EMPLOYMENT_LABELS = dict(EMPLOYMENT_STATUS_CHOICES)
GENDER_LABELS = dict(GENDER_CHOICES)
PROGRAM_LABELS = dict(PROGRAM_CHOICES)

_COUNTRIES = Countries()
NEPAL = "NP"
TOP_N = 12


def graduation_year(batch):
    """Return the B.S. graduation year for an enrollment batch."""
    batch = str(batch or "").strip()
    if not batch.isdigit():
        return None
    year = int(batch)
    enrolled = 2000 + year if year < 100 else year
    return enrolled + 4


def _country_label(code):
    return _COUNTRIES.name(code) or code


def _percentage(value, denominator):
    return round(value * 100 / denominator, 1) if denominator else 0


def _tally(
    queryset,
    column,
    total,
    labels=None,
    blank_label="Not recorded",
    order="count",
    limit=None,
    exclude_blank=False,
):
    """Group records by one database column and add display metrics."""
    rows_qs = queryset
    if exclude_blank:
        rows_qs = rows_qs.exclude(**{column: ""})

    raw = list(rows_qs.values(column).annotate(total=Count("id")))
    largest = max((row["total"] for row in raw), default=0) or 1
    denominator = total or 1
    rows = []
    for row in raw:
        value = row[column]
        if callable(labels):
            label = labels(value) if value else ""
        elif labels:
            label = labels.get(value, value)
        else:
            label = value
        rows.append(
            {
                "value": value,
                "label": label or blank_label,
                "sub": "",
                "is_blank": not value,
                "total": row["total"],
                "share": _percentage(row["total"], denominator),
                "bar": round(row["total"] * 100 / largest, 1),
            }
        )

    if order == "count":
        rows.sort(key=lambda row: (-row["total"], str(row["label"])))
    else:
        rows.sort(key=lambda row: (row["is_blank"], str(row["value"])))
    rows = rows[:limit] if limit else rows
    for index, row in enumerate(rows):
        row["chart_y"] = 30 + (index * 28)
    return rows


def _canonical_labels(queryset, canonical_column, raw_column):
    """Map a canonical value to its most common original spelling."""
    grouped = (
        queryset.exclude(**{canonical_column: ""})
        .values(canonical_column, raw_column)
        .annotate(raw_count=Count("id"))
        .order_by(canonical_column, "-raw_count", raw_column)
    )
    labels = {}
    for row in grouped:
        value = row[canonical_column]
        if value not in labels:
            labels[value] = row[raw_column] or value
    return labels


def _coverage(queryset, field, label, total):
    """Return an honest coverage note for a sparse source field."""
    filled = queryset.exclude(**{field: ""}).count()
    return {
        "field": field,
        "label": label,
        "filled": filled,
        "total": total,
        "percent": _percentage(filled, total),
        "note": f"from {filled:,} of {total:,} records ({_percentage(filled, total)}%)",
    }


def _batch_rows(queryset, total):
    """Aggregate cohort totals and abroad shares in one grouped query."""
    abroad_q = ~Q(current_country="") & ~Q(current_country=NEPAL)
    raw = list(
        queryset.exclude(batch="")
        .values("batch")
        .annotate(total=Count("id"), abroad=Count("id", filter=abroad_q))
    )
    raw.sort(key=lambda row: str(row["batch"]))
    largest = max((row["total"] for row in raw), default=0) or 1
    rows = []
    for row in raw:
        row_total = row["total"]
        abroad_share = _percentage(row["abroad"], row_total)
        rows.append(
            {
                "value": row["batch"],
                "label": row["batch"],
                "sub": f"graduating {graduation_year(row['batch'])}"
                if graduation_year(row["batch"])
                else "",
                "total": row_total,
                "abroad": row["abroad"],
                "abroad_share": abroad_share,
                "share": _percentage(row_total, total),
                "bar": round(row_total * 100 / largest, 1),
            }
        )
    for index, row in enumerate(rows):
        row["chart_x"] = 45 + (index * 28)
        row["chart_total_height"] = round(row["total"] * 170 / largest, 1)
        row["chart_total_y"] = 210 - row["chart_total_height"]
        row["chart_share_y"] = 210 - round(row["abroad_share"] * 1.7, 1)
    return rows


def _program_rows(queryset, total):
    """Aggregate each program and its Nepal/abroad split."""
    abroad_q = ~Q(current_country="") & ~Q(current_country=NEPAL)
    raw = list(
        queryset.values("field_of_study").annotate(
            total=Count("id"),
            in_nepal=Count("id", filter=Q(current_country=NEPAL)),
            abroad=Count("id", filter=abroad_q),
        )
    )
    largest = max((row["total"] for row in raw), default=0) or 1
    rows = []
    for row in raw:
        value = row["field_of_study"]
        rows.append(
            {
                "value": value,
                "label": FIELD_LABELS.get(value, value or "Not recorded"),
                "total": row["total"],
                "in_nepal": row["in_nepal"],
                "abroad": row["abroad"],
                "unknown": row["total"] - row["in_nepal"] - row["abroad"],
                "share": _percentage(row["total"], total),
                "bar": round(row["total"] * 100 / largest, 1),
            }
        )
    rows.sort(key=lambda row: (-row["total"], row["label"]))
    return rows


def _adoption_rows(queryset):
    """Show claimed versus unclaimed records per batch."""
    raw = list(
        queryset.exclude(batch="")
        .values("batch")
        .annotate(
            total=Count("id"),
            claimed=Count("id", filter=Q(user_account__isnull=False)),
        )
    )
    raw.sort(key=lambda row: str(row["batch"]))
    return [
        {
            "batch": row["batch"],
            "total": row["total"],
            "claimed": row["claimed"],
            "unclaimed": row["total"] - row["claimed"],
            "claimed_share": _percentage(row["claimed"], row["total"]),
        }
        for row in raw
    ]


def build_report(queryset):
    """Return all aggregate values rendered by the staff-only report."""
    total = queryset.count()
    in_nepal = queryset.filter(current_country=NEPAL).count()
    abroad = queryset.exclude(current_country__in=["", NEPAL]).count()
    unknown = total - in_nepal - abroad
    abroad_qs = queryset.exclude(current_country__in=["", NEPAL])
    nepal_qs = queryset.filter(current_country=NEPAL)

    by_batch = _batch_rows(queryset, total)
    by_field = _program_rows(queryset, total)
    by_country = _tally(
        abroad_qs,
        "current_country",
        abroad,
        labels=_country_label,
        limit=TOP_N,
        exclude_blank=True,
    )
    city_labels = _canonical_labels(nepal_qs, "current_city_canonical", "current_city")
    employer_labels = _canonical_labels(queryset, "employer_canonical", "employer_organization")
    institution_labels = _canonical_labels(
        queryset,
        "further_study_institution_canonical",
        "further_study_institution",
    )
    by_city = _tally(
        nepal_qs.exclude(current_city_canonical=""),
        "current_city_canonical",
        nepal_qs.exclude(current_city_canonical="").count(),
        labels=city_labels,
        limit=TOP_N,
        exclude_blank=True,
    )
    district_qs = queryset.exclude(permanent_district="")
    by_district = _tally(
        district_qs,
        "permanent_district",
        district_qs.count(),
        limit=TOP_N,
        exclude_blank=True,
    )
    employer_qs = queryset.exclude(employer_canonical="")
    study_country_qs = queryset.exclude(further_study_country="")
    study_institution_qs = queryset.exclude(further_study_institution_canonical="")

    coverage = {
        "gender": _coverage(queryset, "gender", "Gender", total),
        "employer": _coverage(queryset, "employer_organization", "employer", total),
        "employment_status": _coverage(queryset, "employment_status", "employment status", total),
        "higher_studies": _coverage(
            queryset, "further_study_institution", "higher studies", total
        ),
        "current_location": _coverage(queryset, "current_country", "current country", total),
        "current_city": _coverage(queryset, "current_city_canonical", "current city", total),
    }
    missing_data = []
    missing_specs = (
        ("Current country", Q(current_country="")),
        ("Current city", Q(current_city_canonical="")),
        ("Employer", Q(employer_canonical="")),
        ("Employment status", Q(employment_status="")),
        ("Further study institution", Q(further_study_institution_canonical="")),
    )
    for label, condition in missing_specs:
        missing = queryset.filter(condition).count()
        missing_data.append(
            {
                "label": label,
                "total": missing,
                "share": _percentage(missing, total),
                "sub": "",
                "bar": 0,
            }
        )
    missing_largest = max((row["total"] for row in missing_data), default=0) or 1
    for row in missing_data:
        row["bar"] = round(row["total"] * 100 / missing_largest, 1)

    return {
        "total": total,
        "registered": queryset.filter(user_account__isnull=False).count(),
        "batches_represented": len(by_batch),
        "countries_represented": queryset.exclude(current_country="").values("current_country").distinct().count(),
        "in_nepal": in_nepal,
        "abroad": abroad,
        "location_unknown": unknown,
        "in_nepal_percent": _percentage(in_nepal, total),
        "abroad_percent": _percentage(abroad, total),
        "unknown_percent": _percentage(unknown, total),
        "employed": queryset.filter(employment_status="Employed").count(),
        "studying": queryset.filter(employment_status="Studying").count(),
        "by_batch": by_batch,
        "by_field": by_field,
        "by_country": by_country,
        "by_city": by_city,
        "by_district": by_district,
        "by_employment": _tally(
            queryset,
            "employment_status",
            coverage["employment_status"]["filled"],
            labels=EMPLOYMENT_LABELS,
            exclude_blank=True,
        ),
        "by_gender": _tally(
            queryset,
            "gender",
            coverage["gender"]["filled"],
            labels=GENDER_LABELS,
            exclude_blank=True,
        ),
        "by_employer": _tally(
            employer_qs,
            "employer_canonical",
            employer_qs.count(),
            labels=employer_labels,
            limit=TOP_N,
            exclude_blank=True,
        ),
        "by_study_country": _tally(
            study_country_qs,
            "further_study_country",
            study_country_qs.count(),
            labels=_country_label,
            limit=TOP_N,
            exclude_blank=True,
        ),
        "by_study_institution": _tally(
            study_institution_qs,
            "further_study_institution_canonical",
            study_institution_qs.count(),
            labels=institution_labels,
            limit=TOP_N,
            exclude_blank=True,
        ),
        "coverage": coverage,
        "missing_data": missing_data,
        "adoption": _adoption_rows(queryset),
    }


def build_comparison(queryset_a, queryset_b, label_a="First cohort", label_b="Second cohort"):
    """Build comparable headline metrics without loading alumni rows."""
    report_a = build_report(queryset_a)
    report_b = build_report(queryset_b)
    metrics = (
        ("Records", "total"),
        ("Registered accounts", "registered"),
        ("Living in Nepal", "in_nepal"),
        ("Living abroad", "abroad"),
        ("Location unknown", "location_unknown"),
        ("Employed", "employed"),
        ("Studying", "studying"),
        ("Nepal share (%)", "in_nepal_percent"),
        ("Abroad share (%)", "abroad_percent"),
        ("Unknown-location share (%)", "unknown_percent"),
    )
    rows = []
    for metric_label, key in metrics:
        left = report_a[key]
        right = report_b[key]
        rows.append(
            {
                "label": metric_label,
                "a": left,
                "b": right,
                "change": round(right - left, 1),
            }
        )
    return {
        "label_a": label_a,
        "label_b": label_b,
        "report_a": report_a,
        "report_b": report_b,
        "rows": rows,
    }


def build_data_quality(queryset):
    """Return actionable data-quality indicators for a staff work queue."""
    total = queryset.count()
    missing_specs = (
        ("Current country", "current_country"),
        ("Current city", "current_city_canonical"),
        ("Employer", "employer_canonical"),
        ("Employment status", "employment_status"),
        ("Further-study institution", "further_study_institution_canonical"),
        ("Contact number", "contact_number"),
    )
    missing = [
        {
            "label": label,
            "field": field,
            "total": queryset.filter(**{field: ""}).count(),
        }
        for label, field in missing_specs
    ]
    for row in missing:
        row["share"] = _percentage(row["total"], total)

    duplicate_names = list(
        queryset.exclude(first_name="")
        .values("first_name", "middle_name", "last_name")
        .annotate(total=Count("id"))
        .filter(total__gt=1)
        .order_by("-total", "first_name", "last_name")[:10]
    )
    duplicate_rolls = list(
        queryset.exclude(batch="")
        .exclude(roll_scope_canonical="")
        .exclude(roll_number_canonical="")
        .values("batch", "roll_scope_canonical", "roll_number_canonical")
        .annotate(total=Count("id"))
        .filter(total__gt=1)
        .order_by("-total", "batch", "roll_scope_canonical", "roll_number_canonical")[:10]
    )
    for row in duplicate_rolls:
        row["roll_number"] = row["roll_number_canonical"]
        scope = row["roll_scope_canonical"]
        row["program"] = PROGRAM_LABELS.get(scope, scope.replace("_", " ").title())
    followups = FollowUp.objects.filter(
        alumnus__in=queryset, status__in=("open", "in_progress")
    ).count()
    incomplete_identity = queryset.filter(
        Q(first_name="") | Q(last_name="") | Q(roll_number_canonical="")
    ).count()
    return {
        "total": total,
        "missing": missing,
        "duplicate_names": duplicate_names,
        "duplicate_rolls": duplicate_rolls,
        "open_followups": followups,
        "incomplete_identity": incomplete_identity,
        "claimed": queryset.filter(user_account__isnull=False).count(),
        "unclaimed": queryset.filter(user_account__isnull=True).count(),
    }
