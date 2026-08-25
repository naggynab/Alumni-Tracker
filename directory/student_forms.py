"""Forms for student self-service and community features."""

from datetime import date

from django import forms

from .models import ContactRequest, CorrectionRequest, JobPosting


CORRECTABLE_FIELDS = (
    ("gender", "Gender"),
    ("date_of_birth_bs", "Date of birth"),
    ("contact_number", "Contact number"),
    ("permanent_district", "Permanent district"),
    ("current_city", "Current city"),
    ("current_country", "Current country"),
    ("employment_status", "Employment status"),
    ("employer_organization", "Employer"),
    ("job_title", "Job title"),
    ("further_study_institution", "Further-study institution"),
    ("further_study_degree", "Further-study degree"),
    ("further_study_country", "Further-study country"),
)


class CorrectionRequestForm(forms.ModelForm):
    field_name = forms.ChoiceField(choices=CORRECTABLE_FIELDS, label="Field to correct")

    class Meta:
        model = CorrectionRequest
        fields = ["field_name", "proposed_value", "reason"]
        widgets = {
            "proposed_value": forms.Textarea(attrs={"rows": 2}),
            "reason": forms.Textarea(attrs={"rows": 3}),
        }


class CorrectionReviewForm(forms.ModelForm):
    class Meta:
        model = CorrectionRequest
        fields = ["status", "reviewer_note"]
        widgets = {"reviewer_note": forms.Textarea(attrs={"rows": 3})}


class JobPostingForm(forms.ModelForm):
    class Meta:
        model = JobPosting
        fields = [
            "title",
            "organization",
            "description",
            "location",
            "employment_type",
            "application_url",
            "application_email",
            "deadline",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
            "deadline": forms.DateInput(attrs={"type": "date"}),
        }

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("application_url") and not cleaned.get("application_email"):
            raise forms.ValidationError("Add an application link or application email.")
        deadline = cleaned.get("deadline")
        if deadline and deadline < date.today():
            self.add_error("deadline", "The deadline cannot be in the past.")
        return cleaned


class ContactRequestForm(forms.Form):
    recipient_roll_number = forms.CharField(
        max_length=30,
        label="Alumni roll number",
        help_text="Use the complete roll number when available, such as 080BCT047.",
    )
    message = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4}),
        help_text="Your email and phone number remain hidden unless the recipient accepts.",
    )


class DecisionForm(forms.Form):
    status = forms.ChoiceField(choices=(("accepted", "Accept"), ("declined", "Decline")))
    response_note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


class ModerationForm(forms.Form):
    status = forms.ChoiceField()

    def __init__(self, choices, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["status"].choices = choices
