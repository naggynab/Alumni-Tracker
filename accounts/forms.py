import uuid

from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError
from allauth.account import app_settings as allauth_settings
from allauth.account.adapter import get_adapter
from allauth.account.forms import (
    LoginForm as AllauthLoginForm,
    ResetPasswordForm as AllauthResetPasswordForm,
)

from directory.choices import (
    FIELD_OF_STUDY_CHOICES,
    PROGRAM_CHOICES,
    PROGRAM_TO_FIELD,
)
from directory.models import Alumnus

from .authentication import normalize_roll_number

User = get_user_model()


def _normalize_batch(value):
    """'2077' -> '077' to match the campus batch form used across the data."""
    batch = str(value or "").strip()
    if len(batch) == 4 and batch.startswith("20"):
        return batch[1:]
    return batch


class RollNumberLoginForm(AllauthLoginForm):
    """Use the college roll number as the login identifier."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["login"] = forms.CharField(
            label="College roll number",
            max_length=30,
            widget=forms.TextInput(
                attrs={
                    "placeholder": "080BCT047",
                    "autocomplete": "username",
                }
            ),
        )

    def clean_login(self):
        return normalize_roll_number(super().clean_login())

    def user_credentials(self):
        return {
            "roll_number": self.cleaned_data["login"],
            "password": self.cleaned_data["password"],
        }

    def clean(self):
        forms.Form.clean(self)
        if self._errors:
            return

        user = get_adapter(self.request).authenticate(
            self.request, **self.user_credentials()
        )
        if user is None:
            self.add_error(None, "Roll number and/or password is incorrect.")
        else:
            self.user = user
        return self.cleaned_data


class RegistrationForm(forms.Form):
    """Alumni Registration (see Register.svg).

    Creates the account and links it to an alumnus record: an existing
    unclaimed record is matched by roll number, otherwise a new record is
    created from the details provided so the alumnus appears in the yearbook.
    """

    first_name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={"placeholder": "Ram"}))
    last_name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={"placeholder": "Maharjan"}))
    program = forms.ChoiceField(choices=[("", "Select Program")] + list(PROGRAM_CHOICES))
    batch = forms.ChoiceField(
        choices=[("", "Select Year")] + [(str(y), str(y)) for y in range(2082, 2059, -1)]
    )
    roll_number = forms.CharField(
        max_length=30,
        widget=forms.TextInput(
            attrs={"placeholder": "080BCT047", "autocomplete": "username"}
        ),
    )
    date_of_birth = forms.CharField(
        max_length=15, widget=forms.TextInput(attrs={"placeholder": "mm/dd/yyyy"})
    )
    email = forms.EmailField(
        label="Recovery email",
        help_text="Used to reset your password if you forget it.",
        widget=forms.EmailInput(
            attrs={"placeholder": "Ram.mhz@example.com", "autocomplete": "email"}
        ),
    )
    password = forms.CharField(
        min_length=8,
        help_text=(
            "At least 8 characters with a lowercase letter, uppercase letter, "
            "number, and special character."
        ),
        widget=forms.PasswordInput(
            attrs={"placeholder": "Abcd123!", "autocomplete": "new-password"}
        ),
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={"placeholder": "Abcd123!", "autocomplete": "new-password"}
        )
    )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists. Try signing in.")
        return email

    def clean_roll_number(self):
        roll_number = normalize_roll_number(self.cleaned_data["roll_number"])
        if Alumnus.objects.filter(
            class_roll_no__iexact=roll_number,
            user_account__isnull=False,
        ).exists():
            raise forms.ValidationError(
                "An account for this roll number already exists. Try signing in."
            )
        return roll_number

    def clean_password(self):
        password = self.cleaned_data["password"]
        try:
            password_validation.validate_password(password)
        except ValidationError as error:
            raise forms.ValidationError(error.messages)
        return password

    def clean(self):
        cleaned = super().clean()
        roll_number = cleaned.get("roll_number")
        last_name = cleaned.get("last_name")
        if roll_number and last_name:
            unclaimed = Alumnus.objects.filter(
                class_roll_no__iexact=roll_number,
                user_account__isnull=True,
            )
            if unclaimed.exists():
                matches = unclaimed.filter(last_name__iexact=last_name.strip())
                if not matches.exists():
                    self.add_error(
                        "roll_number",
                        "That roll number does not match the supplied last name.",
                    )
                elif matches.count() > 1:
                    self.add_error(
                        "roll_number",
                        "This roll number is linked to multiple records. Please contact the administrator.",
                    )
        pw, cpw = cleaned.get("password"), cleaned.get("confirm_password")
        if pw and cpw and pw != cpw:
            self.add_error("confirm_password", "Passwords do not match.")
        return cleaned

    def save(self):
        data = self.cleaned_data
        field = PROGRAM_TO_FIELD.get(data["program"], "other")
        batch = _normalize_batch(data["batch"])

        # Create the account. Email is marked verified so registration logs
        # the alumnus straight in (email verification is optional in dev).
        from allauth.account.models import EmailAddress

        user = User(email=data["email"], username=uuid.uuid4().hex[:30])
        user.set_password(data["password"])
        user.save()
        EmailAddress.objects.create(
            user=user, email=data["email"], primary=True, verified=True
        )

        # Link an existing unclaimed record by roll number, else create one.
        alumnus = Alumnus.objects.filter(
            user_account__isnull=True,
            class_roll_no__iexact=data["roll_number"].strip(),
            last_name__iexact=data["last_name"].strip(),
        ).first()
        if alumnus is None:
            alumnus = Alumnus(
                first_name=data["first_name"].strip(),
                last_name=data["last_name"].strip(),
                field_of_study=field,
                department_raw=dict(PROGRAM_CHOICES).get(data["program"], ""),
                batch=batch,
                class_roll_no=normalize_roll_number(data["roll_number"]),
                date_of_birth_bs=data["date_of_birth"].strip(),
            )
        alumnus.user_account = user
        if not alumnus.email:
            alumnus.email = data["email"]
        alumnus.save()
        return user


class ClaimRecordForm(forms.Form):
    """Let a verified user claim their pre-loaded alumnus record.

    Identity is confirmed by matching batch + field of study + last name plus
    one of (class roll number, date of birth).
    """

    batch = forms.CharField(max_length=8, label="Batch / year", help_text="e.g. 078")
    field_of_study = forms.ChoiceField(choices=FIELD_OF_STUDY_CHOICES, label="Field of study")
    last_name = forms.CharField(max_length=100)
    class_roll_no = forms.CharField(max_length=30, required=False, label="Class roll no.")
    date_of_birth_bs = forms.CharField(
        max_length=15, required=False, label="Date of birth (B.S.)",
        help_text="Provide roll number or date of birth to confirm identity.",
    )

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("class_roll_no") and not cleaned.get("date_of_birth_bs"):
            raise forms.ValidationError(
                "Enter your class roll number or date of birth to confirm your identity."
            )
        return cleaned

    def find_match(self):
        """Return the single unclaimed Alumnus matching the form, or None."""
        data = self.cleaned_data
        qs = Alumnus.objects.filter(
            user_account__isnull=True,
            batch=data["batch"].strip(),
            field_of_study=data["field_of_study"],
            last_name__iexact=data["last_name"].strip(),
        )
        if data.get("class_roll_no"):
            qs = qs.filter(class_roll_no__iexact=data["class_roll_no"].strip())
        if data.get("date_of_birth_bs"):
            qs = qs.filter(date_of_birth_bs=data["date_of_birth_bs"].strip())

        matches = list(qs[:2])
        return matches[0] if len(matches) == 1 else None


class RollNumberPasswordResetForm(forms.Form):
    """Password reset by roll number — sends the reset link to the recovery
    email the alumnus provided during registration."""

    roll_number = forms.CharField(
        label="College roll number",
        max_length=30,
        widget=forms.TextInput(
            attrs={"placeholder": "080BCT047", "autocomplete": "username"}
        ),
    )

    def clean_roll_number(self):
        roll = normalize_roll_number(self.cleaned_data["roll_number"])
        self.users = []
        try:
            alumnus = Alumnus.objects.select_related("user_account").get(
                class_roll_no__iexact=roll,
                user_account__isnull=False,
            )
        except Alumnus.DoesNotExist:
            if not allauth_settings.PREVENT_ENUMERATION:
                raise forms.ValidationError(
                    "No account found for this roll number."
                )
            return roll
        user = alumnus.user_account
        if user.is_active and user.email:
            self.users = [user]
        return roll

    def save(self, request, **kwargs):
        if self.users:
            AllauthResetPasswordForm._send_password_reset_mail(
                self, request, self.users[0].email, self.users
            )
        return self.cleaned_data["roll_number"]


class AlumnusProfileForm(forms.ModelForm):
    """Fields an alumnus may edit on their own claimed record (Edit Profile.svg)."""

    class Meta:
        model = Alumnus
        fields = [
            "gender",
            "date_of_birth_bs",
            "contact_number",
            "permanent_district",
            "current_city",
            "current_country",
            "employment_status",
            "employer_organization",
            "job_title",
            "further_study_institution",
            "further_study_degree",
            "further_study_country",
        ]
        labels = {
            "date_of_birth_bs": "Date of Birth",
            "contact_number": "Phone Number",
            "permanent_district": "Address",
            "current_city": "City",
            "current_country": "Country",
            "employer_organization": "Current Organization",
            "job_title": "Designation",
            "employment_status": "Employment Status",
            "further_study_institution": "University Name (Post-Grad)",
            "further_study_degree": "Degree Obtained",
            "further_study_country": "Country of Study",
        }
        widgets = {
            "date_of_birth_bs": forms.TextInput(attrs={"placeholder": "mm/dd/yyyy"}),
            "contact_number": forms.TextInput(attrs={"placeholder": "98XXXXXXXX"}),
            "permanent_district": forms.TextInput(attrs={"placeholder": "Address"}),
            "current_city": forms.TextInput(attrs={"placeholder": "City"}),
            "employer_organization": forms.TextInput(attrs={"placeholder": "Organization"}),
            "job_title": forms.TextInput(attrs={"placeholder": "Designation"}),
            "further_study_institution": forms.TextInput(attrs={"placeholder": "Optional"}),
            "further_study_degree": forms.TextInput(attrs={"placeholder": "e.g. MBA, M.Tech"}),
        }
