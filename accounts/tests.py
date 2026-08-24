from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from urllib.parse import unquote

from directory.models import Alumnus


User = get_user_model()


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
        self.assertIn("Google sign-in is not configured yet", response.wsgi_request._messages._queued_messages[0].message)

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
        }
    )
    def test_google_login_starts_with_configured_client(self):
        response = self.client.get(reverse("google_login"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("client_id=test-client-id", response["Location"])
        self.assertIn("/accounts/google/login/callback/", unquote(response["Location"]))
