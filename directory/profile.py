"""Shared profile-completeness calculations for pages and commands."""

PROFILE_FIELDS = (
    ("gender", "Gender"),
    ("date_of_birth_bs", "Date of birth"),
    ("contact_number", "Contact number"),
    ("permanent_district", "Permanent district"),
    ("current_city", "Current city"),
    ("current_country", "Current country"),
    ("employer_organization", "Employer"),
    ("job_title", "Job title"),
    ("employment_status", "Employment status"),
    ("further_study_institution", "Further-study institution"),
    ("further_study_degree", "Further-study degree"),
    ("further_study_country", "Further-study country"),
)


def profile_completeness(alumnus):
    """Return filled/missing fields and a percentage for one record."""
    missing = []
    for field, label in PROFILE_FIELDS:
        if not str(getattr(alumnus, field, "") or "").strip():
            missing.append({"field": field, "label": label})
    total = len(PROFILE_FIELDS)
    filled = total - len(missing)
    return {
        "total": total,
        "filled": filled,
        "missing": missing,
        "percent": round(filled * 100 / total) if total else 100,
    }
