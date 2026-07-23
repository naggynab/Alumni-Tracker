from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from directory.choices import FIELD_COMPUTER
from directory.models import Alumnus

User = get_user_model()


class ClaimFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="alum", email="alum@example.com", password="strong-pass-123"
        )
        self.record = Alumnus.objects.create(
            first_name="Aashish", last_name="Karki", batch="078",
            field_of_study=FIELD_COMPUTER, class_roll_no="078BCT004",
            date_of_birth_bs="2056/01/01",
        )
        self.client.force_login(self.user)

    def test_claim_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse("accounts:claim-record"))
        self.assertEqual(resp.status_code, 302)

    def test_successful_claim_links_record(self):
        resp = self.client.post(
            reverse("accounts:claim-record"),
            {
                "batch": "078",
                "field_of_study": FIELD_COMPUTER,
                "last_name": "Karki",
                "class_roll_no": "078BCT004",
                "date_of_birth_bs": "",
            },
        )
        self.assertRedirects(resp, reverse("directory:my-profile"))
        self.record.refresh_from_db()
        self.assertEqual(self.record.user_account, self.user)

    def test_wrong_details_do_not_link(self):
        resp = self.client.post(
            reverse("accounts:claim-record"),
            {
                "batch": "078",
                "field_of_study": FIELD_COMPUTER,
                "last_name": "WrongName",
                "class_roll_no": "078BCT004",
                "date_of_birth_bs": "",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.record.refresh_from_db()
        self.assertIsNone(self.record.user_account)

    def test_missing_identity_field_rejected(self):
        resp = self.client.post(
            reverse("accounts:claim-record"),
            {
                "batch": "078",
                "field_of_study": FIELD_COMPUTER,
                "last_name": "Karki",
                "class_roll_no": "",
                "date_of_birth_bs": "",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "roll number or date of birth")
