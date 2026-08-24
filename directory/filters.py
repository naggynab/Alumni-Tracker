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
from django.db.models import Count, Q
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
        field_name="current_city_canonical", lookup_expr="exact", label="City",
        empty_label="Select City",
    )
    employer = django_filters.CharFilter(
        field_name="employer_organization", lookup_expr="icontains",
        label="Search by Organization", widget=_text("Enter organization..."),
    )
    university = django_filters.ChoiceFilter(
        field_name="further_study_institution_canonical", lookup_expr="exact",
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

        city_map = defaultdict(dict)
        city_rows = (
            base.exclude(current_city="")
            .values("current_country", "current_city_canonical", "current_city")
            .annotate(raw_count=Count("id"))
        )
        for row in city_rows:
            code = (row["current_country"] or "").strip()
            canonical = (row["current_city_canonical"] or "").strip()
            city = (row["current_city"] or "").strip()
            if code and canonical:
                previous = city_map[code].get(canonical)
                if previous is None or row["raw_count"] > previous["count"]:
                    city_map[code][canonical] = {"label": city, "count": row["raw_count"]}

        self.city_choices_by_country = {
            code: sorted(
                [(value, data["label"]) for value, data in cities.items()],
                key=lambda pair: pair[1].lower(),
            )
            for code, cities in city_map.items()
        }

        if selected_country:
            city_choices = [
                (value, label)
                for value, label in self.city_choices_by_country.get(selected_country, [])
            ]
            self.filters["current_city"].extra["empty_label"] = "Select City"
        else:
            all_cities = {}
            for choices in self.city_choices_by_country.values():
                for value, label in choices:
                    all_cities[value] = label
            city_choices = sorted(all_cities.items(), key=lambda pair: pair[1].lower())
            self.filters["current_city"].extra["empty_label"] = "Select City"

        self.filters["current_city"].extra["choices"] = city_choices

        uni_rows = (
            base.exclude(further_study_institution_canonical="")
            .values("further_study_institution_canonical", "further_study_institution")
            .annotate(raw_count=Count("id"))
        )
        uni_labels = {}
        for row in uni_rows:
            value = row["further_study_institution_canonical"]
            if value not in uni_labels or row["raw_count"] > uni_labels[value][1]:
                uni_labels[value] = (row["further_study_institution"], row["raw_count"])
        self.filters["university"].extra["choices"] = sorted(
            [(value, data[0]) for value, data in uni_labels.items()],
            key=lambda pair: pair[1].lower(),
        )

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
        # django-filter adds each filter's configured empty_label itself.  Adding
        # another blank choice here creates duplicate placeholders when no public
        # records are available (for example, two "Select Batch" options).
        for key in ("batch", "university", "country"):
            computed_choices = list(self.filters[key].extra["choices"])
            self.form.fields[key].choices = computed_choices

        city_field = self.form.fields["current_city"]
        # django-filter's ChoiceField adds its configured empty label itself;
        # supplying another blank option here would duplicate it.
        city_field.choices = city_choices

        city_field.widget.attrs["data-selected-city"] = selected_city
        city_field.widget.attrs.pop("disabled", None)

    def filter_name(self, queryset, name, value):
        """Every whitespace-separated term must appear in some name part."""
        for term in value.split():
            queryset = queryset.filter(
                Q(first_name__icontains=term)
                | Q(middle_name__icontains=term)
                | Q(last_name__icontains=term)
            )
        return queryset
