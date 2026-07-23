from django import forms

from directory.choices import FIELD_OF_STUDY_CHOICES
from directory.models import Alumnus


class ClaimRecordForm(forms.Form):
    """Let a verified user claim their pre-loaded alumnus record.

    Identity is confirmed by matching batch + field of study + last name plus
    one of (class roll number, date of birth). This is deliberately stricter
    than the reference project, which authenticated on date of birth alone.
    """

    batch = forms.CharField(max_length=8, label="Batch / year", help_text="e.g. 078")
    field_of_study = forms.ChoiceField(choices=FIELD_OF_STUDY_CHOICES, label="Field of study")
    last_name = forms.CharField(max_length=100)
    class_roll_no = forms.CharField(max_length=30, required=False, label="Class roll no.")
    date_of_birth_bs = forms.CharField(
        max_length=15, required=False, label="Date of birth (B.S.)",
        help_text="Provide roll number or date of birth to confirm identity.",
    )

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("class_roll_no") and not cleaned.get("date_of_birth_bs"):
            raise forms.ValidationError(
                "Enter your class roll number or date of birth to confirm your identity."
            )
        return cleaned

    def find_match(self):
        """Return the single unclaimed Alumnus matching the form, or None."""
        data = self.cleaned_data
        qs = Alumnus.objects.filter(
            user_account__isnull=True,
            batch=data["batch"].strip(),
            field_of_study=data["field_of_study"],
            last_name__iexact=data["last_name"].strip(),
        )
        if data.get("class_roll_no"):
            qs = qs.filter(class_roll_no__iexact=data["class_roll_no"].strip())
        if data.get("date_of_birth_bs"):
            qs = qs.filter(date_of_birth_bs=data["date_of_birth_bs"].strip())

        matches = list(qs[:2])
        return matches[0] if len(matches) == 1 else None


class AlumnusProfileForm(forms.ModelForm):
    """Fields an alumnus may edit on their own claimed record."""

    class Meta:
        model = Alumnus
        fields = [
            "gender",
            "current_city",
            "current_country",
            "employment_status",
            "employer_organization",
            "job_title",
            "further_study_institution",
            "further_study_country",
            "email",
            "contact_number",
            "linkedin_url",
            "website",
            "is_public",
        ]
        widgets = {
            "current_city": forms.TextInput(attrs={"class": "input"}),
            "employer_organization": forms.TextInput(attrs={"class": "input"}),
            "job_title": forms.TextInput(attrs={"class": "input"}),
            "further_study_institution": forms.TextInput(attrs={"class": "input"}),
            "email": forms.EmailInput(attrs={"class": "input"}),
            "contact_number": forms.TextInput(attrs={"class": "input"}),
            "linkedin_url": forms.URLInput(attrs={"class": "input"}),
            "website": forms.URLInput(attrs={"class": "input"}),
        }
