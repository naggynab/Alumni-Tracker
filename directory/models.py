from django.conf import settings
from django.db import models
from django.urls import reverse
from django_countries.fields import CountryField

from .choices import (
    FIELD_OF_STUDY_CHOICES,
    GENDER_CHOICES,
    EMPLOYMENT_STATUS_CHOICES,
)


class Alumnus(models.Model):
    """A single alumnus/student record.

    Location and employment fields are stored directly on the record so the
    directory's six filters (name, batch, field of study, current city,
    employer, country) can all be applied with simple, indexed lookups.
    """

    # --- Identity -----------------------------------------------------------
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    date_of_birth_bs = models.CharField(
        "Date of birth (B.S.)", max_length=15, blank=True
    )

    # --- Academic -----------------------------------------------------------
    field_of_study = models.CharField(
        max_length=30,
        choices=FIELD_OF_STUDY_CHOICES,
        blank=True,
        db_index=True,
        help_text="Canonical field of study, normalised from the department name.",
    )
    department_raw = models.CharField(
        max_length=150,
        blank=True,
        help_text="Original department/faculty name as recorded.",
    )
    batch = models.CharField(
        max_length=8,
        blank=True,
        db_index=True,
        help_text="Enrollment batch/year, e.g. '078'.",
    )
    class_roll_no = models.CharField(max_length=30, blank=True, db_index=True)

    # --- Current location (where they live now) -----------------------------
    current_city = models.CharField(max_length=100, blank=True, db_index=True)
    current_country = CountryField(blank=True, db_index=True)

    # --- Permanent / home location ------------------------------------------
    permanent_district = models.CharField(max_length=100, blank=True)
    permanent_country = CountryField(blank=True)

    # --- Employment (where they work) ---------------------------------------
    employment_status = models.CharField(
        max_length=20, choices=EMPLOYMENT_STATUS_CHOICES, blank=True
    )
    employer_organization = models.CharField(
        max_length=150, blank=True, db_index=True,
        help_text="Organization the alumnus currently works at.",
    )
    job_title = models.CharField(max_length=150, blank=True)

    # --- Further education --------------------------------------------------
    further_study_institution = models.CharField(max_length=150, blank=True)
    further_study_degree = models.CharField(max_length=100, blank=True)
    further_study_country = CountryField(blank=True)

    # --- Contact / socials --------------------------------------------------
    email = models.EmailField(blank=True)
    contact_number = models.CharField(max_length=30, blank=True)
    linkedin_url = models.URLField(blank=True)
    website = models.URLField(blank=True)

    # --- Account linkage & housekeeping -------------------------------------
    user_account = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alumnus_profile",
        help_text="The signed-in account that has claimed this record.",
    )
    is_public = models.BooleanField(
        default=True,
        help_text="If off, the record is hidden from the public directory.",
    )
    date_added = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "alumni"
        ordering = ["batch", "last_name", "first_name"]
        indexes = [
            models.Index(fields=["batch", "field_of_study"]),
            models.Index(fields=["last_name", "first_name"]),
        ]

    def __str__(self):
        return self.full_name or f"Alumnus #{self.pk}"

    @property
    def full_name(self):
        return " ".join(
            p for p in [self.first_name, self.middle_name, self.last_name] if p
        )

    @property
    def is_claimed(self):
        return self.user_account_id is not None

    def get_absolute_url(self):
        return reverse("directory:alumnus-detail", args=[self.pk])
