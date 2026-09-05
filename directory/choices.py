"""
Central choices for the alumni directory.

The source CSV recorded faculty/department names very inconsistently (64 raw
variants with typos and casing differences). We normalise them into a small,
clean set of canonical fields of study so the "field of study" filter is
usable, while keeping the original text on the record for reference.
"""

import re
import unicodedata

# Canonical fields of study used for filtering and display.
FIELD_COMPUTER = "computer"
FIELD_ELECTRONICS = "electronics"
FIELD_ELECTRICAL = "electrical"
FIELD_CIVIL = "civil"
FIELD_MECHANICAL = "mechanical"
FIELD_ARCHITECTURE = "architecture"
FIELD_AEROSPACE = "aerospace"
FIELD_CHEMICAL = "chemical"
FIELD_SCIENCE = "science_humanities"
FIELD_OTHER = "other"

FIELD_OF_STUDY_CHOICES = (
    (FIELD_COMPUTER, "Computer Engineering"),
    (FIELD_ELECTRONICS, "Electronics & Communication Engineering"),
    (FIELD_ELECTRICAL, "Electrical Engineering"),
    (FIELD_CIVIL, "Civil Engineering"),
    (FIELD_MECHANICAL, "Mechanical Engineering"),
    (FIELD_ARCHITECTURE, "Architecture"),
    (FIELD_AEROSPACE, "Aerospace Engineering"),
    (FIELD_CHEMICAL, "Chemical & Applied Sciences"),
    (FIELD_SCIENCE, "Science & Humanities"),
    (FIELD_OTHER, "Other / Interdisciplinary"),
)

# Degree programs offered (used on the registration form). Each maps to a
# canonical field of study so a new alumnus is filed under the right program.
PROGRAM_CHOICES = (
    ("BCT", "BCT — Computer Engineering"),
    ("BEX", "BEX — Electronics & Communication"),
    ("BEI", "BEI — Electronics, Information & Communication"),
    ("BEL", "BEL — Electrical Engineering"),
    ("BCE", "BCE — Civil Engineering"),
    ("BME", "BME — Mechanical Engineering"),
    ("BAR", "BAR — Architecture"),
    ("BAS", "BAS — Aerospace Engineering"),
    ("BCH", "BCH — Chemical Engineering"),
)

PROGRAM_TO_FIELD = {
    "BCT": FIELD_COMPUTER,
    "BEX": FIELD_ELECTRONICS,
    "BEI": FIELD_ELECTRONICS,
    "BEL": FIELD_ELECTRICAL,
    "BCE": FIELD_CIVIL,
    "BME": FIELD_MECHANICAL,
    "BAR": FIELD_ARCHITECTURE,
    "BAS": FIELD_AEROSPACE,
    "BCH": FIELD_CHEMICAL,
}

GENDER_CHOICES = (
    ("Male", "Male"),
    ("Female", "Female"),
    ("Other", "Other"),
)

EMPLOYMENT_STATUS_CHOICES = (
    ("Employed", "Employed"),
    ("Unemployed", "Unemployed"),
    ("Studying", "Studying"),
    ("Retired", "Retired"),
)

# The public forms use the full B.S. year, while imported legacy records may
# store the same batch in the campus' three-digit form (for example, 2078 as
# 078). Keep the user-facing range in one place and let filters support both
# representations without rewriting existing records.
BATCH_YEAR_CHOICES = tuple((str(year), str(year)) for year in range(2051, 2081))


def normalize_batch_year(value):
    """Return the legacy three-digit storage form for a full batch year."""
    batch = str(value or "").strip()
    if len(batch) == 4 and batch.startswith("20"):
        return batch[1:]
    return batch


def batch_year_variants(value):
    """Return full and legacy values that represent the requested batch."""
    batch = str(value or "").strip()
    normalized = normalize_batch_year(batch)
    if len(normalized) == 3 and normalized.isdigit():
        return tuple(dict.fromkeys((batch, normalized, f"2{normalized}")))
    return (batch,) if batch else ()


# Keyword-based normaliser: maps a raw faculty string to a canonical field.
# Order matters — more specific keywords are checked first.
_FIELD_KEYWORDS = (
    ("computer", FIELD_COMPUTER),
    ("knowledge engineering", FIELD_COMPUTER),
    ("information and communication", FIELD_ELECTRONICS),
    ("communicatin", FIELD_ELECTRONICS),  # common typo in the source data
    ("communication", FIELD_ELECTRONICS),
    ("electronics", FIELD_ELECTRONICS),
    ("electrical", FIELD_ELECTRICAL),
    ("egnineering", FIELD_ELECTRICAL),     # "ELECTRICAL EGNINEERING" typo
    ("power system", FIELD_ELECTRICAL),
    ("power electronics", FIELD_ELECTRICAL),
    ("energy", FIELD_ELECTRICAL),
    ("civil", FIELD_CIVIL),
    ("structural", FIELD_CIVIL),
    ("transportation", FIELD_CIVIL),
    ("geo-technical", FIELD_CIVIL),
    ("geotechnical", FIELD_CIVIL),
    ("hydropower", FIELD_CIVIL),
    ("water resources", FIELD_CIVIL),
    ("environmental", FIELD_CIVIL),
    ("construction", FIELD_CIVIL),
    ("disaster", FIELD_CIVIL),
    ("urban planning", FIELD_CIVIL),
    ("climate change", FIELD_CIVIL),
    ("mechanical", FIELD_MECHANICAL),
    ("renewable", FIELD_MECHANICAL),
    ("architech", FIELD_ARCHITECTURE),     # "Architechture" typo
    ("architecture", FIELD_ARCHITECTURE),
    ("building", FIELD_ARCHITECTURE),
    ("aerospace", FIELD_AEROSPACE),
    ("chemical", FIELD_CHEMICAL),
    ("material science", FIELD_CHEMICAL),
    ("applied science", FIELD_CHEMICAL),
    ("science and humanities", FIELD_SCIENCE),
    ("technology and innovation", FIELD_OTHER),
    ("lateral entry", FIELD_OTHER),
)


def normalize_field_of_study(raw):
    """Return a canonical field-of-study code for a raw faculty string.

    Note: "Electronics and Computer Engineering" (the DOECE department) is
    classified as Computer because the 'computer' keyword is checked first.
    """
    if not raw:
        return FIELD_OTHER
    text = str(raw).strip().lower()
    for keyword, code in _FIELD_KEYWORDS:
        if keyword in text:
            return code
    return FIELD_OTHER


def normalize_gender(raw):
    """Map messy source gender values ('1', '2', 'Male', ...) to a choice."""
    if not raw:
        return ""
    text = str(raw).strip().lower()
    if text in {"male", "m", "1"}:
        return "Male"
    if text in {"female", "f", "2"}:
        return "Female"
    if text in {"other", "3"}:
        return "Other"
    return ""


def _canonical_text(raw):
    """Return a stable lowercase key while preserving words for display maps."""
    if not raw:
        return ""
    text = unicodedata.normalize("NFKC", str(raw)).strip().lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[.,;:/()\[\]{}'\"_-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _normalize_organization(raw):
    """Collapse common institution spellings into a comparable key."""
    text = _canonical_text(raw)
    if not text:
        return ""

    text = re.sub(r"\buniv\b", "university", text)
    text = re.sub(r"\binst\b", "institute", text)
    text = re.sub(r"\bi\s*o\s*e\b", "institute of engineering", text)
    text = re.sub(r"\ba\s*i\s*t\b", "asian institute of technology", text)
    text = re.sub(r"\bi\s*i\s*t\b", "indian institute of technology", text)

    # These refer to one campus even when the source reverses the words.
    if (
        "institute of engineering" in text
        and "pulchowk" in text
    ) or ("pulchowk" in text and "institute of engineering" in text):
        return "institute of engineering"

    text = re.sub(r"\b(?:pulchowk\s+)?campus\b", "", text)
    text = re.sub(r"\s+", " ", text).strip(" ,")
    return text


def normalize_institution(raw):
    """Return a canonical key for higher-study institutions.

    Raw institution text remains on the record so the most common original
    spelling can be shown in dropdowns and reports.
    """
    return _normalize_organization(raw)


def normalize_employer(raw):
    """Return a canonical key for employer names and common abbreviations."""
    return _normalize_organization(raw)


def normalize_city(raw):
    """Return a punctuation- and case-insensitive key for current cities."""
    text = _canonical_text(raw)
    return text.title() if text else ""


def normalize_roll_serial(value):
    """Extract the comparable serial from bare or full roll-number formats.

    A serial is not globally unique: batch and program remain part of the
    identity. This helper only makes ``080BCT047`` and ``047`` comparable.
    """
    raw = re.sub(r"\s+", "", str(value or "").upper())
    if not raw:
        return ""
    match = re.search(r"(\d+)$", raw)
    if match:
        return str(int(match.group(1)))
    return raw


def normalize_roll_scope(value, field_of_study="", department_raw=""):
    """Return the program scope encoded in a roll number when available."""
    raw = re.sub(r"\s+", "", str(value or "").upper())
    match = re.search(r"\d{3,4}([A-Z]+)\d+$", raw)
    if match and match.group(1):
        return match.group(1)
    department = _canonical_text(department_raw)
    return department or str(field_of_study or "").strip().lower()
