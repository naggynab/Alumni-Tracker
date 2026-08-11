from django.contrib.auth.backends import BaseBackend

from directory.models import Alumnus


def normalize_roll_number(value):
    """Return roll numbers in a consistent form for storage and lookup."""
    return "".join(str(value or "").split()).upper()


class RollNumberBackend(BaseBackend):
    """Authenticate an account through its linked college roll number."""

    def authenticate(self, request, roll_number=None, password=None, **kwargs):
        if roll_number is None or password is None:
            return None

        normalized_roll_number = normalize_roll_number(roll_number)
        if not normalized_roll_number:
            return None

        records = Alumnus.objects.select_related("user_account").filter(
            user_account__isnull=False,
            class_roll_no__iexact=normalized_roll_number,
        )
        for record in records:
            user = record.user_account
            if user.is_active and user.check_password(password):
                return user
        return None

    def get_user(self, user_id):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
