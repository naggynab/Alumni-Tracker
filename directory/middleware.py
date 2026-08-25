"""Privacy-conscious account activity history."""

from .notifications import record_activity
from .permissions import is_department_only_staff


DEPARTMENT_ONLY_BLOCKED_PATHS = (
    "/accounts/claim/",
    "/accounts/profile/edit/",
    "/api/v1/",
)


class DepartmentOnlyAccessMiddleware:
    """Keep department-only staff out of alumni self-service endpoints."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path or ""
        department_only = is_department_only_staff(getattr(request, "user", None))
        student_subpage = path.startswith("/student/") and path != "/student/"
        if department_only and (
            student_subpage or path.startswith(DEPARTMENT_ONLY_BLOCKED_PATHS)
        ):
            from django.shortcuts import redirect

            return redirect("directory:department-report")
        return self.get_response(request)


class ActivityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        user = getattr(request, "user", None)
        path = request.path or ""
        if (
            user
            and user.is_authenticated
            and response.status_code < 400
            and not path.startswith(("/static/", "/media/", "/admin/jsi18n/"))
        ):
            record_activity(user, "page_view", path)
        return response
