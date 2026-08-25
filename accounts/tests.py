from urllib.parse import unquote
from types import SimpleNamespace
from unittest.mock import patch

from django.core import mail
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.account.forms import ResetPasswordForm, SetPasswordForm
from allauth.account.models import EmailAddress

from .adapters import RegisteredAlumniSocialAccountAdapter
from .forms import (
    ClaimRecordForm,
    RegistrationForm,
    RollNumberLoginForm,
    RollNumberPasswordResetForm,
)
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
        self.assertTrue(self.record.is_public)

    def test_claim_accepts_equivalent_bs_date_spelling(self):
        form = ClaimRecordForm(
            data={
                "batch": "078",
                "field_of_study": FIELD_COMPUTER,
                "last_name": "Karki",
                "date_of_birth_bs": "2056/1/1",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.find_match(), self.record)

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


class RollNumberLoginTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="roll-login-user",
            email="roll-login@example.com",
            password="ValidPass1!",
        )
        self.record = Alumnus.objects.create(
            first_name="Bikash",
            last_name="Shrestha",
            batch="080",
            field_of_study=FIELD_COMPUTER,
            class_roll_no="080BCT047",
            user_account=self.user,
        )

    def test_login_accepts_roll_number_case_insensitively(self):
        request = RequestFactory().post(
            reverse("account_login"),
            {"login": "080bct047", "password": "ValidPass1!"},
        )
        form = RollNumberLoginForm(
            data={"login": "080bct047", "password": "ValidPass1!"},
            request=request,
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.user, self.user)

    def test_wrong_password_is_rejected(self):
        request = RequestFactory().post(
            reverse("account_login"),
            {"login": "080BCT047", "password": "WrongPass1!"},
        )
        form = RollNumberLoginForm(
            data={"login": "080BCT047", "password": "WrongPass1!"},
            request=request,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("Roll number and/or password is incorrect.", form.non_field_errors())

    def test_login_rejects_a_preloaded_record_until_it_is_registered(self):
        User.objects.create_user(
            username="unregistered-user",
            email="unregistered@example.com",
            password="ValidPass1!",
        )
        Alumnus.objects.create(
            first_name="Unregistered",
            last_name="Alumnus",
            batch="080",
            field_of_study=FIELD_COMPUTER,
            class_roll_no="080BCT048",
        )

        request = RequestFactory().post(
            reverse("account_login"),
            {"login": "080BCT048", "password": "ValidPass1!"},
        )
        form = RollNumberLoginForm(
            data={"login": "080BCT048", "password": "ValidPass1!"},
            request=request,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("Roll number and/or password is incorrect.", form.non_field_errors())


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class RollNumberPasswordResetTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="roll-reset-user",
            email="reset-user@example.com",
            password="ValidPass1!",
        )
        self.record = Alumnus.objects.create(
            first_name="Bikash",
            last_name="Shrestha",
            batch="080",
            field_of_study=FIELD_COMPUTER,
            class_roll_no="080BCT047",
            email="record-recovery@example.com",
            user_account=self.user,
        )

    def test_reset_uses_registered_email_when_user_email_is_empty(self):
        self.user.email = ""
        self.user.save(update_fields=["email"])
        EmailAddress.objects.create(
            user=self.user,
            email="registered-recovery@example.com",
            primary=True,
            verified=True,
        )

        form = RollNumberPasswordResetForm(data={"roll_number": "080BCT047"})

        self.assertTrue(form.is_valid(), form.errors)
        form.save(
            RequestFactory().post(
                reverse("account_reset_password"),
                {"roll_number": "080BCT047"},
            )
        )

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["registered-recovery@example.com"])


class SocialLoginRegistrationGateTests(TestCase):
    def test_unregistered_social_login_is_rejected(self):
        request = RequestFactory().get(reverse("account_login"))
        user = User.objects.create_user(
            username="unregistered-social-user",
            email="unregistered-social@example.com",
            password="ValidPass1!",
        )
        sociallogin = SimpleNamespace(user=user)
        adapter = RegisteredAlumniSocialAccountAdapter()

        with patch("accounts.adapters.messages.error") as add_message:
            with self.assertRaises(ImmediateHttpResponse) as raised:
                adapter.pre_social_login(request, sociallogin)

        self.assertEqual(raised.exception.response.status_code, 302)
        self.assertEqual(raised.exception.response.url, reverse("accounts:register"))
        add_message.assert_called_once()

    def test_social_signup_is_closed(self):
        adapter = RegisteredAlumniSocialAccountAdapter()

        self.assertFalse(adapter.is_open_for_signup(None, None))


class RegistrationSecurityTests(TestCase):
    def registration_data(self, password):
        return {
            "first_name": "Nabina",
            "last_name": "Karki",
            "program": "BCT",
            "batch": "2080",
            "roll_number": "080BCT047",
            "date_of_birth": "2058/01/01",
            "email": "nabina@example.com",
            "password": password,
            "confirm_password": password,
        }

    def test_password_requires_all_character_types(self):
        form = RegistrationForm(data=self.registration_data("Abcdefgh"))

        self.assertFalse(form.is_valid())
        self.assertIn("password", form.errors)
        self.assertIn("number", str(form.errors["password"]))
        self.assertIn("special character", str(form.errors["password"]))

    def test_registration_stores_recovery_email_and_roll_number(self):
        form = RegistrationForm(data=self.registration_data("ValidPass1!"))

        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        record = Alumnus.objects.get(user_account=user)

        self.assertEqual(user.email, "nabina@example.com")
        self.assertEqual(record.class_roll_no, "080BCT047")
        self.assertTrue(record.is_public)
        self.assertTrue(
            EmailAddress.objects.filter(
                user=user, email="nabina@example.com", primary=True, verified=True
            ).exists()
        )

    def test_preloaded_registration_requires_matching_date_of_birth(self):
        Alumnus.objects.create(
            first_name="Nabina",
            last_name="Karki",
            batch="080",
            field_of_study=FIELD_COMPUTER,
            class_roll_no="080BCT047",
            date_of_birth_bs="2057/01/01",
        )

        form = RegistrationForm(data=self.registration_data("ValidPass1!"))

        self.assertFalse(form.is_valid())
        self.assertIn("date_of_birth", form.errors)

    def test_preloaded_registration_accepts_zero_padded_bs_date(self):
        Alumnus.objects.create(
            first_name="Aditya",
            last_name="Shah",
            batch="080",
            field_of_study=FIELD_COMPUTER,
            class_roll_no="080BCT011",
            date_of_birth_bs="12/1/2061",
        )
        data = self.registration_data("ValidPass1!")
        data.update(
            {
                "first_name": "Aditya",
                "last_name": "Shah",
                "roll_number": "080BCT011",
                "date_of_birth": "12/01/2061",
                "email": "aditya@example.com",
            }
        )

        form = RegistrationForm(data=data)

        self.assertTrue(form.is_valid(), form.errors)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_recovery_email_can_request_password_reset(self):
        form = RegistrationForm(data=self.registration_data("ValidPass1!"))
        self.assertTrue(form.is_valid(), form.errors)
        form.save()

        reset_form = ResetPasswordForm(data={"email": "nabina@example.com"})

        self.assertTrue(reset_form.is_valid(), reset_form.errors)
        reset_form.save(
            RequestFactory().post(
                reverse("account_reset_password"),
                {"email": "nabina@example.com"},
            )
        )

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Password Reset", mail.outbox[0].subject)

    def test_password_policy_also_applies_to_reset_password(self):
        form = RegistrationForm(data=self.registration_data("ValidPass1!"))
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()

        reset_form = SetPasswordForm(
            user=user,
            data={"password1": "Abcdefgh", "password2": "Abcdefgh"},
        )

        self.assertFalse(reset_form.is_valid())
        self.assertIn("number", str(reset_form.errors["password1"]))
        self.assertIn("special character", str(reset_form.errors["password1"]))


class LoginFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="login-test",
            email="login-test@example.com",
            password="ValidPass1!",
        )
        Alumnus.objects.create(
            first_name="Login",
            last_name="Tester",
            class_roll_no="080BCT047",
            user_account=self.user,
        )

    def test_roll_number_login_redirects_to_profile(self):
        response = self.client.post(
            reverse("account_login"),
            {"login": "080bct047", "password": "ValidPass1!"},
        )

        self.assertRedirects(response, reverse("directory:my-profile"), fetch_redirect_response=False)
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_google_button_is_hidden_without_credentials(self):
        response = self.client.get(reverse("account_login"))

        self.assertNotContains(response, "Continue with Google")

    def test_unconfigured_google_login_redirects_cleanly(self):
        response = self.client.get(reverse("google_login"))

        self.assertRedirects(response, reverse("account_login"), fetch_redirect_response=False)
        self.assertIn(
            "Google sign-in is not configured yet",
            response.wsgi_request._messages._queued_messages[0].message,
        )

    @override_settings(
        GOOGLE_CLIENT_ID="test-client-id",
        GOOGLE_CLIENT_SECRET="test-client-secret",
        SOCIALACCOUNT_PROVIDERS={
            "google": {
                "SCOPE": ["profile", "email"],
                "AUTH_PARAMS": {"access_type": "online"},
                "APP": {
                    "client_id": "test-client-id",
                    "secret": "test-client-secret",
                    "key": "",
                },
            }
        },
    )
    def test_google_login_starts_with_configured_client(self):
        response = self.client.get(reverse("google_login"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("client_id=test-client-id", response["Location"])
        self.assertIn("/accounts/google/login/callback/", unquote(response["Location"]))
