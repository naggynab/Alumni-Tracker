"""
Central choices for the alumni directory.

The source CSV recorded faculty/department names very inconsistently (64 raw
variants with typos and casing differences). We normalise them into a small,
clean set of canonical fields of study so the "field of study" filter is
usable, while keeping the original text on the record for reference.
"""

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
