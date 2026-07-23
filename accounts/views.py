from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from directory.models import Alumnus

from .forms import AlumnusProfileForm, ClaimRecordForm


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
                match.save(update_fields=["user_account", "email", "date_modified"])
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

    return render(request, "accounts/edit_profile.html", {"form": form, "alumnus": alumnus})
