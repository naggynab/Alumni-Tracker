"""Forms for the directory app."""

from django import forms
from django_countries import Countries

from .choices import EMPLOYMENT_STATUS_CHOICES, FIELD_OF_STUDY_CHOICES
from .models import Alumnus, ClaimReview, FollowUp


class ReportFilterForm(forms.Form):
    """Narrow the staff report to a batch range, program, country or status.

    Dropdowns are built from the values actually on record so every option
    returns at least one alumnus.
    """

    batch = forms.ChoiceField(required=False, label="Batch")
    batch_from = forms.ChoiceField(required=False, label="From batch")
    batch_to = forms.ChoiceField(required=False, label="To batch")
    field_of_study = forms.ChoiceField(required=False, label="Program")
    country = forms.ChoiceField(required=False, label="Current country")
    employment_status = forms.ChoiceField(required=False, label="Employment status")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        base = Alumnus.objects.all()
        names = Countries()

        batches = (
            base.exclude(batch="").order_by("batch")
            .values_list("batch", flat=True).distinct()
        )
        batch_choices = [(b, b) for b in batches]
        self.fields["batch"].choices = [("", "All batches")] + batch_choices
        self.fields["batch_from"].choices = [("", "Any starting batch")] + batch_choices
        self.fields["batch_to"].choices = [("", "Any ending batch")] + batch_choices

        fields_present = set(
            base.exclude(field_of_study="")
            .values_list("field_of_study", flat=True)
            .distinct()
        )
        self.fields["field_of_study"].choices = [("", "All programs")] + [
            (code, label)
            for code, label in FIELD_OF_STUDY_CHOICES
            if code in fields_present
        ]

        codes = (
            base.exclude(current_country="").order_by("current_country")
            .values_list("current_country", flat=True).distinct()
        )
        self.fields["country"].choices = [("", "All countries")] + sorted(
            ((code, names.name(code) or code) for code in codes),
            key=lambda pair: str(pair[1]),
        )

        statuses_present = set(
            base.exclude(employment_status="")
            .values_list("employment_status", flat=True)
            .distinct()
        )
        self.fields["employment_status"].choices = [("", "All statuses")] + [
            (code, label)
            for code, label in EMPLOYMENT_STATUS_CHOICES
            if code in statuses_present
        ]

    def apply(self, queryset):
        """Return `queryset` narrowed by whichever filters were supplied."""
        data = self.cleaned_data
        if data.get("batch"):
            queryset = queryset.filter(batch=data["batch"])
        if data.get("batch_from"):
            queryset = queryset.filter(batch__gte=data["batch_from"])
        if data.get("batch_to"):
            queryset = queryset.filter(batch__lte=data["batch_to"])
        if data.get("field_of_study"):
            queryset = queryset.filter(field_of_study=data["field_of_study"])
        if data.get("country"):
            queryset = queryset.filter(current_country=data["country"])
        if data.get("employment_status"):
            queryset = queryset.filter(employment_status=data["employment_status"])
        return queryset

    def summary(self):
        """A human-readable description of the current selection."""
        if not self.is_bound or not self.is_valid():
            return "All alumni on record"

        parts = []
        for name in (
            "field_of_study",
            "batch",
            "batch_from",
            "batch_to",
            "country",
            "employment_status",
        ):
            value = self.cleaned_data.get(name)
            if not value:
                continue
            label = dict(self.fields[name].choices).get(value, value)
            prefix = {
                "batch": "batch ",
                "batch_from": "from batch ",
                "batch_to": "to batch ",
                "country": "living in ",
                "employment_status": "status ",
            }.get(name, "")
            parts.append(f"{prefix}{label}")

        return " · ".join(parts) if parts else "All alumni on record"
