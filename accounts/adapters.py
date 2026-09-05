from django.contrib import messages
from django.shortcuts import redirect

from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

from directory.models import Alumnus


class RegisteredAlumniSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Allow social authentication only for accounts linked by registration."""

    def is_open_for_signup(self, request, sociallogin):
        return False

    def pre_social_login(self, request, sociallogin):
        user = getattr(sociallogin, "user", None)
        registered_user_id = getattr(user, "pk", None)

        if registered_user_id and Alumnus.objects.filter(
            user_account_id=registered_user_id
        ).exists():
            return

        messages.error(request, "Register as an alumnus before signing in.")
        raise ImmediateHttpResponse(redirect("accounts:register"))
