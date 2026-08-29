from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .choices import (
    FIELD_COMPUTER,
    FIELD_ELECTRICAL,
    normalize_employer,
    normalize_field_of_study,
    normalize_gender,
    normalize_institution,
    normalize_roll_scope,
    normalize_roll_serial,
)
from .filters import AlumnusFilter
from .models import (
    AlumniEvent,
    Alumnus,
    ClaimReview,
    ContactRequest,
    CorrectionRequest,
    EventRegistration,
    FollowUp,
    JobPosting,
    MentorshipProfile,
    MentorshipRequest,
    Notification,
    ServiceRequestReply,
    Survey,
    SurveyResponse,
)
from .permissions import is_department_data_editor, is_department_staff
from .profile import profile_completeness
from .stats import build_comparison, build_data_quality, build_report
from .student_forms import AlumniEventForm, ContactRequestForm, JobPostingForm


User = get_user_model()


class NormalisationTests(TestCase):
    def test_field_normalisation(self):
        self.assertEqual(normalize_field_of_study("COMPUTER ENGINEERING"), FIELD_COMPUTER)
        self.assertEqual(normalize_field_of_study("Electronics and Computer Engineering"), FIELD_COMPUTER)
        self.assertEqual(normalize_field_of_study("ELECTRICAL EGNINEERING"), FIELD_ELECTRICAL)
        self.assertEqual(normalize_field_of_study(""), "other")

    def test_gender_normalisation(self):
        self.assertEqual(normalize_gender("1"), "Male")
        self.assertEqual(normalize_gender("2"), "Female")
        self.assertEqual(normalize_gender("Female"), "Female")
        self.assertEqual(normalize_gender(""), "")

    def test_institution_duplicate_spellings_share_a_key(self):
        self.assertEqual(
            normalize_institution("IIT KHARAGPUR"),
            normalize_institution("IIT Kharagpur"),
        )
        self.assertEqual(
            normalize_institution("Institute of Engineering, Pulchowk"),
            normalize_institution("Pulchowk Campus, IOE"),
        )
        self.assertEqual(
            normalize_institution("IOE pulchowk"),
            "institute of engineering",
        )

    def test_employer_abbreviations_share_a_key(self):
        self.assertEqual(normalize_employer("AIT"), normalize_employer("Asian Institute of Technology"))
        self.assertEqual(normalize_employer("Univ. of Kathmandu"), normalize_employer("University of Kathmandu"))

    def test_roll_identity_keeps_scope_separate_from_serial(self):
        self.assertEqual(normalize_roll_serial("080BCT047"), "47")
        self.assertEqual(normalize_roll_serial("047"), "47")
        self.assertEqual(normalize_roll_scope("080BCT047"), "BCT")
        self.assertEqual(normalize_roll_scope("047", "computer"), "computer")


class BatchNormalisationTests(TestCase):
    def test_batch_normalisation(self):
        from directory.management.commands.import_alumni import normalize_batch
        # DOECE dump stores '2075'; roster stores '075' — both must land on '075'.
        self.assertEqual(normalize_batch("2075"), "075")
        self.assertEqual(normalize_batch(" 2078 "), "078")
        self.assertEqual(normalize_batch("078"), "078")
        self.assertEqual(normalize_batch(""), "")
        self.assertEqual(normalize_batch(None), "")


class FilterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Alumnus.objects.create(
            first_name="Aashish", last_name="Karki", batch="078",
            field_of_study=FIELD_COMPUTER, current_city="Kathmandu",
            current_country="NP", employer_organization="Nepal Telecom",
            is_public=True,
        )
        Alumnus.objects.create(
            first_name="Bindu", last_name="Paudel", batch="078",
            field_of_study=FIELD_ELECTRICAL, current_city="Lalitpur",
            current_country="US", employer_organization="LogPoint",
            is_public=True,
        )
        Alumnus.objects.create(
            first_name="Canon", last_name="One", batch="078",
            field_of_study=FIELD_COMPUTER,
            further_study_institution="Institute of Engineering, Pulchowk",
            is_public=True,
        )
        Alumnus.objects.create(
            first_name="Canon", last_name="Two", batch="078",
            field_of_study=FIELD_COMPUTER,
            further_study_institution="Pulchowk Campus, IOE",
            is_public=True,
        )

    def _count(self, params):
        return AlumnusFilter(params, queryset=Alumnus.objects.all()).qs.count()

    def test_name_filter(self):
        self.assertEqual(self._count({"name": "karki"}), 1)
        self.assertEqual(self._count({"name": "aashish karki"}), 1)

    def test_batch_and_field(self):
        self.assertEqual(self._count({"batch": "078"}), 4)
        self.assertEqual(self._count({"field_of_study": FIELD_ELECTRICAL}), 1)

    def test_city_employer_country(self):
        # City/country/university are dropdowns populated from the data, so
        # they match the exact stored value; employer stays free-text (icontains).
        self.assertEqual(self._count({"country": "NP", "current_city": "Kathmandu"}), 1)
        self.assertEqual(self._count({"employer": "telecom"}), 1)
        self.assertEqual(self._count({"country": "US"}), 1)

    def test_combined(self):
        self.assertEqual(self._count({"batch": "078", "field_of_study": FIELD_COMPUTER}), 3)

    def test_university_filter_matches_canonical_duplicate_spellings(self):
        self.assertEqual(
            self._count({"university": normalize_institution("IOE pulchowk")}),
            2,
        )

    def test_city_choices_remain_usable_without_country(self):
        alumni_filter = AlumnusFilter({}, queryset=Alumnus.objects.all())
        city_field = alumni_filter.form.fields["current_city"]

        city_values = [value for value, _label in city_field.choices if value]
        self.assertEqual(city_values, ["Kathmandu", "Lalitpur"])
        self.assertNotIn("disabled", city_field.widget.attrs)

    def test_city_choices_are_scoped_by_country(self):
        alumni_filter = AlumnusFilter({"country": "NP"}, queryset=Alumnus.objects.all())
        city_field = alumni_filter.form.fields["current_city"]
        city_values = [value for value, _label in city_field.choices if value]

        self.assertEqual(city_values, ["Kathmandu"])
        self.assertNotIn("disabled", city_field.widget.attrs)


class ViewTests(TestCase):
    def test_home_and_list_render(self):
        self.assertEqual(self.client.get(reverse("directory:home")).status_code, 200)
        self.assertEqual(self.client.get(reverse("directory:alumni-list")).status_code, 200)

    def test_private_record_hidden(self):
        a = Alumnus.objects.create(first_name="Hidden", last_name="Person", is_public=False)
        self.assertEqual(self.client.get(a.get_absolute_url()).status_code, 404)


@override_settings(DEPARTMENT_EMAILS=[], DEPARTMENT_EMAIL_DOMAINS=[])
class DepartmentAccessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="officer-test", email="officer@example.com", password="ValidPass1!"
        )

    def test_anonymous_is_denied(self):
        self.assertFalse(is_department_staff(AnonymousUser()))

    def test_ordinary_user_is_denied_without_explicit_grant(self):
        self.assertFalse(is_department_staff(self.user))

    def test_superuser_is_allowed(self):
        self.user.is_superuser = True
        self.assertTrue(is_department_staff(self.user))

    def test_allowlisted_email_is_allowed(self):
        with self.settings(DEPARTMENT_EMAILS=["officer@example.com"]):
            self.assertTrue(is_department_staff(self.user))

    def test_group_member_is_allowed(self):
        group = Group.objects.create(name="Department Staff")
        group.user_set.add(self.user)
        self.assertTrue(is_department_staff(self.user))

    def test_department_staff_profile_hides_academic_sections(self):
        group = Group.objects.create(name="Department Staff")
        group.user_set.add(self.user)
        Alumnus.objects.create(
            first_name="Department",
            last_name="Officer",
            batch="080",
            field_of_study=FIELD_COMPUTER,
            class_roll_no="999BCT001",
            user_account=self.user,
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("directory:my-profile"))

        self.assertContains(response, "Personal Information")
        self.assertContains(response, "Contact Information")
        self.assertContains(response, "Professional Information")
        self.assertNotContains(response, "Academic Information")
        self.assertNotContains(response, "Graduation Year")
        self.assertNotContains(response, "Higher Studies Information")

    def test_department_staff_student_services_shows_authority_workspace(self):
        staff_group = Group.objects.create(name="Department Staff")
        editor_group = Group.objects.create(name="Alumni Data Editors")
        staff_group.user_set.add(self.user)
        editor_group.user_set.add(self.user)
        Alumnus.objects.create(
            first_name="Department",
            last_name="Officer",
            batch="080",
            field_of_study=FIELD_COMPUTER,
            user_account=self.user,
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("directory:student-services"))

        self.assertContains(response, "Department authority workspace")
        self.assertContains(response, "Student request desk")
        self.assertContains(response, "Student recommendations &amp; feedback")

    def test_configured_domain_is_allowed(self):
        with self.settings(DEPARTMENT_EMAIL_DOMAINS=["example.com"]):
            self.assertTrue(is_department_staff(self.user))

    def test_unconfigured_domain_is_denied(self):
        self.user.email = "officer@ioe.edu.np"
        self.user.save(update_fields=["email"])
        self.assertFalse(is_department_staff(self.user))

    def test_updated_profiles_tool_lists_recently_updated_profiles(self):
        department_group = Group.objects.create(name="Department Staff")
        department_group.user_set.add(self.user)
        older = Alumnus.objects.create(
            first_name="Older", last_name="Profile", date_modified=timezone.now()
        )
        recent = Alumnus.objects.create(
            first_name="Recent", last_name="Profile", date_modified=timezone.now()
        )
        from datetime import timedelta

        Alumnus.objects.filter(pk=older.pk).update(
            date_modified=timezone.now() - timedelta(days=31)
        )
        Alumnus.objects.filter(pk=recent.pk).update(
            date_modified=timezone.now() - timedelta(days=1)
        )
        self.client.force_login(self.user)

        report = self.client.get(reverse("directory:department-report"))
        self.assertContains(report, "Last updated profiles (1)")

        response = self.client.get(reverse("directory:department-updated-profiles"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "1 profile updated")
        self.assertContains(response, "Recent Profile")
        self.assertNotContains(response, "Older Profile")


@override_settings(DEPARTMENT_EMAILS=[], DEPARTMENT_EMAIL_DOMAINS=[])
class StudentServiceReplyTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            username="student-requester",
            email="student@example.com",
            password="ValidPass1!",
        )
        self.alumnus = Alumnus.objects.create(
            first_name="Student",
            last_name="Requester",
            batch="080",
            field_of_study=FIELD_COMPUTER,
            current_city="Lalitpur",
            user_account=self.student,
        )
        self.editor = User.objects.create_user(
            username="department-editor",
            email="editor@example.com",
            password="ValidPass1!",
        )
        editor_group = Group.objects.create(name="Alumni Data Editors")
        editor_group.user_set.add(self.editor)
        self.staff = User.objects.create_user(
            username="department-reader",
            email="reader@example.com",
            password="ValidPass1!",
        )
        staff_group = Group.objects.create(name="Department Staff")
        staff_group.user_set.add(self.staff)
        self.correction = CorrectionRequest.objects.create(
            alumnus=self.alumnus,
            requester=self.student,
            field_name="current_city",
            current_value="Lalitpur",
            proposed_value="Kathmandu",
            reason="I moved recently.",
        )

    def test_editor_can_approve_and_reply_to_correction(self):
        self.client.force_login(self.editor)

        response = self.client.post(
            reverse("directory:student-requests"),
            {
                "kind": "correction",
                "object_id": self.correction.pk,
                "status": "approved",
                "message": "Your city correction was approved.",
            },
        )

        self.assertRedirects(response, reverse("directory:student-requests"))
        self.correction.refresh_from_db()
        self.alumnus.refresh_from_db()
        self.assertEqual(self.correction.status, "approved")
        self.assertEqual(self.alumnus.current_city, "Kathmandu")
        self.assertEqual(
            ServiceRequestReply.objects.get(object_id=self.correction.pk).message,
            "Your city correction was approved.",
        )
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.student,
                kind="service_request",
                message="Your city correction was approved.",
            ).exists()
        )

        self.client.force_login(self.student)
        response = self.client.get(reverse("directory:correction-requests"))
        self.assertContains(response, "Your city correction was approved.")

    def test_department_reader_cannot_reply(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse("directory:student-requests"))

        self.assertEqual(response.status_code, 403)
        self.assertFalse(ServiceRequestReply.objects.exists())

    def test_private_peer_requests_are_not_in_department_queue(self):
        recipient = User.objects.create_user(
            username="private-recipient",
            email="recipient@example.com",
            password="ValidPass1!",
        )
        ContactRequest.objects.create(
            sender=self.student,
            recipient=recipient,
            message="PRIVATE_CONTACT_REQUEST_SHOULD_NOT_APPEAR",
        )
        self.client.force_login(self.editor)

        response = self.client.get(reverse("directory:student-requests"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "PRIVATE_CONTACT_REQUEST_SHOULD_NOT_APPEAR")

    def test_department_editor_can_review_student_feedback_without_identity(self):
        survey = Survey.objects.create(
            title="Student recommendations",
            description="Tell the department what to improve.",
            status="published",
            questions=[{"key": "recommendation", "label": "Recommendation"}],
            created_by=self.editor,
        )
        SurveyResponse.objects.create(
            survey=survey,
            respondent=self.student,
            answers={"recommendation": "Please add more career workshops."},
        )
        self.client.force_login(self.editor)

        response = self.client.get(reverse("directory:department-feedback"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Student recommendations")
        self.assertContains(response, "Please add more career workshops.")
        self.assertNotContains(response, "student@example.com")


class ReportAggregationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Alumnus.objects.create(
            first_name="Nepal", last_name="Alumnus", batch="078",
            field_of_study=FIELD_COMPUTER, current_country="NP",
            current_city="Kathmandu", employer_organization="IIT KHARAGPUR",
        )
        Alumnus.objects.create(
            first_name="Abroad", last_name="Alumnus", batch="078",
            field_of_study=FIELD_COMPUTER, current_country="US",
            current_city="Boston", further_study_institution="IIT Kharagpur",
        )

    def test_report_counts_location_and_program_split(self):
        report = build_report(Alumnus.objects.all())
        self.assertEqual(report["total"], 2)
        self.assertEqual(report["in_nepal"], 1)
        self.assertEqual(report["abroad"], 1)
        self.assertEqual(report["by_field"][0]["in_nepal"], 1)
        self.assertEqual(report["by_field"][0]["abroad"], 1)

    def test_report_uses_canonical_study_institution(self):
        report = build_report(Alumnus.objects.all())
        self.assertEqual(report["by_study_institution"][0]["value"], "indian institute of technology kharagpur")

    def test_comparison_returns_change_values(self):
        comparison = build_comparison(
            Alumnus.objects.filter(batch="078"),
            Alumnus.objects.filter(batch="079"),
        )
        self.assertEqual(comparison["rows"][0]["a"], 2)
        self.assertEqual(comparison["rows"][0]["b"], 0)
        self.assertEqual(comparison["rows"][0]["change"], -2)

    def test_quality_detects_missing_data_duplicates_and_followups(self):
        first = Alumnus.objects.create(first_name="Same", last_name="Name")
        Alumnus.objects.create(first_name="Same", last_name="Name")
        FollowUp.objects.create(alumnus=first, reason="Check identity")
        quality = build_data_quality(Alumnus.objects.all())
        self.assertEqual(quality["duplicate_names"][0]["total"], 2)
        self.assertEqual(quality["open_followups"], 1)

    def test_quality_scopes_roll_duplicates_by_batch_and_program(self):
        Alumnus.objects.create(
            first_name="One", last_name="Student", batch="078",
            field_of_study=FIELD_COMPUTER, class_roll_no="078BCT047",
        )
        Alumnus.objects.create(
            first_name="Another", last_name="Batch", batch="079",
            field_of_study=FIELD_COMPUTER, class_roll_no="047",
        )
        Alumnus.objects.create(
            first_name="Same", last_name="Cohort", batch="078",
            field_of_study=FIELD_COMPUTER, class_roll_no="078BCT047",
        )
        quality = build_data_quality(Alumnus.objects.all())
        self.assertEqual(len(quality["duplicate_rolls"]), 1)
        self.assertEqual(quality["duplicate_rolls"][0]["batch"], "078")
        self.assertEqual(quality["duplicate_rolls"][0]["roll_number"], "47")


class WorkflowLogicTests(TestCase):
    def test_profile_completeness_lists_missing_fields(self):
        alumnus = Alumnus.objects.create(first_name="Profile", last_name="Test")
        result = profile_completeness(alumnus)
        self.assertEqual(result["filled"], 0)
        self.assertEqual(result["percent"], 0)
        self.assertIn("current_country", {item["field"] for item in result["missing"]})

    def test_claim_review_history_is_persistent(self):
        alumnus = Alumnus.objects.create(first_name="Claim", last_name="Test")
        review = ClaimReview.objects.create(alumnus=alumnus, status="pending")
        self.assertEqual(alumnus.claim_reviews.get().pk, review.pk)

    def test_editor_role_is_narrower_than_report_role(self):
        user = User.objects.create_user(
            username="workflow-editor", email="workflow@example.com", password="ValidPass1!"
        )
        report_group = Group.objects.create(name="Department Staff")
        report_group.user_set.add(user)
        self.assertTrue(is_department_staff(user))
        self.assertFalse(is_department_data_editor(user))
        editor_group = Group.objects.create(name="Alumni Data Editors")
        editor_group.user_set.add(user)
        self.assertTrue(is_department_data_editor(user))


class StudentFeatureLogicTests(TestCase):
    def setUp(self):
        self.mentor_user = User.objects.create_user(
            username="mentor-student", email="mentor@example.com", password="ValidPass1!"
        )
        self.mentee_user = User.objects.create_user(
            username="mentee-student", email="mentee@example.com", password="ValidPass1!"
        )
        self.mentor = Alumnus.objects.create(
            first_name="Experienced", last_name="Alumnus", batch="070",
            field_of_study=FIELD_COMPUTER, class_roll_no="070BCT001",
            user_account=self.mentor_user, is_public=True,
        )
        self.mentee = Alumnus.objects.create(
            first_name="Current", last_name="Student", batch="080",
            field_of_study=FIELD_COMPUTER, class_roll_no="080BCT002",
            user_account=self.mentee_user, is_public=True,
        )

    def test_job_requires_a_reliable_application_route(self):
        form = JobPostingForm(
            data={
                "title": "Intern",
                "organization": "DOECE Labs",
                "description": "Work with the team.",
                "location": "Kathmandu",
                "employment_type": "internship",
                "application_url": "",
                "application_email": "",
                "deadline": "",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertTrue(form.non_field_errors())

    def test_mentorship_request_links_mentee_and_mentor(self):
        profile = MentorshipProfile.objects.create(
            alumnus=self.mentor, expertise="Career planning", max_mentees=2
        )
        request_record = MentorshipRequest.objects.create(
            mentor=self.mentor, mentee=self.mentee, message="I would appreciate guidance."
        )
        self.assertTrue(profile.is_available)
        self.assertEqual(request_record.mentor, self.mentor)
        self.assertEqual(request_record.mentee, self.mentee)

    def test_event_registration_is_unique_per_attendee(self):
        from django.utils import timezone
        from datetime import timedelta

        event = AlumniEvent.objects.create(
            organizer=self.mentor_user,
            title="Batch reunion",
            description="Meet the batch.",
            starts_at=timezone.now() + timedelta(days=2),
            status="published",
        )
        EventRegistration.objects.create(event=event, attendee=self.mentee_user)
        with self.assertRaises(Exception):
            EventRegistration.objects.create(event=event, attendee=self.mentee_user)

    def test_contact_request_does_not_share_details_before_acceptance(self):
        contact = ContactRequest.objects.create(
            sender=self.mentee_user,
            recipient=self.mentor_user,
            message="Could I ask about your career path?",
        )
        self.assertEqual(contact.status, "pending")
        self.assertEqual(contact.recipient, self.mentor_user)
