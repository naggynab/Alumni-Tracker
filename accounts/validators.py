import re

from django.core.exceptions import ValidationError


class PasswordComplexityValidator:
    """Require the password format used by the alumni login module."""

    def validate(self, password, user=None):
        requirements = (
            (r"[a-z]", "at least one lowercase letter"),
            (r"[A-Z]", "at least one uppercase letter"),
            (r"\d", "at least one number"),
            (r"[^A-Za-z0-9\s]", "at least one special character"),
        )
        missing = [label for pattern, label in requirements if not re.search(pattern, password)]
        if missing:
            raise ValidationError(
                "Password must contain " + ", ".join(missing) + ".",
                code="password_complexity",
            )

    def get_help_text(self):
        return (
            "Use at least 8 characters with one lowercase letter, one uppercase "
            "letter, one number, and one special character."
        )
