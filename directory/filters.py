"""Search & filter definitions for the alumni directory.

Implements the search portal from the design mockups:
    1. name          - matches names or a roll number (free text)
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

from .choices import (
    BATCH_YEAR_CHOICES,
    FIELD_OF_STUDY_CHOICES,
    batch_year_variants,
    normalize_city,
    normalize_institution,
)
from .models import Alumnus


def _text(placeholder):
    return forms.TextInput(attrs={"placeholder": placeholder})


def _representative_choices(queryset, raw_field, normalizer):
    """Return unique normalized values with a useful label and raw fallbacks.

    The canonical columns were added after the first fixture was produced, so
    option discovery intentionally reads the source columns.  Grouping the
    raw values in the database removes exact duplicates; the normalizer then
    also collapses harmless casing/punctuation variants.
    """
    rows = (
        queryset.exclude(**{raw_field: ""})
        .exclude(**{f"{raw_field}__isnull": True})
        .values(raw_field)
        .annotate(raw_count=Count("pk"))
    )
    grouped = {}
    raw_values = defaultdict(list)
    for row in rows:
        raw_value = (row[raw_field] or "").strip()
        value = normalizer(raw_value)
        if not value:
            continue
        raw_values[value].append(raw_value)
        previous = grouped.get(value)
        if previous is None or row["raw_count"] > previous[1] or (
            row["raw_count"] == previous[1] and raw_value.lower() < previous[0].lower()
        ):
            grouped[value] = (raw_value, row["raw_count"])

    choices = sorted(
        ((value, data[0]) for value, data in grouped.items()),
        key=lambda pair: pair[1].lower(),
    )
    return choices, {key: tuple(dict.fromkeys(values)) for key, values in raw_values.items()}


def get_filter_option_data(queryset):
    """Build public directory filter options from the supplied queryset."""
    country_rows = (
        queryset.exclude(current_country="")
        .exclude(current_country__isnull=True)
        .values_list("current_country", flat=True)
        .distinct()
    )
    countries = Countries()
    country_codes = {
        str(code).strip() for code in country_rows if str(code or "").strip()
    }
    country_choices = sorted(
        ((code, countries.name(code) or code) for code in country_codes),
        key=lambda pair: str(pair[1]).lower(),
    )

    city_choices_by_country = {}
    city_raw_values_by_country = {}
    country_city_rows = (
        queryset.exclude(current_country="")
        .exclude(current_country__isnull=True)
        .exclude(current_city="")
        .exclude(current_city__isnull=True)
        .values("current_country", "current_city")
        .annotate(raw_count=Count("pk"))
    )
    grouped_cities = defaultdict(dict)
    for row in country_city_rows:
        country = (row["current_country"] or "").strip()
        raw_city = (row["current_city"] or "").strip()
        city = normalize_city(raw_city)
        if not country or not city:
            continue
        previous = grouped_cities[country].get(city)
        if previous is None or row["raw_count"] > previous[1] or (
            row["raw_count"] == previous[1] and raw_city.lower() < previous[0].lower()
        ):
            grouped_cities[country][city] = (raw_city, row["raw_count"])

    for country, cities in grouped_cities.items():
        city_choices_by_country[country] = sorted(
            ((value, data[0]) for value, data in cities.items()),
            key=lambda pair: pair[1].lower(),
        )
        city_raw_values_by_country[country] = {
            value: tuple(
                dict.fromkeys(
                    row["current_city"].strip()
                    for row in country_city_rows
                    if row["current_country"] == country
                    and normalize_city(row["current_city"]) == value
                )
            )
            for value in cities
        }

    university_choices, university_raw_values = _representative_choices(
        queryset, "further_study_institution", normalize_institution
    )
    return {
        "countries": country_choices,
        "cities_by_country": city_choices_by_country,
        "city_raw_values_by_country": city_raw_values_by_country,
        "universities": university_choices,
        "university_raw_values": university_raw_values,
    }


class AlumnusFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(
        method="filter_name", label="Roll Number / Alumni Search",
        widget=_text("Enter name or roll number..."),
    )
    batch = django_filters.ChoiceFilter(
        method="filter_batch", label="Graduation Batch",
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
        method="filter_city", label="City",
        empty_label="Select City",
    )
    employer = django_filters.CharFilter(
        field_name="employer_organization", lookup_expr="icontains",
        label="Search by Organization", widget=_text("Enter organization..."),
    )
    university = django_filters.ChoiceFilter(
        method="filter_university", label="Search by University",
        empty_label="Select University",
    )

    class Meta:
        model = Alumnus
        fields = [
            "name", "batch", "field_of_study", "country",
            "current_city", "employer", "university",
        ]

    def __init__(self, *args, **kwargs):
        data = kwargs.get("data")
        if data:
            # Keep old bookmarked/search links usable while the public
            # dropdown uses full B.S. years.
            data = data.copy()
            selected_batch = (data.get("batch", "") or "").strip()
            if len(selected_batch) == 3 and selected_batch.isdigit():
                data["batch"] = f"2{selected_batch}"
            kwargs["data"] = data
        super().__init__(*args, **kwargs)
        # Populate the dropdowns from the values actually present in the data
        # so every option returns at least one hit.
        # The view supplies the public queryset.  Keeping option discovery on
        # that queryset prevents private records from leaking into the form.
        base = self.queryset
        selected_country = (self.data.get("country", "") or "").strip() if self.data else ""
        selected_city = (self.data.get("current_city", "") or "").strip() if self.data else ""

        self.filters["batch"].extra["choices"] = list(BATCH_YEAR_CHOICES)

        option_data = get_filter_option_data(base)
        self.city_choices_by_country = option_data["cities_by_country"]
        self.city_raw_values_by_country = option_data["city_raw_values_by_country"]
        self.university_raw_values = option_data["university_raw_values"]
        city_choices = list(self.city_choices_by_country.get(selected_country, [])) if selected_country else []
        self.filters["current_city"].extra["choices"] = city_choices
        self.filters["university"].extra["choices"] = option_data["universities"]
        self.filters["country"].extra["choices"] = option_data["countries"]

        # Push the freshly computed choices onto the already-built form fields.
        # django-filter adds each filter's configured empty_label itself.  Adding
        # another blank choice here creates duplicate placeholders when no public
        # records are available (for example, two "Select Batch" options).
        for key in ("batch", "university", "country"):
            computed_choices = list(self.filters[key].extra["choices"])
            empty_label = self.filters[key].extra.get("empty_label") or "Select"
            self.form.fields[key].choices = [("", empty_label)] + computed_choices

        city_field = self.form.fields["current_city"]
        # django-filter's ChoiceField adds its configured empty label itself;
        # supplying another blank option here would duplicate it.
        city_field.choices = [("", "Select City")] + city_choices

        city_field.widget.attrs["data-selected-city"] = selected_city
        city_field.widget.attrs.pop("disabled", None)

    def filter_name(self, queryset, name, value):
        """Match every term against names, the stored roll, or its serial."""
        for term in value.split():
            queryset = queryset.filter(
                Q(first_name__icontains=term)
                | Q(middle_name__icontains=term)
                | Q(last_name__icontains=term)
                | Q(class_roll_no__icontains=term)
                | Q(roll_number_canonical__icontains=term)
            )
        return queryset

    def filter_city(self, queryset, name, value):
        if not value:
            return queryset
        country = (self.data.get("country", "") or "").strip()
        raw_values = self.city_raw_values_by_country.get(country, {}).get(value, ())
        return queryset.filter(current_country=country).filter(
            Q(current_city_canonical=value) | Q(current_city__in=raw_values)
        ).distinct()

    def filter_university(self, queryset, name, value):
        if not value:
            return queryset
        raw_values = self.university_raw_values.get(value, ())
        return queryset.filter(
            Q(further_study_institution_canonical=value)
            | Q(further_study_institution__in=raw_values)
        ).distinct()

    def filter_batch(self, queryset, name, value):
        """Match both full-year and legacy three-digit stored batch values."""
        variants = batch_year_variants(value)
        return queryset.filter(batch__in=variants) if variants else queryset
