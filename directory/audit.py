"""Audit helpers for staff-only aggregate reporting actions."""

import json
import logging

from django.utils import timezone


logger = logging.getLogger("directory.audit")


def log_department_action(request, action, filters=None):
    """Record who accessed an aggregate report or export and its filters."""
    selection = {}
    if filters:
        selection = {
            str(key): str(value)
            for key, value in filters.items()
            if key not in {"email", "contact_number"}
        }
    user = getattr(request, "user", None)
    logger.info(
        "department_action=%s timestamp=%s user_email=%s filters=%s",
        action,
        timezone.now().isoformat(),
        getattr(user, "email", "") or "<unknown>",
        json.dumps(selection, sort_keys=True),
    )
