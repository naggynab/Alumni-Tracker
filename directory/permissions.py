"""Who may see the department report.

The report exposes campus-wide numbers (including unclaimed records), so it is
gated behind explicit grants rather than plain authentication. Access is
granted four ways, checked in order of explicitness:

    1. superusers                       — always
    2. an exact email on DEPARTMENT_EMAILS
    3. membership of one of the department role groups, managed in Django admin
    4. an email under an explicitly configured DEPARTMENT_EMAIL_DOMAINS domain

The email routes let the department onboard staff by setting one environment
variable; the group route lets the admin add someone without a redeploy.
"""

from functools import wraps

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def is_department_staff(user):
    """Return True if `user` may view the department report."""
    if user is None or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    email = (user.email or "").strip().lower()
    if email:
        if email in settings.DEPARTMENT_EMAILS:
            return True

    if user.groups.filter(
        name__in={
            settings.DEPARTMENT_GROUP_NAME,
            settings.DEPARTMENT_DATA_EDITOR_GROUP,
            settings.DEPARTMENT_ADMIN_GROUP,
        }
    ).exists():
        return True

    if email:
        domain = email.rpartition("@")[2]
        if domain and domain in settings.DEPARTMENT_EMAIL_DOMAINS:
            return True

    return False


def _has_group(user, group_name):
    return bool(
        user
        and user.is_authenticated
        and user.groups.filter(name=group_name).exists()
    )


def is_department_data_editor(user):
    """Return True if `user` may change staff workflow records."""
    return bool(
        user
        and user.is_authenticated
        and (
            user.is_superuser
            or is_department_staff(user)
            and (
                _has_group(user, settings.DEPARTMENT_DATA_EDITOR_GROUP)
                or _has_group(user, settings.DEPARTMENT_ADMIN_GROUP)
            )
        )
    )


def is_department_admin(user):
    """Return True if `user` may manage department roles."""
    return bool(
        user
        and user.is_authenticated
        and (user.is_superuser or _has_group(user, settings.DEPARTMENT_ADMIN_GROUP))
    )


def department_required(view):
    """Restrict a view to department staff; anyone else gets a 403."""

    @wraps(view)
    def _wrapped(request, *args, **kwargs):
        if not is_department_staff(request.user):
            raise PermissionDenied(
                "The department report is restricted to department staff."
            )
        return view(request, *args, **kwargs)

    return login_required(_wrapped)


def _role_required(check, message):
    def decorator(view):
        @wraps(view)
        def _wrapped(request, *args, **kwargs):
            if not check(request.user):
                raise PermissionDenied(message)
            return view(request, *args, **kwargs)

        return login_required(_wrapped)

    return decorator


department_data_editor_required = _role_required(
    is_department_data_editor,
    "Only department data editors may change workflow records.",
)
department_admin_required = _role_required(
    is_department_admin,
    "Only department administrators may manage department roles.",
)
