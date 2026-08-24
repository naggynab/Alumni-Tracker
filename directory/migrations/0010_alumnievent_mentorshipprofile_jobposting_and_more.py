from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("directory", "0009_refresh_roll_scope_prefixes"),
    ]

    operations = [
        migrations.CreateModel(
            name="AlumniEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=180)),
                ("description", models.TextField()),
                ("starts_at", models.DateTimeField(db_index=True)),
                ("ends_at", models.DateTimeField(blank=True, null=True)),
                ("location", models.CharField(blank=True, max_length=180)),
                ("virtual_url", models.URLField(blank=True)),
                ("max_attendees", models.PositiveIntegerField(blank=True, null=True)),
                ("status", models.CharField(choices=[("pending", "Pending review"), ("published", "Published"), ("cancelled", "Cancelled"), ("rejected", "Rejected")], db_index=True, default="pending", max_length=20)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("organizer", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="organized_alumni_events", to=settings.AUTH_USER_MODEL)),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reviewed_alumni_events", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["starts_at", "-created_at"]},
        ),
        migrations.CreateModel(
            name="MentorshipProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("headline", models.CharField(blank=True, max_length=150)),
                ("bio", models.TextField(blank=True)),
                ("expertise", models.CharField(blank=True, max_length=500)),
                ("max_mentees", models.PositiveIntegerField(default=3)),
                ("is_available", models.BooleanField(db_index=True, default=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("alumnus", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="mentorship_profile", to="directory.alumnus")),
            ],
            options={"ordering": ["-is_available", "alumnus__last_name", "alumnus__first_name"]},
        ),
        migrations.CreateModel(
            name="JobPosting",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=180)),
                ("organization", models.CharField(max_length=180)),
                ("description", models.TextField()),
                ("location", models.CharField(blank=True, max_length=150)),
                ("employment_type", models.CharField(choices=[("internship", "Internship"), ("full_time", "Full-time"), ("part_time", "Part-time"), ("contract", "Contract"), ("volunteer", "Volunteer")], max_length=20)),
                ("application_url", models.URLField(blank=True)),
                ("application_email", models.EmailField(blank=True, max_length=254)),
                ("deadline", models.DateField(blank=True, db_index=True, null=True)),
                ("status", models.CharField(choices=[("pending", "Pending review"), ("published", "Published"), ("closed", "Closed"), ("rejected", "Rejected")], db_index=True, default="pending", max_length=20)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("posted_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="job_postings", to=settings.AUTH_USER_MODEL)),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reviewed_job_postings", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["status", "deadline", "-created_at"]},
        ),
        migrations.CreateModel(
            name="EventRegistration",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("registered", "Registered"), ("cancelled", "Cancelled")], db_index=True, default="registered", max_length=15)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("attendee", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="event_registrations", to=settings.AUTH_USER_MODEL)),
                ("event", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="registrations", to="directory.alumnievent")),
            ],
        ),
        migrations.CreateModel(
            name="CorrectionRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("field_name", models.CharField(max_length=50)),
                ("current_value", models.TextField(blank=True)),
                ("proposed_value", models.TextField()),
                ("reason", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("in_review", "In review"), ("approved", "Approved"), ("rejected", "Rejected")], db_index=True, default="pending", max_length=20)),
                ("reviewer_note", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("alumnus", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="correction_requests", to="directory.alumnus")),
                ("requester", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="submitted_correction_requests", to=settings.AUTH_USER_MODEL)),
                ("reviewer", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reviewed_correction_requests", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["status", "-created_at"]},
        ),
        migrations.CreateModel(
            name="ContactRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("message", models.TextField()),
                ("status", models.CharField(choices=[("pending", "Pending"), ("accepted", "Accepted"), ("declined", "Declined"), ("closed", "Closed")], db_index=True, default="pending", max_length=20)),
                ("response_note", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("responded_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("recipient", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="contact_requests_received", to=settings.AUTH_USER_MODEL)),
                ("sender", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="contact_requests_sent", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["status", "-created_at"]},
        ),
        migrations.CreateModel(
            name="MentorshipRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("message", models.TextField()),
                ("status", models.CharField(choices=[("pending", "Pending"), ("accepted", "Accepted"), ("declined", "Declined"), ("closed", "Closed")], db_index=True, default="pending", max_length=20)),
                ("response_note", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("responded_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("mentee", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="mentorship_requests_sent", to="directory.alumnus")),
                ("mentor", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="mentorship_requests_received", to="directory.alumnus")),
            ],
            options={"ordering": ["status", "-created_at"], "indexes": [
                models.Index(fields=["mentor", "status"], name="directory_m_mentor__49f76e_idx"),
                models.Index(fields=["mentee", "status"], name="directory_m_mentee__af8e92_idx"),
            ]},
        ),
        migrations.AddConstraint(
            model_name="eventregistration",
            constraint=models.UniqueConstraint(fields=("event", "attendee"), name="unique_event_attendee"),
        ),
        migrations.AddIndex(
            model_name="correctionrequest",
            index=models.Index(fields=["status", "-created_at"], name="directory_c_status_f4cc0c_idx"),
        ),
        migrations.AddIndex(
            model_name="correctionrequest",
            index=models.Index(fields=["alumnus", "-created_at"], name="directory_c_alumnus_a2fc48_idx"),
        ),
        migrations.AddIndex(
            model_name="contactrequest",
            index=models.Index(fields=["sender", "status"], name="directory_c_sender__8b96fe_idx"),
        ),
        migrations.AddIndex(
            model_name="contactrequest",
            index=models.Index(fields=["recipient", "status"], name="directory_c_recipie_030880_idx"),
        ),
    ]
