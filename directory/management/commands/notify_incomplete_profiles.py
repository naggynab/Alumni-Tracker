"""Notify claimed alumni whose records remain incomplete."""

from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.mail import send_mail

from directory.models import Alumnus
from directory.profile import profile_completeness


class Command(BaseCommand):
    help = "Email claimed alumni below a profile-completeness threshold."

    def add_arguments(self, parser):
        parser.add_argument("--min-percent", type=int, default=70)
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument(
            "--subject",
            default="Please complete your DOECE Alumni Tracker profile",
        )

    def handle(self, *args, **options):
        threshold = max(0, min(100, options["min_percent"]))
        candidates = (
            Alumnus.objects.filter(user_account__isnull=False)
            .exclude(email="")
            .order_by("id")
        )
        sent = 0
        eligible = 0
        for alumnus in candidates:
            completeness = profile_completeness(alumnus)
            if completeness["percent"] >= threshold:
                continue
            eligible += 1
            if options["limit"] and sent >= options["limit"]:
                continue
            missing = ", ".join(item["label"] for item in completeness["missing"])
            body = (
                f"Hello {alumnus.first_name},\n\n"
                "Please take a moment to update your DOECE Alumni Tracker profile.\n"
                f"Your profile is {completeness['percent']}% complete. "
                f"Suggested fields: {missing}.\n\n"
                "Sign in to the tracker and use Edit Profile to make your updates."
            )
            if not options["dry_run"]:
                send_mail(
                    options["subject"],
                    body,
                    getattr(settings, "DEFAULT_FROM_EMAIL", None),
                    [alumnus.email],
                    fail_silently=False,
                )
            sent += 1
        mode = "would notify" if options["dry_run"] else "notified"
        self.stdout.write(
            self.style.SUCCESS(
                f"{mode} {sent:,} alumni; {eligible:,} eligible below {threshold}%."
            )
        )
