"""Search & filter definitions for the alumni directory.

Implements the search portal from the design mockups:
    1. name          - matches across first/middle/last name (free text)
    2. batch         - graduation batch/year (dropdown of batches on record)
    3. field_of_study- program / department (dropdown)
    4. country       - current country (dropdown of countries on record)
    5. current_city  - current city (dropdown of cities on record)
    6. employer      - organization / place where they work (free text)
    7. university    - further-study institution (dropdown)
"""

from collections import defaultdict

from django import forms
from django.db.models import Q
import django_filters
from django_countries import Countries

from .choices import FIELD_OF_STUDY_CHOICES
from .models import Alumnus


def _text(placeholder):
    return forms.TextInput(attrs={"placeholder": placeholder})


class AlumnusFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(
        method="filter_name", label="Name",
        widget=_text("Enter alumni name..."),
    )
    batch = django_filters.ChoiceFilter(
        field_name="batch", lookup_expr="exact", label="Graduation Batch",
        empty_label="Select Batch",
    )
    field_of_study = django_filters.ChoiceFilter(
        choices=FIELD_OF_STUDY_CHOICES, label="Program / Department",
        empty_label="Select Program",
    )
    country = django_filters.ChoiceFilter(
        field_name="current_country", lookup_expr="exact", label="Country",
        empty_label="Select Country",
    )
    current_city = django_filters.ChoiceFilter(
        field_name="current_city", lookup_expr="exact", label="City",
        empty_label="Select City",
    )
    employer = django_filters.CharFilter(
        field_name="employer_organization", lookup_expr="icontains",
        label="Search by Organization", widget=_text("Enter organization..."),
    )
    university = django_filters.ChoiceFilter(
        field_name="further_study_institution", lookup_expr="exact",
        label="Search by University", empty_label="Select University",
    )

    class Meta:
        model = Alumnus
        fields = [
            "name", "batch", "field_of_study", "country",
            "current_city", "employer", "university",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populate the dropdowns from the values actually present in the data
        # so every option returns at least one hit.
        base = Alumnus.objects.filter(is_public=True)
        selected_country = (self.data.get("country", "") or "").strip() if self.data else ""
        selected_city = (self.data.get("current_city", "") or "").strip() if self.data else ""

        batches = (
            base.exclude(batch="").order_by("batch")
            .values_list("batch", flat=True).distinct()
        )
        self.filters["batch"].extra["choices"] = [(b, b) for b in batches]

        city_map = defaultdict(set)
        city_rows = (
            base.exclude(current_city="")
            .values_list("current_country", "current_city")
            .distinct()
        )
        for code, city in city_rows:
            code = (code or "").strip()
            city = (city or "").strip()
            if code and city:
                city_map[code].add(city)

        self.city_choices_by_country = {
            code: sorted(cities, key=str.lower)
            for code, cities in city_map.items()
        }

        if selected_country:
            city_choices = [
                (city, city)
                for city in self.city_choices_by_country.get(selected_country, [])
            ]
            self.filters["current_city"].extra["empty_label"] = "Select City"
        else:
            city_choices = []
            self.filters["current_city"].extra["empty_label"] = "Select Country First"

        self.filters["current_city"].extra["choices"] = city_choices

        unis = (
            base.exclude(further_study_institution="").order_by("further_study_institution")
            .values_list("further_study_institution", flat=True).distinct()
        )
        self.filters["university"].extra["choices"] = [(u, u) for u in unis]

        names = Countries()
        codes = (
            base.exclude(current_country="").order_by("current_country")
            .values_list("current_country", flat=True).distinct()
        )
        country_choices = sorted(
            ((code, names.name(code) or code) for code in codes),
            key=lambda pair: str(pair[1]),
        )
        self.filters["country"].extra["choices"] = country_choices

        # Push the freshly computed choices onto the already-built form fields.
        for key in ("batch", "current_city", "university", "country"):
            computed_choices = list(self.filters[key].extra["choices"])
            if computed_choices and computed_choices[0][0] == "":
                self.form.fields[key].choices = computed_choices
            else:
                self.form.fields[key].choices = [
                    ("", self.filters[key].extra["empty_label"])
                ] + computed_choices

        city_field = self.form.fields["current_city"]
        unique_city_choices = []
        seen_empty = False
        for value, label in city_field.choices:
            if value == "":
                if seen_empty:
                    continue
                seen_empty = True
                unique_city_choices.append(("", self.filters["current_city"].extra["empty_label"]))
            else:
                unique_city_choices.append((value, label))
        city_field.choices = unique_city_choices

        city_field.widget.attrs["data-selected-city"] = selected_city
        if selected_country:
            city_field.widget.attrs.pop("disabled", None)
        else:
            city_field.widget.attrs["disabled"] = "disabled"

    def filter_name(self, queryset, name, value):
        """Every whitespace-separated term must appear in some name part."""
        for term in value.split():
            queryset = queryset.filter(
                Q(first_name__icontains=term)
                | Q(middle_name__icontains=term)
                | Q(last_name__icontains=term)
            )
        return queryset
