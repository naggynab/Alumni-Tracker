from django.test import TestCase
from django.urls import reverse

from .choices import normalize_field_of_study, normalize_gender, FIELD_COMPUTER, FIELD_ELECTRICAL
from .filters import AlumnusFilter
from .models import Alumnus


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


class FilterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Alumnus.objects.create(
            first_name="Aashish", last_name="Karki", batch="078",
            field_of_study=FIELD_COMPUTER, current_city="Kathmandu",
            current_country="NP", employer_organization="Nepal Telecom",
        )
        Alumnus.objects.create(
            first_name="Bindu", last_name="Paudel", batch="078",
            field_of_study=FIELD_ELECTRICAL, current_city="Lalitpur",
            current_country="US", employer_organization="LogPoint",
        )

    def _count(self, params):
        return AlumnusFilter(params, queryset=Alumnus.objects.all()).qs.count()

    def test_name_filter(self):
        self.assertEqual(self._count({"name": "karki"}), 1)
        self.assertEqual(self._count({"name": "aashish karki"}), 1)

    def test_batch_and_field(self):
        self.assertEqual(self._count({"batch": "078"}), 2)
        self.assertEqual(self._count({"field_of_study": FIELD_ELECTRICAL}), 1)

    def test_city_employer_country(self):
        self.assertEqual(self._count({"current_city": "kathmandu"}), 1)
        self.assertEqual(self._count({"employer": "telecom"}), 1)
        self.assertEqual(self._count({"country": "US"}), 1)

    def test_combined(self):
        self.assertEqual(self._count({"batch": "078", "field_of_study": FIELD_COMPUTER}), 1)


class ViewTests(TestCase):
    def test_home_and_list_render(self):
        self.assertEqual(self.client.get(reverse("directory:home")).status_code, 200)
        self.assertEqual(self.client.get(reverse("directory:alumni-list")).status_code, 200)

    def test_private_record_hidden(self):
        a = Alumnus.objects.create(first_name="Hidden", last_name="Person", is_public=False)
        self.assertEqual(self.client.get(a.get_absolute_url()).status_code, 404)
