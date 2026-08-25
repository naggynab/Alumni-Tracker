"""Logged-in student services and community workflows."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.authentication import normalize_roll_number

from .audit import log_department_action
from .notifications import notify_user
from .models import (
    Alumnus,
    ContactRequest,
    CorrectionRequest,
    JobPosting,
)
from .permissions import department_data_editor_required
from .student_forms import (
    ContactRequestForm,
    CorrectionRequestForm,
    CorrectionReviewForm,
    DecisionForm,
    JobPostingForm,
)


def _student_alumnus(request):
    alumnus = getattr(request.user, "alumnus_profile", None)
    if alumnus is None:
        messages.info(request, "Link your alumni record to use Student Services.")
    return alumnus


def _shell_context(request, **extra):
    context = {
        "app_alumnus": getattr(request.user, "alumnus_profile", None),
        "nav_active": "student",
    }
    context.update(extra)
    return context


@login_required
def student_services(request):
    alumnus = _student_alumnus(request)
    if alumnus is None:
        return redirect("accounts:claim-record")
    today = timezone.localdate()
    context = _shell_context(
        request,
        alumnus=alumnus,
        current_jobs=JobPosting.objects.filter(status="published").filter(
            Q(deadline__isnull=True) | Q(deadline__gte=today)
        )[:4],
        pending_corrections=CorrectionRequest.objects.filter(
            alumnus=alumnus, status__in=("pending", "in_review")
        ).count(),
    )
    return render(request, "directory/student_services.html", context)


@login_required
def correction_requests(request):
    alumnus = _student_alumnus(request)
    if alumnus is None:
        return redirect("accounts:claim-record")
    if request.method == "POST":
        form = CorrectionRequestForm(request.POST)
        if form.is_valid():
            field_name = form.cleaned_data["field_name"]
            current_value = str(getattr(alumnus, field_name, "") or "")
            proposed_value = form.cleaned_data["proposed_value"].strip()
            if proposed_value == current_value.strip():
                form.add_error(
                    "proposed_value", "The proposed value is the same as the current value."
                )
            elif CorrectionRequest.objects.filter(
                alumnus=alumnus,
                field_name=field_name,
                status__in=("pending", "in_review"),
            ).exists():
                form.add_error(
                    "field_name",
                    "There is already an open request for this field.",
                )
            else:
                correction = form.save(commit=False)
                correction.alumnus = alumnus
                correction.requester = request.user
                correction.current_value = current_value
                correction.proposed_value = proposed_value
                correction.save()
                notify_user(
                    request.user,
                    "correction",
                    "Correction request submitted",
                    f"Your request for {field_name.replace('_', ' ')} is awaiting review.",
                    "/student/corrections/",
                )
                messages.success(request, "Correction request submitted for review.")
                return redirect("directory:correction-requests")
    else:
        form = CorrectionRequestForm()
    return render(
        request,
        "directory/correction_requests.html",
        _shell_context(
            request,
            alumnus=alumnus,
            form=form,
            corrections=CorrectionRequest.objects.filter(alumnus=alumnus),
        ),
    )


@login_required
def job_board(request):
    alumnus = _student_alumnus(request)
    if alumnus is None:
        return redirect("accounts:claim-record")
    today = timezone.localdate()
    jobs = JobPosting.objects.filter(status="published").filter(
        Q(deadline__isnull=True) | Q(deadline__gte=today)
    )
    mine = JobPosting.objects.filter(posted_by=request.user)
    return render(
        request,
        "directory/job_board.html",
        _shell_context(request, jobs=jobs, mine=mine, alumnus=alumnus),
    )


@login_required
def job_submit(request):
    alumnus = _student_alumnus(request)
    if alumnus is None:
        return redirect("accounts:claim-record")
    if request.method == "POST":
        form = JobPostingForm(request.POST)
        if form.is_valid():
            job = form.save(commit=False)
            job.posted_by = request.user
            job.status = "pending"
            job.save()
            messages.success(request, "Job or internship submitted for review.")
            return redirect("directory:job-board")
    else:
        form = JobPostingForm()
    return render(
        request,
        "directory/job_submit.html",
        _shell_context(request, form=form, alumnus=alumnus),
    )


@login_required
def contact_requests(request):
    alumnus = _student_alumnus(request)
    if alumnus is None:
        return redirect("accounts:claim-record")
    return render(
        request,
        "directory/contact_requests.html",
        _shell_context(
            request,
            alumnus=alumnus,
            form=ContactRequestForm(),
            sent=ContactRequest.objects.filter(
                sender=request.user
            ).select_related("recipient"),
            received=ContactRequest.objects.filter(
                recipient=request.user
            ).select_related("sender"),
        ),
    )


@login_required
def contact_request_create(request):
    sender_alumnus = _student_alumnus(request)
    if sender_alumnus is None:
        return redirect("accounts:claim-record")
    if request.method != "POST":
        return redirect("directory:contact-requests")
    form = ContactRequestForm(request.POST)
    if form.is_valid():
        roll = normalize_roll_number(form.cleaned_data["recipient_roll_number"])
        matches = list(
            Alumnus.objects.filter(
                class_roll_no__iexact=roll,
                user_account__isnull=False,
                is_public=True,
            ).exclude(user_account=request.user)[:2]
        )
        if len(matches) != 1:
            form.add_error(
                "recipient_roll_number",
                "Use a complete roll number; no unique public account matched it.",
            )
        else:
            recipient = matches[0].user_account
            if ContactRequest.objects.filter(
                sender=request.user,
                recipient=recipient,
                status="pending",
            ).exists():
                form.add_error(None, "You already have a pending request to this person.")
            else:
                ContactRequest.objects.create(
                    sender=request.user,
                    recipient=recipient,
                    message=form.cleaned_data["message"],
                )
                notify_user(
                    recipient,
                    "contact",
                    "New private contact request",
                    f"{sender_alumnus.full_name} would like to connect with you.",
                    "/student/contacts/",
                )
                messages.success(request, "Private contact request sent.")
                return redirect("directory:contact-requests")
    return render(
        request,
        "directory/contact_requests.html",
        _shell_context(
            request,
            alumnus=sender_alumnus,
            form=form,
            sent=ContactRequest.objects.filter(
                sender=request.user
            ).select_related("recipient"),
            received=ContactRequest.objects.filter(
                recipient=request.user
            ).select_related("sender"),
        ),
    )


@login_required
def contact_request_decision(request, request_id):
    if request.method != "POST":
        return redirect("directory:contact-requests")
    contact = get_object_or_404(
        ContactRequest, pk=request_id, recipient=request.user, status="pending"
    )
    form = DecisionForm(request.POST)
    if form.is_valid():
        contact.status = form.cleaned_data["status"]
        contact.response_note = form.cleaned_data["response_note"]
        contact.responded_at = timezone.now()
        contact.save()
        notify_user(
            contact.sender,
            "contact",
            "Private contact request updated",
            f"Your private contact request was {contact.get_status_display().lower()}.",
            "/student/contacts/",
        )
        messages.success(request, "Contact request updated.")
    return redirect("directory:contact-requests")


@department_data_editor_required
def correction_review_queue(request):
    status = request.GET.get("status", "pending")
    requests = CorrectionRequest.objects.select_related(
        "alumnus", "requester", "reviewer"
    )
    if status in dict(CorrectionRequest.STATUS_CHOICES):
        requests = requests.filter(status=status)
    else:
        status = "pending"
        requests = requests.filter(status=status)
    return render(
        request,
        "directory/correction_review_queue.html",
        {
            "requests": requests[:100],
            "status": status,
            "status_choices": CorrectionRequest.STATUS_CHOICES,
            "app_alumnus": getattr(request.user, "alumnus_profile", None),
            "nav_active": "report",
        },
    )


@department_data_editor_required
def correction_review(request, request_id):
    correction = get_object_or_404(CorrectionRequest, pk=request_id)
    if request.method == "POST":
        form = CorrectionReviewForm(request.POST, instance=correction)
        if form.is_valid():
            correction = form.save(commit=False)
            if correction.status == "approved":
                allowed = dict(CorrectionRequestFieldChoices())
                if correction.field_name not in allowed:
                    messages.error(request, "That field is not allowed for self-service correction.")
                    return redirect("directory:correction-review-queue")
                setattr(correction.alumnus, correction.field_name, correction.proposed_value)
                correction.alumnus.save(
                    update_fields=[correction.field_name, "date_modified"]
                )
            correction.reviewer = request.user
            correction.reviewed_at = (
                timezone.now() if correction.status in ("approved", "rejected") else None
            )
            correction.save()
            notify_user(
                correction.requester,
                "correction",
                "Correction request reviewed",
                f"Your correction request was {correction.get_status_display().lower()}.",
                "/student/corrections/",
            )
            log_department_action(
                request,
                "correction_review",
                {"request_id": request_id, "status": correction.status},
            )
            messages.success(request, "Correction request reviewed.")
    return redirect("directory:correction-review-queue")


def CorrectionRequestFieldChoices():
    from .student_forms import CORRECTABLE_FIELDS

    return CORRECTABLE_FIELDS


@department_data_editor_required
def community_moderation(request):
    pending_jobs = JobPosting.objects.filter(status="pending").select_related("posted_by")
    if request.method == "POST":
        kind = request.POST.get("kind")
        object_id = request.POST.get("object_id")
        status = request.POST.get("status")
        if kind == "job":
            item = get_object_or_404(JobPosting, pk=object_id, status="pending")
            choices = {"published", "rejected", "closed"}
        else:
            item = None
            choices = set()
        if item is not None and status in choices:
            item.status = status
            item.reviewed_by = request.user
            item.reviewed_at = timezone.now()
            item.save()
            messages.success(request, "Community submission moderated.")
            return redirect("directory:community-moderation")
        messages.error(request, "Invalid moderation action.")
    return render(
        request,
        "directory/community_moderation.html",
        {
            "pending_jobs": pending_jobs,
            "app_alumnus": getattr(request.user, "alumnus_profile", None),
            "nav_active": "report",
        },
    )
