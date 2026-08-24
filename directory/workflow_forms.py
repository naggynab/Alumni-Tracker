"""Forms used by the additive department workflows."""

from django import forms

from .choices import FIELD_OF_STUDY_CHOICES
from .models import Alumnus, ClaimReview, FollowUp


class ComparisonForm(forms.Form):
    """Choose two cohorts for a side-by-side aggregate comparison."""

    batch_a = forms.ChoiceField(label="First cohort")
    batch_b = forms.ChoiceField(label="Second cohort")
    field_of_study = forms.ChoiceField(required=False, label="Program")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        batches = list(
            Alumnus.objects.exclude(batch="")
            .values_list("batch", flat=True)
            .distinct()
            .order_by("batch")
        )
        choices = [(batch, batch) for batch in batches]
        self.fields["batch_a"].choices = choices
        self.fields["batch_b"].choices = choices
        present = set(
            Alumnus.objects.exclude(field_of_study="")
            .values_list("field_of_study", flat=True)
            .distinct()
        )
        self.fields["field_of_study"].choices = [
            ("", "All programs")
        ] + [(code, label) for code, label in FIELD_OF_STUDY_CHOICES if code in present]


class FollowUpForm(forms.ModelForm):
    class Meta:
        model = FollowUp
        fields = ["status", "reason", "note", "next_contact_at"]
        widgets = {
            "next_contact_at": forms.DateInput(attrs={"type": "date"}),
            "note": forms.Textarea(attrs={"rows": 3}),
        }


class ClaimReviewForm(forms.ModelForm):
    class Meta:
        model = ClaimReview
        fields = ["status", "note"]
        widgets = {"note": forms.Textarea(attrs={"rows": 3})}


class DataQualityFilterForm(forms.Form):
    scope = forms.ChoiceField(
        required=False,
        choices=(
            ("all", "All records"),
            ("claimed", "Claimed records"),
            ("unclaimed", "Unclaimed records"),
        ),
        initial="all",
    )
