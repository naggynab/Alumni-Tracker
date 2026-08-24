"""Grant and revoke named department-officer access without opening admin."""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError


User = get_user_model()


class Command(BaseCommand):
    help = "Grant, revoke, or list department report access for named users."

    def add_arguments(self, parser):
        parser.add_argument("email", nargs="?", help="User email to grant or revoke")
        parser.add_argument("--revoke", action="store_true", help="Remove group access")
        parser.add_argument("--list", action="store_true", help="List group members")

    def handle(self, *args, **options):
        group_name = settings.DEPARTMENT_GROUP_NAME
        group, _created = Group.objects.get_or_create(name=group_name)

        if options["list"]:
            self.stdout.write(f"Department group: {group_name}")
            members = group.user_set.order_by("email")
            for user in members:
                self.stdout.write(user.email or user.get_username())
            if not members.exists():
                self.stdout.write("No group members.")
            if settings.DEPARTMENT_EMAILS:
                self.stdout.write("Configured allowlist:")
                for email in settings.DEPARTMENT_EMAILS:
                    self.stdout.write(email)
            if settings.DEPARTMENT_EMAIL_DOMAINS:
                self.stdout.write("Configured trusted domains:")
                for domain in settings.DEPARTMENT_EMAIL_DOMAINS:
                    self.stdout.write(domain)
            return

        email = (options.get("email") or "").strip().lower()
        if not email:
            raise CommandError("Provide an email, or use --list.")

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            raise CommandError(f"No user exists with email {email}.")

        if options["revoke"]:
            group.user_set.remove(user)
            self.stdout.write(self.style.SUCCESS(f"Revoked group access for {email}."))
            if email in settings.DEPARTMENT_EMAILS:
                self.stdout.write(
                    self.style.WARNING(
                        "This email is still in DEPARTMENT_EMAILS and remains allowed "
                        "until the deployment setting is changed."
                    )
                )
            return

        group.user_set.add(user)
        self.stdout.write(self.style.SUCCESS(f"Granted department access to {email}."))
