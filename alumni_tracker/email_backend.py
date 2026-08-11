import resend
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from django.core.exceptions import ImproperlyConfigured


class ResendEmailBackend(BaseEmailBackend):

    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        if not settings.RESEND_API_KEY:
            raise ImproperlyConfigured("RESEND_API_KEY must be set to send email with Resend.")

        resend.api_key = settings.RESEND_API_KEY

        sent_count = 0

        for message in email_messages:
            try:
                params = {
                    "from": message.from_email or settings.DEFAULT_FROM_EMAIL,
                    "to": message.to,
                    "subject": message.subject,
                    "text": message.body,
                }
                html_alternative = next(
                    (
                        content
                        for content, mimetype in message.alternatives
                        if mimetype == "text/html"
                    ),
                    None,
                )
                if html_alternative:
                    params["html"] = html_alternative
                if message.cc:
                    params["cc"] = message.cc
                if message.bcc:
                    params["bcc"] = message.bcc
                if message.reply_to:
                    params["reply_to"] = message.reply_to

                resend.Emails.send(params)

                sent_count += 1

            except Exception:
                if not self.fail_silently:
                    raise

        return sent_count
