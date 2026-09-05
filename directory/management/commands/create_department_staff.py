"""Create or update a department-only staff login without linking an alumnus."""

from getpass import getpass

from django.conf import settings
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email

from allauth.account.models import EmailAddress

from directory.models import Alumnus


User = get_user_model()


class Command(BaseCommand):
    help = "Create or update an email/password login for department-only staff."

    def add_arguments(self, parser):
        parser.add_argument("email", help="The department staff member's email address")

    def handle(self, *args, **options):
        email = (options["email"] or "").strip().lower()
        try:
            validate_email(email)
        except ValidationError as error:
            raise CommandError(error.messages[0]) from error

        user = User.objects.filter(email__iexact=email).first()
        if user and Alumnus.objects.filter(user_account=user).exists():
            raise CommandError(
                "This email belongs to an alumni account. Use roll-number login instead."
            )

        password = getpass("Department staff password: ")
        confirmation = getpass("Confirm password: ")
        if not password:
            raise CommandError("The password cannot be empty.")
        if password != confirmation:
            raise CommandError("The passwords do not match.")

        if user is None:
            user = User(email=email, username=self._username(email))
        else:
            user.email = email
        user.is_active = True
        try:
            password_validation.validate_password(password, user=user)
        except ValidationError as error:
            raise CommandError(" ".join(error.messages)) from error
        user.set_password(password)
        user.save()

        EmailAddress.objects.filter(user=user).update(primary=False)
        EmailAddress.objects.update_or_create(
            user=user,
            email=email,
            defaults={"primary": True, "verified": True},
        )

        group, _created = Group.objects.get_or_create(
            name=settings.DEPARTMENT_GROUP_NAME
        )
        group.user_set.add(user)
        self.stdout.write(
            self.style.SUCCESS(
                f"Department staff account ready for {email}. "
                f"Use /accounts/department/login/."
            )
        )

    @staticmethod
    def _username(email):
        """Generate the internal username without exposing a second login ID."""
        import uuid

        return uuid.uuid4().hex[:30]
