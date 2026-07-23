"""Search & filter definitions for the alumni directory.

Implements the six filters requested for the system:
    1. name              - matches across first/middle/last name
    2. batch             - enrollment batch/year
    3. field of study    - canonical field (Computer, Electrical, Electronics...)
    4. current city      - city the alumnus currently lives in
    5. employer          - organization / place where they work
    6. country           - country the alumnus is currently in
"""

from django import forms
from django.db.models import Q
import django_filters
from django_countries import Countries

from .choices import FIELD_OF_STUDY_CHOICES
from .models import Alumnus


def _text_widget(placeholder):
    return forms.TextInput(attrs={"class": "input", "placeholder": placeholder})


class AlumnusFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(
        method="filter_name",
        label="Name",
        widget=_text_widget("e.g. Aashish Karki"),
    )
    batch = django_filters.CharFilter(
        field_name="batch",
        lookup_expr="exact",
        label="Batch / year",
        widget=_text_widget("e.g. 078"),
    )
    field_of_study = django_filters.ChoiceFilter(
        choices=FIELD_OF_STUDY_CHOICES,
        label="Field of study",
        empty_label="Any field",
    )
    current_city = django_filters.CharFilter(
        field_name="current_city",
        lookup_expr="icontains",
        label="Current city",
        widget=_text_widget("e.g. Kathmandu"),
    )
    employer = django_filters.CharFilter(
        field_name="employer_organization",
        lookup_expr="icontains",
        label="Works at",
        widget=_text_widget("e.g. Nepal Telecom"),
    )
    country = django_filters.ChoiceFilter(
        field_name="current_country",
        choices=list(Countries()),
        label="Country",
        empty_label="Any country",
    )

    class Meta:
        model = Alumnus
        fields = ["name", "batch", "field_of_study", "current_city", "employer", "country"]

    def filter_name(self, queryset, name, value):
        """Match each search term against any of the name parts.

        Every whitespace-separated term must appear in at least one of the
        name fields, so "aashish karki" matches a first name of Aashish and a
        last name of Karki regardless of order.
        """
        for term in value.split():
            queryset = queryset.filter(
                Q(first_name__icontains=term)
                | Q(middle_name__icontains=term)
                | Q(last_name__icontains=term)
            )
        return queryset
