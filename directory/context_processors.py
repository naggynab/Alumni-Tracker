"""Template context shared across the app."""

from .permissions import (
    is_department_admin,
    is_department_data_editor,
    is_department_only_staff,
    is_department_staff,
)


def department_access(request):
    """Expose report access so the sidebar can show or hide the link."""
    return {
        "is_department_staff": is_department_staff(getattr(request, "user", None)),
        "is_department_only_staff": is_department_only_staff(
            getattr(request, "user", None)
        ),
        "can_edit_workflows": is_department_data_editor(
            getattr(request, "user", None)
        ),
        "can_manage_department_roles": is_department_admin(
            getattr(request, "user", None)
        ),
    }
