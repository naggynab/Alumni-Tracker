from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.core.mail import EmailMultiAlternatives
from django.test import SimpleTestCase, override_settings

from .email_backend import ResendEmailBackend


class ResendEmailBackendTests(SimpleTestCase):
    @override_settings(
        RESEND_API_KEY="re_test_key",
        DEFAULT_FROM_EMAIL="Alumni Tracker <noreply@example.com>",
    )
    @patch("alumni_tracker.email_backend.resend.Emails.send")
    def test_sends_django_message_through_resend(self, send):
        message = EmailMultiAlternatives(
            subject="Password Reset",
            body="Reset your password.",
            from_email="Alumni Tracker <noreply@example.com>",
            to=["alum@example.com"],
            cc=["audit@example.com"],
            reply_to=["support@example.com"],
        )
        message.attach_alternative("<p>Reset your password.</p>", "text/html")

        sent = ResendEmailBackend().send_messages([message])

        self.assertEqual(sent, 1)
        send.assert_called_once_with(
            {
                "from": "Alumni Tracker <noreply@example.com>",
                "to": ["alum@example.com"],
                "subject": "Password Reset",
                "text": "Reset your password.",
                "html": "<p>Reset your password.</p>",
                "cc": ["audit@example.com"],
                "reply_to": ["support@example.com"],
            }
        )

    @override_settings(RESEND_API_KEY="")
    def test_requires_resend_api_key(self):
        message = EmailMultiAlternatives(
            subject="Password Reset",
            body="Reset your password.",
            to=["alum@example.com"],
        )

        with self.assertRaises(ImproperlyConfigured):
            ResendEmailBackend().send_messages([message])
