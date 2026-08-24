from django.conf import settings
from django.db import models
from django.urls import reverse
from django_countries.fields import CountryField

from .choices import (
    FIELD_OF_STUDY_CHOICES,
    GENDER_CHOICES,
    EMPLOYMENT_STATUS_CHOICES,
    normalize_city,
    normalize_employer,
    normalize_institution,
    normalize_roll_serial,
    normalize_roll_scope,
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
    roll_number_canonical = models.CharField(max_length=30, blank=True, db_index=True)
    roll_scope_canonical = models.CharField(max_length=150, blank=True, db_index=True)

    # --- Current location (where they live now) -----------------------------
    current_city = models.CharField(max_length=100, blank=True, db_index=True)
    current_city_canonical = models.CharField(max_length=100, blank=True, db_index=True)
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
    employer_canonical = models.CharField(max_length=150, blank=True, db_index=True)
    job_title = models.CharField(max_length=150, blank=True)

    # --- Further education --------------------------------------------------
    further_study_institution = models.CharField(max_length=150, blank=True)
    further_study_institution_canonical = models.CharField(
        max_length=150, blank=True, db_index=True
    )
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
        default=False,
        help_text="If on, the record appears in the public directory.",
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

    def save(self, *args, **kwargs):
        """Keep searchable canonical keys synchronized with raw text fields."""
        self.current_city_canonical = normalize_city(self.current_city)
        self.employer_canonical = normalize_employer(self.employer_organization)
        self.further_study_institution_canonical = normalize_institution(
            self.further_study_institution
        )
        self.roll_number_canonical = normalize_roll_serial(self.class_roll_no)
        self.roll_scope_canonical = normalize_roll_scope(
            self.class_roll_no, self.field_of_study, self.department_raw
        )

        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            update_fields = set(update_fields)
            if "current_city" in update_fields:
                update_fields.add("current_city_canonical")
            if "employer_organization" in update_fields:
                update_fields.add("employer_canonical")
            if "further_study_institution" in update_fields:
                update_fields.add("further_study_institution_canonical")
            if "class_roll_no" in update_fields:
                update_fields.add("roll_number_canonical")
                update_fields.add("roll_scope_canonical")
            if "field_of_study" in update_fields or "department_raw" in update_fields:
                update_fields.add("roll_scope_canonical")
            kwargs["update_fields"] = update_fields

        return super().save(*args, **kwargs)

    @property
    def is_claimed(self):
        return self.user_account_id is not None

    def get_absolute_url(self):
        return reverse("directory:alumnus-detail", args=[self.pk])


class FollowUp(models.Model):
    """A small officer-owned work item for records needing attention."""

    STATUS_CHOICES = (
        ("open", "Open"),
        ("in_progress", "In progress"),
        ("closed", "Closed"),
    )

    alumnus = models.OneToOneField(
        Alumnus,
        on_delete=models.CASCADE,
        related_name="follow_up",
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="open", db_index=True
    )
    reason = models.CharField(max_length=80, blank=True)
    note = models.TextField(blank=True)
    next_contact_at = models.DateField(null=True, blank=True, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_alumni_follow_ups",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_alumni_follow_ups",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["status", "next_contact_at", "-updated_at"]

    def __str__(self):
        return f"Follow-up for {self.alumnus}"


class ClaimReview(models.Model):
    """An auditable review record for an alumnus account claim."""

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    )

    alumnus = models.ForeignKey(
        Alumnus,
        on_delete=models.CASCADE,
        related_name="claim_reviews",
    )
    claimant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submitted_claim_reviews",
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_claim_reviews",
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True
    )
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["status", "-created_at"]
        indexes = [
            models.Index(fields=["alumnus", "-created_at"]),
            models.Index(fields=["status", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.get_status_display()} claim for {self.alumnus}"


class CorrectionRequest(models.Model):
    """A student-requested change awaiting staff review."""

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("in_review", "In review"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    )

    alumnus = models.ForeignKey(
        Alumnus, on_delete=models.CASCADE, related_name="correction_requests"
    )
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="submitted_correction_requests",
    )
    field_name = models.CharField(max_length=50)
    current_value = models.TextField(blank=True)
    proposed_value = models.TextField()
    reason = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_correction_requests",
    )
    reviewer_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["status", "-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["alumnus", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.get_status_display()} correction for {self.alumnus}"


class MentorshipProfile(models.Model):
    """Opt-in public profile for an alumnus willing to mentor students."""

    alumnus = models.OneToOneField(
        Alumnus, on_delete=models.CASCADE, related_name="mentorship_profile"
    )
    headline = models.CharField(max_length=150, blank=True)
    bio = models.TextField(blank=True)
    expertise = models.CharField(max_length=500, blank=True)
    max_mentees = models.PositiveIntegerField(default=3)
    is_available = models.BooleanField(default=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_available", "alumnus__last_name", "alumnus__first_name"]

    def __str__(self):
        return f"Mentorship profile for {self.alumnus}"


class MentorshipRequest(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("declined", "Declined"),
        ("closed", "Closed"),
    )

    mentor = models.ForeignKey(
        Alumnus, on_delete=models.CASCADE, related_name="mentorship_requests_received"
    )
    mentee = models.ForeignKey(
        Alumnus, on_delete=models.CASCADE, related_name="mentorship_requests_sent"
    )
    message = models.TextField()
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True
    )
    response_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["status", "-created_at"]
        indexes = [
            models.Index(fields=["mentor", "status"]),
            models.Index(fields=["mentee", "status"]),
        ]

    def __str__(self):
        return f"Mentorship request from {self.mentee} to {self.mentor}"


class JobPosting(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending review"),
        ("published", "Published"),
        ("closed", "Closed"),
        ("rejected", "Rejected"),
    )
    EMPLOYMENT_TYPE_CHOICES = (
        ("internship", "Internship"),
        ("full_time", "Full-time"),
        ("part_time", "Part-time"),
        ("contract", "Contract"),
        ("volunteer", "Volunteer"),
    )

    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="job_postings",
    )
    title = models.CharField(max_length=180)
    organization = models.CharField(max_length=180)
    description = models.TextField()
    location = models.CharField(max_length=150, blank=True)
    employment_type = models.CharField(max_length=20, choices=EMPLOYMENT_TYPE_CHOICES)
    application_url = models.URLField(blank=True)
    application_email = models.EmailField(blank=True)
    deadline = models.DateField(null=True, blank=True, db_index=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_job_postings",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["status", "deadline", "-created_at"]

    def __str__(self):
        return f"{self.title} at {self.organization}"


class AlumniEvent(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending review"),
        ("published", "Published"),
        ("cancelled", "Cancelled"),
        ("rejected", "Rejected"),
    )

    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="organized_alumni_events",
    )
    title = models.CharField(max_length=180)
    description = models.TextField()
    starts_at = models.DateTimeField(db_index=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    location = models.CharField(max_length=180, blank=True)
    virtual_url = models.URLField(blank=True)
    max_attendees = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_alumni_events",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["starts_at", "-created_at"]

    def __str__(self):
        return self.title


class EventRegistration(models.Model):
    STATUS_CHOICES = (("registered", "Registered"), ("cancelled", "Cancelled"))

    event = models.ForeignKey(
        AlumniEvent, on_delete=models.CASCADE, related_name="registrations"
    )
    attendee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="event_registrations",
    )
    status = models.CharField(
        max_length=15, choices=STATUS_CHOICES, default="registered", db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["event", "attendee"], name="unique_event_attendee"
            )
        ]

    def __str__(self):
        return f"{self.attendee} at {self.event}"


class ContactRequest(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("declined", "Declined"),
        ("closed", "Closed"),
    )

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="contact_requests_sent",
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="contact_requests_received",
    )
    message = models.TextField()
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True
    )
    response_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["status", "-created_at"]
        indexes = [
            models.Index(fields=["sender", "status"]),
            models.Index(fields=["recipient", "status"]),
        ]

    def __str__(self):
        return f"Contact request from {self.sender} to {self.recipient}"


class Notification(models.Model):
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    kind = models.CharField(max_length=40)
    title = models.CharField(max_length=180)
    message = models.TextField()
    url = models.CharField(max_length=300, blank=True)
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["is_read", "-created_at"]

    def __str__(self):
        return f"Notification for {self.recipient}: {self.title}"


class SavedSearch(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_searches"
    )
    name = models.CharField(max_length=100)
    query_params = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-last_used_at", "-created_at"]

    def __str__(self):
        return f"{self.name} ({self.user})"


class AlumniFavorite(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="alumni_favorites"
    )
    alumnus = models.ForeignKey(
        Alumnus, on_delete=models.CASCADE, related_name="favorited_by"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "alumnus"], name="unique_alumni_favorite")
        ]


class CommunityGroup(models.Model):
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=170, unique=True)
    description = models.TextField(blank=True)
    batch = models.CharField(max_length=8, blank=True)
    program = models.CharField(max_length=30, blank=True)
    is_public = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_community_groups",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class GroupMembership(models.Model):
    ROLE_CHOICES = (("member", "Member"), ("moderator", "Moderator"))

    group = models.ForeignKey(
        CommunityGroup, on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="group_memberships"
    )
    role = models.CharField(max_length=15, choices=ROLE_CHOICES, default="member")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["group", "user"], name="unique_group_member")
        ]


class GroupPost(models.Model):
    group = models.ForeignKey(
        CommunityGroup, on_delete=models.CASCADE, related_name="posts"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="community_posts"
    )
    body = models.TextField()
    is_hidden = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]


class AlumniStory(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending review"),
        ("published", "Published"),
        ("rejected", "Rejected"),
    )

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="alumni_stories"
    )
    title = models.CharField(max_length=180)
    body = models.TextField()
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_alumni_stories",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]


class Skill(models.Model):
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class AlumniSkill(models.Model):
    LEVEL_CHOICES = (("basic", "Basic"), ("working", "Working knowledge"), ("advanced", "Advanced"))

    alumnus = models.ForeignKey(Alumnus, on_delete=models.CASCADE, related_name="skills")
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name="alumni_skills")
    level = models.CharField(max_length=15, choices=LEVEL_CHOICES, default="working")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["alumnus", "skill"], name="unique_alumni_skill")
        ]


class SkillEndorsement(models.Model):
    alumni_skill = models.ForeignKey(
        AlumniSkill, on_delete=models.CASCADE, related_name="endorsements"
    )
    endorser = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="skill_endorsements"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["alumni_skill", "endorser"], name="unique_skill_endorsement"
            )
        ]


class Survey(models.Model):
    STATUS_CHOICES = (("draft", "Draft"), ("published", "Published"), ("closed", "Closed"))

    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    questions = models.JSONField(default=list)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="draft", db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="created_surveys"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    closes_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class SurveyResponse(models.Model):
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name="responses")
    respondent = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="survey_responses"
    )
    answers = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["survey", "respondent"], name="unique_survey_response")
        ]


class Resource(models.Model):
    STATUS_CHOICES = (("pending", "Pending review"), ("published", "Published"), ("rejected", "Rejected"))

    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=80)
    url = models.URLField()
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="submitted_resources"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviewed_resources"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["category", "title"]


class ActivityLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="activity_logs"
    )
    action = models.CharField(max_length=100)
    path = models.CharField(max_length=300, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]


class ApiToken(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="api_tokens"
    )
    name = models.CharField(max_length=100)
    token_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class TwoFactorSetting(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="two_factor_setting"
    )
    enabled = models.BooleanField(default=False)
    method = models.CharField(max_length=20, default="email")
    updated_at = models.DateTimeField(auto_now=True)


class TwoFactorCode(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="two_factor_codes"
    )
    code_hash = models.CharField(max_length=64)
    purpose = models.CharField(max_length=30, default="sensitive_action")
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class DataConflict(models.Model):
    STATUS_CHOICES = (("open", "Open"), ("resolved", "Resolved"), ("ignored", "Ignored"))

    record_a = models.ForeignKey(
        Alumnus, on_delete=models.SET_NULL, null=True, related_name="conflicts_as_a"
    )
    record_b = models.ForeignKey(
        Alumnus, on_delete=models.SET_NULL, null=True, related_name="conflicts_as_b"
    )
    field_name = models.CharField(max_length=80)
    value_a = models.TextField(blank=True)
    value_b = models.TextField(blank=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="open", db_index=True)
    resolution_note = models.TextField(blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="resolved_data_conflicts"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["status", "-created_at"]
