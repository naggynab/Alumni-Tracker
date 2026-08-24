"""Small notification and activity helpers used by community workflows."""

from .models import ActivityLog, Notification


def notify_user(user, kind, title, message, url=""):
    if user and getattr(user, "is_authenticated", False):
        return Notification.objects.create(
            recipient=user, kind=kind, title=title, message=message, url=url
        )
    return None


def record_activity(user, action, path="", metadata=None):
    if user and getattr(user, "is_authenticated", False):
        return ActivityLog.objects.create(
            user=user, action=action, path=path[:300], metadata=metadata or {}
        )
    return None
