import hashlib
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.urls import reverse
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import FormView
from allauth.account.views import LoginView, PasswordResetView

from directory.models import Alumnus, ClaimReview, TwoFactorCode, TwoFactorSetting

from .forms import (
    AlumnusProfileForm,
    ClaimRecordForm,
    DepartmentEmailLoginForm,
    DepartmentPasswordResetForm,
    RegistrationForm,
    RollNumberPasswordResetForm,
)


logger = logging.getLogger(__name__)


def _code_hash(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class SecureLoginView(LoginView):
    """Route enabled accounts through a short email-code challenge."""

    login_backend = "accounts.authentication.RollNumberBackend"

    def form_valid(self, form):
        user = getattr(form, "user", None)
        setting = TwoFactorSetting.objects.filter(user=user, enabled=True).first()
        if not setting:
            return super().form_valid(form)
        code = f"{secrets.randbelow(1000000):06d}"
        TwoFactorCode.objects.filter(user=user, purpose="login", used_at__isnull=True).update(used_at=timezone.now())
        TwoFactorCode.objects.create(user=user, purpose="login", code_hash=_code_hash(code), expires_at=timezone.now() + timedelta(minutes=10))
        send_mail("DOECE Alumni Tracker login verification", f"Your login verification code is {code}. It expires in 10 minutes.", None, [user.email])
        self.request.session["pending_2fa_user_id"] = user.pk
        self.request.session["pending_2fa_redirect"] = self.get_success_url()
        self.request.session["pending_2fa_backend"] = self.login_backend
        messages.info(self.request, "Enter the verification code sent to your email.")
        return redirect("account_login_2fa")


class DepartmentEmailLoginView(SecureLoginView):
    """Email/password login for approved department-only staff accounts."""

    template_name = "account/department_login.html"
    login_backend = "django.contrib.auth.backends.ModelBackend"

    def get_form_class(self):
        return DepartmentEmailLoginForm

    def get_success_url(self):
        next_url = super().get_success_url()
        if next_url and next_url.startswith("/reports/department/"):
            return next_url
        return reverse("directory:department-report")


def google_login(request):
    """Start Google sign-in when OAuth credentials are configured.

    Keep an incomplete deployment graceful: the provider button is hidden when
    credentials are absent, and direct visits receive a useful message instead
    of an allauth ``SocialApp.DoesNotExist`` server error.
    """
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        messages.warning(
            request,
            "Google sign-in is not configured yet. Use your college roll number instead.",
        )
        return redirect("account_login")

    from allauth.socialaccount.providers.google.views import oauth2_login

    return oauth2_login(request)


def login_2fa(request):
    user_id = request.session.get("pending_2fa_user_id")
    if not user_id:
        return redirect("account_login")
    if request.method == "POST":
        code = (request.POST.get("code") or "").strip()
        record = TwoFactorCode.objects.filter(user_id=user_id, purpose="login", used_at__isnull=True, expires_at__gte=timezone.now()).first()
        if record and secrets.compare_digest(record.code_hash, _code_hash(code)):
            record.used_at = timezone.now()
            record.save(update_fields=["used_at"])
            user = get_user_model().objects.get(pk=user_id)
            backend = request.session.pop(
                "pending_2fa_backend", "accounts.authentication.RollNumberBackend"
            )
            login(request, user, backend=backend)
            destination = request.session.pop("pending_2fa_redirect", reverse("directory:my-profile"))
            request.session.pop("pending_2fa_user_id", None)
            return redirect(destination)
        messages.error(request, "That code is invalid or expired.")
    return render(request, "account/login_2fa.html")


class RollNumberPasswordResetView(FormView):
    template_name = "account/password_reset.html"
    form_class = RollNumberPasswordResetForm
    success_url = reverse_lazy("account_reset_password_done")

    def form_valid(self, form):
        try:
            form.save(self.request)
        except Exception:
            logger.exception("Password reset email delivery failed for roll-number request")
            form.add_error(
                None,
                "We could not send the reset link right now. Please try again later or contact the department.",
            )
            return self.form_invalid(form)
        return super().form_valid(form)


class DepartmentPasswordResetView(PasswordResetView):
    """Password reset form for department-only staff accounts."""

    template_name = "account/department_password_reset.html"

    def get_form_class(self):
        return DepartmentPasswordResetForm

    def form_valid(self, form):
        try:
            return super().form_valid(form)
        except Exception:
            logger.exception("Password reset email delivery failed for department request")
            form.add_error(
                None,
                "We could not send the reset link right now. Please try again later or contact the department.",
            )
            return self.form_invalid(form)


def register(request):
    """Alumni Registration — create an account and link an alumnus record."""
    if request.user.is_authenticated:
        return redirect("directory:my-profile")

    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user, backend="accounts.authentication.RollNumberBackend")
            messages.success(request, "Welcome! Your alumni account is ready.")
            return redirect("directory:my-profile")
    else:
        form = RegistrationForm()

    return render(request, "accounts/register.html", {"form": form, "nav_active": "register"})


@login_required
def claim_record(request):
    """Confirm identity and link the signed-in account to an alumnus record."""
    if getattr(request.user, "alumnus_profile", None):
        messages.info(request, "Your account is already linked to a record.")
        return redirect("directory:my-profile")

    if request.method == "POST":
        form = ClaimRecordForm(request.POST)
        if form.is_valid():
            match = form.find_match()
            if match is None:
                messages.error(
                    request,
                    "No unclaimed record matched those details. "
                    "Double-check your batch, field, name and roll/DOB.",
                )
            else:
                match.user_account = request.user
                if not match.email and request.user.email:
                    match.email = request.user.email
                # The supplied dataset is approved for publication, including
                # records linked during the claim flow.
                match.is_public = True
                match.save(update_fields=["user_account", "email", "is_public", "date_modified"])
                ClaimReview.objects.create(
                    alumnus=match,
                    claimant=request.user,
                    status="pending",
                    note="Created when the record was claimed.",
                )
                messages.success(request, "Record claimed. You can now keep it up to date.")
                return redirect("directory:my-profile")
    else:
        form = ClaimRecordForm()

    return render(request, "accounts/claim_record.html", {"form": form})


@login_required
def edit_profile(request):
    """Let an alumnus edit their own claimed record."""
    alumnus = getattr(request.user, "alumnus_profile", None)
    if alumnus is None:
        messages.info(request, "Link your account to a record first.")
        return redirect("accounts:claim-record")

    if request.method == "POST":
        form = AlumnusProfileForm(request.POST, instance=alumnus)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated.")
            return redirect("directory:my-profile")
    else:
        form = AlumnusProfileForm(instance=alumnus)

    context = {
        "form": form,
        "alumnus": alumnus,
        "app_alumnus": alumnus,
        "nav_active": "edit",
    }
    return render(request, "accounts/edit_profile.html", context)
