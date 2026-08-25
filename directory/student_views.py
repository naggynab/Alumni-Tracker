"""Logged-in student services and community workflows."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from accounts.authentication import normalize_roll_number

from .audit import log_department_action
from .notifications import notify_user
from .models import (
    AlumniEvent,
    AlumniStory,
    Alumnus,
    ContactRequest,
    CorrectionRequest,
    EventRegistration,
    JobPosting,
    MentorshipProfile,
    MentorshipRequest,
    Resource,
    ServiceRequestReply,
)
from .permissions import department_data_editor_required
from .student_forms import (
    AlumniEventForm,
    ContactRequestForm,
    CorrectionRequestForm,
    CorrectionReviewForm,
    DecisionForm,
    JobPostingForm,
    MentorshipProfileForm,
    MentorshipRequestForm,
    ServiceRequestReplyForm,
)


SERVICE_REQUEST_DEFINITIONS = {
    "correction": {
        "label": "Correction request",
        "model": CorrectionRequest,
        "requester_field": "requester",
        "select_related": ("alumnus", "requester", "reviewer"),
        "url": "directory:correction-requests",
        "status_choices": CorrectionRequest.STATUS_CHOICES,
    },
    "job": {
        "label": "Job or internship submission",
        "model": JobPosting,
        "requester_field": "posted_by",
        "select_related": ("posted_by", "reviewed_by"),
        "url": "directory:job-board",
        "status_choices": JobPosting.STATUS_CHOICES,
    },
    "event": {
        "label": "Event submission",
        "model": AlumniEvent,
        "requester_field": "organizer",
        "select_related": ("organizer", "reviewed_by"),
        "url": "directory:event-list",
        "status_choices": AlumniEvent.STATUS_CHOICES,
    },
    "story": {
        "label": "Story submission",
        "model": AlumniStory,
        "requester_field": "author",
        "select_related": ("author", "reviewed_by"),
        "url": "directory:stories",
        "status_choices": AlumniStory.STATUS_CHOICES,
    },
    "resource": {
        "label": "Resource submission",
        "model": Resource,
        "requester_field": "submitted_by",
        "select_related": ("submitted_by", "reviewed_by"),
        "url": "directory:resources",
        "status_choices": Resource.STATUS_CHOICES,
    },
}


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


def attach_service_replies(items):
    """Attach durable department replies to a list of one model type."""
    items = list(items)
    if not items:
        return items
    content_type = ContentType.objects.get_for_model(items[0])
    replies = ServiceRequestReply.objects.filter(
        content_type=content_type,
        object_id__in=[item.pk for item in items],
    ).select_related("author")
    by_object = {}
    for reply in replies:
        by_object.setdefault(reply.object_id, []).append(reply)
    for item in items:
        item.service_replies = by_object.get(item.pk, [])
    return items


def _request_title(kind, item):
    if kind == "correction":
        return f"{item.alumnus.full_name} - {item.field_name.replace('_', ' ').title()}"
    if kind == "job":
        return f"{item.title} - {item.organization}"
    if kind == "event":
        return item.title
    return item.title


def _request_summary(kind, item):
    if kind == "correction":
        return (
            f"Current: {item.current_value or '-'} | "
            f"Proposed: {item.proposed_value}"
            + (f" | Reason: {item.reason}" if item.reason else "")
        )
    if kind == "job":
        return item.description
    if kind == "event":
        return item.description
    if kind == "story":
        return item.body
    return item.description


def _request_status_choices(kind, item):
    choices = list(SERVICE_REQUEST_DEFINITIONS[kind]["status_choices"])
    if item.status not in dict(choices):
        choices.insert(0, (item.status, item.get_status_display()))
    return choices


def _request_entries(status_filter="pending"):
    entries = []
    for kind, definition in SERVICE_REQUEST_DEFINITIONS.items():
        queryset = definition["model"].objects.select_related(
            *definition["select_related"]
        )
        if status_filter == "pending":
            queryset = queryset.filter(status="pending")
        elif status_filter == "active":
            queryset = queryset.filter(status__in=("pending", "in_review"))
        items = attach_service_replies(queryset[:100])
        for item in items:
            if status_filter == "replied" and not item.service_replies:
                continue
            requester = getattr(item, definition["requester_field"], None)
            entries.append(
                {
                    "kind": kind,
                    "label": definition["label"],
                    "item": item,
                    "title": _request_title(kind, item),
                    "summary": _request_summary(kind, item),
                    "requester": requester,
                    "status_choices": _request_status_choices(kind, item),
                    "url": definition["url"],
                }
            )
    return sorted(entries, key=lambda entry: entry["item"].created_at, reverse=True)


@login_required
def student_services(request):
    alumnus = _student_alumnus(request)
    if alumnus is None:
        return redirect("accounts:claim-record")
    today = timezone.localdate()
    now = timezone.now()
    context = _shell_context(
        request,
        alumnus=alumnus,
        upcoming_events=AlumniEvent.objects.filter(
            status="published", starts_at__gte=now
        )[:4],
        current_jobs=JobPosting.objects.filter(status="published").filter(
            Q(deadline__isnull=True) | Q(deadline__gte=today)
        )[:4],
        mentors=MentorshipProfile.objects.filter(
            is_available=True,
            alumnus__is_public=True,
            alumnus__user_account__isnull=False,
        ).exclude(alumnus=alumnus)[:4],
        pending_corrections=CorrectionRequest.objects.filter(
            alumnus=alumnus, status__in=("pending", "in_review")
        ).count(),
        pending_requests=MentorshipRequest.objects.filter(
            mentee=alumnus, status="pending"
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
            corrections=attach_service_replies(
                CorrectionRequest.objects.filter(alumnus=alumnus)
            ),
        ),
    )


@login_required
def mentorship_hub(request):
    alumnus = _student_alumnus(request)
    if alumnus is None:
        return redirect("accounts:claim-record")
    profiles = (
        MentorshipProfile.objects.filter(
            is_available=True,
            alumnus__is_public=True,
            alumnus__user_account__isnull=False,
        )
        .exclude(alumnus=alumnus)
        .annotate(
            active_mentees=Count(
                "alumnus__mentorship_requests_received",
                filter=Q(alumnus__mentorship_requests_received__status="accepted"),
            )
        )
        .select_related("alumnus")
    )
    return render(
        request,
        "directory/mentorship.html",
        _shell_context(
            request,
            alumnus=alumnus,
            profiles=profiles,
            sent_requests=MentorshipRequest.objects.filter(
                mentee=alumnus
            ).select_related("mentor"),
            received_requests=MentorshipRequest.objects.filter(
                mentor=alumnus
            ).select_related("mentee"),
        ),
    )


@login_required
def mentorship_profile(request):
    alumnus = _student_alumnus(request)
    if alumnus is None:
        return redirect("accounts:claim-record")
    profile, _created = MentorshipProfile.objects.get_or_create(alumnus=alumnus)
    if request.method == "POST":
        form = MentorshipProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Mentorship profile saved.")
            return redirect("directory:mentorship")
    else:
        form = MentorshipProfileForm(instance=profile)
    return render(
        request,
        "directory/mentorship_profile.html",
        _shell_context(request, form=form, alumnus=alumnus),
    )


@login_required
def mentorship_request(request, mentor_id):
    mentee = _student_alumnus(request)
    if mentee is None:
        return redirect("accounts:claim-record")
    profile = get_object_or_404(
        MentorshipProfile.objects.select_related("alumnus"),
        alumnus_id=mentor_id,
        is_available=True,
        alumnus__is_public=True,
        alumnus__user_account__isnull=False,
    )
    mentor = profile.alumnus
    if mentor == mentee:
        messages.error(request, "You cannot request yourself as a mentor.")
        return redirect("directory:mentorship")
    if request.method == "POST":
        form = MentorshipRequestForm(request.POST)
        active_count = MentorshipRequest.objects.filter(
            mentor=mentor, status="accepted"
        ).count()
        if active_count >= profile.max_mentees:
            form.add_error(None, "This mentor is currently at capacity.")
        elif MentorshipRequest.objects.filter(
            mentor=mentor, mentee=mentee, status="pending"
        ).exists():
            form.add_error(None, "You already have a pending request to this mentor.")
        elif form.is_valid():
            request_record = form.save(commit=False)
            request_record.mentor = mentor
            request_record.mentee = mentee
            request_record.save()
            notify_user(
                mentor.user_account,
                "mentorship",
                "New mentorship request",
                f"{mentee.full_name} sent you a mentorship request.",
                "/student/mentorship/",
            )
            messages.success(request, "Mentorship request sent.")
            return redirect("directory:mentorship")
    else:
        form = MentorshipRequestForm()
    return render(
        request,
        "directory/mentorship_request.html",
        _shell_context(request, form=form, mentor=mentor, profile=profile),
    )


@login_required
def mentorship_decision(request, request_id):
    mentor = _student_alumnus(request)
    if mentor is None:
        return redirect("accounts:claim-record")
    mentorship = get_object_or_404(
        MentorshipRequest, pk=request_id, mentor=mentor, status="pending"
    )
    if request.method == "POST":
        form = DecisionForm(request.POST)
        if form.is_valid():
            if form.cleaned_data["status"] == "accepted":
                capacity = MentorshipProfile.objects.filter(
                    alumnus=mentor
                ).values_list("max_mentees", flat=True).first() or 0
                active_count = MentorshipRequest.objects.filter(
                    mentor=mentor, status="accepted"
                ).count()
                if active_count >= capacity:
                    messages.error(request, "Your mentorship capacity has been reached.")
                    return redirect("directory:mentorship")
            mentorship.status = form.cleaned_data["status"]
            mentorship.response_note = form.cleaned_data["response_note"]
            mentorship.responded_at = timezone.now()
            mentorship.save()
            notify_user(
                mentorship.mentee.user_account,
                "mentorship",
                "Mentorship request updated",
                f"Your mentorship request was {mentorship.get_status_display().lower()}.",
                "/student/mentorship/",
            )
            messages.success(request, "Mentorship request updated.")
    return redirect("directory:mentorship")


@login_required
def job_board(request):
    alumnus = _student_alumnus(request)
    if alumnus is None:
        return redirect("accounts:claim-record")
    today = timezone.localdate()
    jobs = JobPosting.objects.filter(status="published").filter(
        Q(deadline__isnull=True) | Q(deadline__gte=today)
    )
    mine = attach_service_replies(JobPosting.objects.filter(posted_by=request.user))
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
def event_list(request):
    alumnus = _student_alumnus(request)
    if alumnus is None:
        return redirect("accounts:claim-record")
    now = timezone.now()
    events = AlumniEvent.objects.filter(status="published", starts_at__gte=now)
    registered = set(
        EventRegistration.objects.filter(
            attendee=request.user, status="registered"
        ).values_list("event_id", flat=True)
    )
    return render(
        request,
        "directory/event_list.html",
        _shell_context(
            request,
            events=events,
            registered=registered,
            mine=attach_service_replies(
                AlumniEvent.objects.filter(organizer=request.user)
            ),
            alumnus=alumnus,
        ),
    )


@login_required
def event_submit(request):
    alumnus = _student_alumnus(request)
    if alumnus is None:
        return redirect("accounts:claim-record")
    if request.method == "POST":
        form = AlumniEventForm(request.POST)
        if form.is_valid():
            event = form.save(commit=False)
            event.organizer = request.user
            event.status = "pending"
            event.save()
            messages.success(request, "Event submitted for review.")
            return redirect("directory:event-list")
    else:
        form = AlumniEventForm()
    return render(
        request,
        "directory/event_submit.html",
        _shell_context(request, form=form, alumnus=alumnus),
    )


@login_required
def event_registration(request, event_id):
    if request.method != "POST":
        return redirect("directory:event-list")
    event = get_object_or_404(AlumniEvent, pk=event_id, status="published")
    action = request.POST.get("action", "register")
    registration, _created = EventRegistration.objects.get_or_create(
        event=event, attendee=request.user
    )
    if action == "cancel":
        registration.status = "cancelled"
        registration.save(update_fields=["status", "updated_at"])
        messages.info(request, "Event registration cancelled.")
    else:
        if event.max_attendees and EventRegistration.objects.filter(
            event=event, status="registered"
        ).exclude(attendee=request.user).count() >= event.max_attendees:
            messages.error(request, "This event is currently full.")
        else:
            registration.status = "registered"
            registration.save(update_fields=["status", "updated_at"])
            messages.success(request, "You are registered for the event.")
    return redirect("directory:event-list")


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
def student_request_replies(request):
    """Review department-owned student-service submissions and reply."""
    if request.method == "POST":
        kind = request.POST.get("kind")
        definition = SERVICE_REQUEST_DEFINITIONS.get(kind)
        if definition is None:
            messages.error(request, "That student request is not available.")
            return redirect("directory:student-requests")

        item = get_object_or_404(definition["model"], pk=request.POST.get("object_id"))
        form = ServiceRequestReplyForm(
            _request_status_choices(kind, item), request.POST
        )
        if form.is_valid():
            message = form.cleaned_data["message"].strip()
            if not message:
                form.add_error("message", "Write a reply before saving.")
            else:
                status = form.cleaned_data["status"]
                with transaction.atomic():
                    if kind == "correction":
                        if status == "approved":
                            allowed = dict(CorrectionRequestFieldChoices())
                            if item.field_name not in allowed:
                                messages.error(
                                    request,
                                    "That field is not allowed for self-service correction.",
                                )
                                return redirect("directory:student-requests")
                            setattr(item.alumnus, item.field_name, item.proposed_value)
                            item.alumnus.save(
                                update_fields=[item.field_name, "date_modified"]
                            )
                        item.reviewer = request.user
                        item.reviewed_at = (
                            timezone.now()
                            if status in ("approved", "rejected")
                            else None
                        )
                        item.reviewer_note = message
                        item.status = status
                        item.save()
                    else:
                        item.status = status
                        item.reviewed_by = request.user
                        item.reviewed_at = timezone.now()
                        item.save(update_fields=["status", "reviewed_by", "reviewed_at"])

                    ServiceRequestReply.objects.create(
                        content_type=ContentType.objects.get_for_model(item),
                        object_id=item.pk,
                        author=request.user,
                        message=message,
                    )
                    requester = getattr(item, definition["requester_field"], None)
                    notify_user(
                        requester,
                        "service_request",
                        f"{definition['label']} updated",
                        message,
                        reverse(definition["url"]),
                    )
                    log_department_action(
                        request,
                        "student_service_reply",
                        {"kind": kind, "request_id": item.pk, "status": status},
                    )
                messages.success(request, "The student request was updated and replied to.")
                return redirect("directory:student-requests")

        messages.error(request, "Please choose a decision and write a reply.")

    status_filter = request.GET.get("status", "pending")
    if status_filter not in {"pending", "active", "replied", "all"}:
        status_filter = "pending"
    return render(
        request,
        "directory/student_requests.html",
        {
            "entries": _request_entries(status_filter),
            "status_filter": status_filter,
            "status_filters": (
                ("pending", "Pending"),
                ("active", "Active"),
                ("replied", "Replied"),
                ("all", "All requests"),
            ),
            "app_alumnus": getattr(request.user, "alumnus_profile", None),
            "nav_active": "report",
        },
    )


@department_data_editor_required
def community_moderation(request):
    pending_jobs = JobPosting.objects.filter(status="pending").select_related("posted_by")
    pending_events = AlumniEvent.objects.filter(status="pending").select_related("organizer")
    if request.method == "POST":
        kind = request.POST.get("kind")
        object_id = request.POST.get("object_id")
        status = request.POST.get("status")
        if kind == "job":
            item = get_object_or_404(JobPosting, pk=object_id, status="pending")
            choices = {"published", "rejected", "closed"}
        elif kind == "event":
            item = get_object_or_404(AlumniEvent, pk=object_id, status="pending")
            choices = {"published", "rejected", "cancelled"}
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
            "pending_events": pending_events,
            "app_alumnus": getattr(request.user, "alumnus_profile", None),
            "nav_active": "report",
        },
    )
