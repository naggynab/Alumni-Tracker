"""Grant, revoke, or inspect least-privilege department roles."""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError


User = get_user_model()


class Command(BaseCommand):
    help = "Manage department report, editor, and administrator roles."

    def add_arguments(self, parser):
        parser.add_argument("email", nargs="?")
        parser.add_argument("--role", choices=("report", "editor", "admin"))
        parser.add_argument("--revoke", action="store_true")
        parser.add_argument("--list", action="store_true", dest="list_roles")

    def handle(self, *args, **options):
        groups = {
            "report": settings.DEPARTMENT_GROUP_NAME,
            "editor": settings.DEPARTMENT_DATA_EDITOR_GROUP,
            "admin": settings.DEPARTMENT_ADMIN_GROUP,
        }
        if options["list_roles"]:
            for role, name in groups.items():
                group = Group.objects.filter(name=name).first()
                members = list(
                    group.user_set.order_by("email").values_list("email", flat=True)
                ) if group else []
                self.stdout.write(f"{role}: {name} -> {', '.join(members) or '(none)'}")
            return

        email = (options.get("email") or "").strip()
        role = options.get("role")
        if not email or not role:
            raise CommandError("Provide an email and --role, or use --list.")
        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            raise CommandError(f"No user exists with email {email}.")
        group, _created = Group.objects.get_or_create(name=groups[role])
        if options["revoke"]:
            group.user_set.remove(user)
            action = "revoked"
        else:
            group.user_set.add(user)
            action = "granted"
        self.stdout.write(self.style.SUCCESS(f"{action} {role} role for {user.email}."))
