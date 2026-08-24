"""User-level features added around the existing alumni directory."""

import hashlib
import io
import secrets
from datetime import timedelta
from urllib.parse import parse_qs

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .community_forms import (
    ApiTokenForm,
    CommunityGroupForm,
    ConflictReviewForm,
    GroupPostForm,
    ResourceForm,
    SavedSearchForm,
    SecurityCodeForm,
    SkillForm,
    StoryForm,
)
from .models import (
    AlumniFavorite,
    AlumniSkill,
    AlumniStory,
    Alumnus,
    ApiToken,
    CommunityGroup,
    DataConflict,
    GroupMembership,
    GroupPost,
    Notification,
    Resource,
    SavedSearch,
    Skill,
    SkillEndorsement,
    Survey,
    SurveyResponse,
    TwoFactorCode,
    TwoFactorSetting,
)
from .notifications import notify_user
from .permissions import department_data_editor_required
from .student_views import _shell_context, _student_alumnus


def _student_or_claim(request):
    alumnus = _student_alumnus(request)
    if alumnus is None:
        return None, redirect("accounts:claim-record")
    return alumnus, None


@login_required
def notification_list(request):
    if request.method == "POST":
        Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
        messages.success(request, "All notifications marked as read.")
        return redirect("directory:notifications")
    notifications = Notification.objects.filter(recipient=request.user)[:100]
    return render(request, "directory/notifications.html", _shell_context(
        request,
        notifications=notifications,
        unread_count=Notification.objects.filter(recipient=request.user, is_read=False).count(),
    ))


@login_required
@require_POST
def notification_read(request, notification_id):
    notification = get_object_or_404(Notification, pk=notification_id, recipient=request.user)
    notification.is_read = True
    notification.save(update_fields=["is_read"])
    return redirect(notification.url or "directory:notifications")


@login_required
def saved_searches(request):
    if request.method == "POST":
        form = SavedSearchForm(request.POST)
        if form.is_valid():
            params = {
                key: values[-1]
                for key, values in parse_qs(form.cleaned_data["query"], keep_blank_values=True).items()
            }
            SavedSearch.objects.create(user=request.user, name=form.cleaned_data["name"], query_params=params)
            messages.success(request, "Saved search created.")
            return redirect("directory:saved-searches")
    else:
        form = SavedSearchForm()
    searches = SavedSearch.objects.filter(user=request.user)
    for search in searches:
        search.query_string = "&".join(f"{key}={value}" for key, value in search.query_params.items())
        search.use_url = f"{reverse('directory:alumni-list')}?{search.query_string}" if search.query_string else reverse("directory:alumni-list")
    return render(request, "directory/saved_searches.html", _shell_context(request, form=form, searches=searches))


@login_required
@require_POST
def saved_search_delete(request, search_id):
    SavedSearch.objects.filter(pk=search_id, user=request.user).delete()
    messages.success(request, "Saved search removed.")
    return redirect("directory:saved-searches")


@login_required
def favorite_list(request):
    alumnus, response = _student_or_claim(request)
    if response:
        return response
    favorites = AlumniFavorite.objects.filter(user=request.user).select_related("alumnus")
    return render(request, "directory/favorites.html", _shell_context(request, alumnus=alumnus, favorites=favorites))


@login_required
@require_POST
def favorite_toggle(request, alumnus_id):
    alumnus = get_object_or_404(Alumnus, pk=alumnus_id, is_public=True)
    favorite, created = AlumniFavorite.objects.get_or_create(user=request.user, alumnus=alumnus)
    if not created:
        favorite.delete()
        messages.info(request, "Alumnus removed from favorites.")
    else:
        messages.success(request, "Alumnus saved to favorites.")
    return redirect(request.POST.get("next") or "directory:favorites")


def _batch_group(alumnus, request):
    if not alumnus.batch:
        return None
    program = alumnus.get_field_of_study_display() if alumnus.field_of_study else ""
    slug = f"batch-{alumnus.batch}-{(alumnus.field_of_study or 'all').lower()}"
    group, _created = CommunityGroup.objects.get_or_create(
        slug=slug,
        defaults={
            "name": f"Batch {alumnus.batch} {program}".strip(),
            "description": "A space for classmates to share updates and opportunities.",
            "batch": alumnus.batch,
            "program": alumnus.field_of_study,
            "created_by": request.user,
            "is_public": True,
        },
    )
    return group


@login_required
def community_groups(request):
    alumnus, response = _student_or_claim(request)
    if response:
        return response
    _batch_group(alumnus, request)
    groups = CommunityGroup.objects.filter(is_public=True).annotate(member_count=Count("memberships"))
    mine = set(GroupMembership.objects.filter(user=request.user).values_list("group_id", flat=True))
    return render(request, "directory/community_groups.html", _shell_context(
        request, alumnus=alumnus, groups=groups, mine=mine, form=CommunityGroupForm()
    ))


@login_required
def community_group_create(request):
    if request.method != "POST":
        return redirect("directory:community-groups")
    form = CommunityGroupForm(request.POST)
    if form.is_valid():
        group = form.save(commit=False)
        group.created_by = request.user
        group.slug = f"{secrets.token_hex(4)}-{group.name.lower().replace(' ', '-')[:100]}"
        group.save()
        GroupMembership.objects.create(group=group, user=request.user, role="moderator")
        messages.success(request, "Community group created.")
        return redirect("directory:community-group", slug=group.slug)
    return redirect("directory:community-groups")


@login_required
def community_group(request, slug):
    alumnus, response = _student_or_claim(request)
    if response:
        return response
    group = get_object_or_404(CommunityGroup, slug=slug)
    membership = GroupMembership.objects.filter(group=group, user=request.user).first()
    if not group.is_public and not membership:
        messages.error(request, "This group is restricted to members.")
        return redirect("directory:community-groups")
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "join":
            GroupMembership.objects.get_or_create(group=group, user=request.user)
            messages.success(request, "You joined the group.")
        elif action == "leave":
            GroupMembership.objects.filter(group=group, user=request.user).delete()
            messages.info(request, "You left the group.")
        return redirect("directory:community-group", slug=slug)
    posts = group.posts.filter(is_hidden=False).select_related("author")[:100]
    return render(request, "directory/community_group.html", _shell_context(
        request, alumnus=alumnus, group=group, membership=membership, posts=posts, form=GroupPostForm()
    ))


@login_required
@require_POST
def community_group_post(request, slug):
    group = get_object_or_404(CommunityGroup, slug=slug)
    if not GroupMembership.objects.filter(group=group, user=request.user).exists():
        messages.error(request, "Join this group before posting.")
        return redirect("directory:community-group", slug=slug)
    form = GroupPostForm(request.POST)
    if form.is_valid():
        post = form.save(commit=False)
        post.group, post.author = group, request.user
        post.save()
        for member in GroupMembership.objects.filter(group=group).exclude(user=request.user).select_related("user")[:100]:
            notify_user(member.user, "group_post", f"New post in {group.name}", "A group member shared a new update.", reverse("directory:community-group", args=[group.slug]))
        messages.success(request, "Your group post was published.")
    return redirect("directory:community-group", slug=slug)


@login_required
def stories(request):
    alumnus, response = _student_or_claim(request)
    if response:
        return response
    published = AlumniStory.objects.filter(status="published").select_related("author")
    mine = AlumniStory.objects.filter(author=request.user)
    return render(request, "directory/stories.html", _shell_context(request, alumnus=alumnus, stories=published, mine=mine))


@login_required
def story_submit(request):
    alumnus, response = _student_or_claim(request)
    if response:
        return response
    form = StoryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        story = form.save(commit=False)
        story.author = request.user
        story.save()
        messages.success(request, "Your story was submitted for review.")
        return redirect("directory:stories")
    return render(request, "directory/story_submit.html", _shell_context(request, alumnus=alumnus, form=form))


@login_required
def skills(request):
    alumnus, response = _student_or_claim(request)
    if response:
        return response
    form = SkillForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        skill, _created = Skill.objects.get_or_create(name=form.cleaned_data["name"].strip())
        AlumniSkill.objects.update_or_create(
            alumnus=alumnus, skill=skill, defaults={"level": form.cleaned_data["level"]}
        )
        messages.success(request, "Skill added to your profile.")
        return redirect("directory:skills")
    own_skills = AlumniSkill.objects.filter(alumnus=alumnus).annotate(endorsement_count=Count("endorsements")).select_related("skill")
    available = AlumniSkill.objects.exclude(alumnus=alumnus).filter(alumnus__is_public=True).annotate(endorsement_count=Count("endorsements")).select_related("alumnus", "skill")[:80]
    return render(request, "directory/skills.html", _shell_context(request, alumnus=alumnus, form=form, own_skills=own_skills, available=available))


@login_required
@require_POST
def endorse_skill(request, skill_id):
    alumnus, response = _student_or_claim(request)
    if response:
        return response
    alumni_skill = get_object_or_404(AlumniSkill, pk=skill_id, alumnus__is_public=True)
    if alumni_skill.alumnus_id == alumnus.id:
        messages.error(request, "You cannot endorse your own skill.")
    else:
        endorsement, created = SkillEndorsement.objects.get_or_create(alumni_skill=alumni_skill, endorser=request.user)
        if not created:
            endorsement.delete()
            messages.info(request, "Endorsement removed.")
        else:
            messages.success(request, "Skill endorsed.")
    return redirect("directory:skills")


def _survey_form(survey, data=None):
    form = forms.Form(data=data)
    for question in survey.questions or []:
        key = str(question.get("key", "question"))
        field = forms.CharField(required=question.get("required", False))
        if question.get("type") == "choice":
            field = forms.ChoiceField(
                choices=[(str(choice), str(choice)) for choice in question.get("choices", [])],
                required=question.get("required", False),
            )
        elif question.get("type") == "textarea":
            field = forms.CharField(widget=forms.Textarea(attrs={"rows": 4}), required=question.get("required", False))
        field.label = question.get("label", key)
        form.fields[key] = field
    return form


@login_required
def surveys(request):
    alumnus, response = _student_or_claim(request)
    if response:
        return response
    survey_list = Survey.objects.filter(status="published")
    completed = set(SurveyResponse.objects.filter(respondent=request.user).values_list("survey_id", flat=True))
    return render(request, "directory/surveys.html", _shell_context(request, alumnus=alumnus, surveys=survey_list, completed=completed))


@login_required
def survey_detail(request, survey_id):
    alumnus, response = _student_or_claim(request)
    if response:
        return response
    survey = get_object_or_404(Survey, pk=survey_id, status="published")
    form = _survey_form(survey, request.POST or None)
    if request.method == "POST" and form.is_valid():
        SurveyResponse.objects.update_or_create(survey=survey, respondent=request.user, defaults={"answers": form.cleaned_data})
        messages.success(request, "Thank you for your feedback.")
        return redirect("directory:surveys")
    return render(request, "directory/survey_detail.html", _shell_context(request, alumnus=alumnus, survey=survey, form=form))


@login_required
def resources(request):
    alumnus, response = _student_or_claim(request)
    if response:
        return response
    items = Resource.objects.filter(status="published")
    return render(request, "directory/resources.html", _shell_context(request, alumnus=alumnus, resources=items))


@login_required
def resource_submit(request):
    alumnus, response = _student_or_claim(request)
    if response:
        return response
    form = ResourceForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.submitted_by = request.user
        item.save()
        messages.success(request, "Resource submitted for review.")
        return redirect("directory:resources")
    return render(request, "directory/resource_submit.html", _shell_context(request, alumnus=alumnus, form=form))


@login_required
def recommendations(request):
    alumnus, response = _student_or_claim(request)
    if response:
        return response
    matches = Alumnus.objects.filter(is_public=True).exclude(pk=alumnus.pk)
    if alumnus.field_of_study:
        matches = matches.filter(field_of_study=alumnus.field_of_study)
    recommendations_list = list(matches.select_related("user_account")[:12])
    if len(recommendations_list) < 12:
        existing = [item.pk for item in recommendations_list]
        extra = Alumnus.objects.filter(is_public=True).exclude(pk=alumnus.pk).exclude(pk__in=existing)[:12 - len(recommendations_list)]
        recommendations_list.extend(extra)
    return render(request, "directory/recommendations.html", _shell_context(request, alumnus=alumnus, recommendations=recommendations_list))


@login_required
def resume_pdf(request):
    alumnus, response = _student_or_claim(request)
    if response:
        return response
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except ImportError:
        return HttpResponse("PDF support is not installed. Install the reportlab dependency.", status=503)
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 58
    pdf.setTitle(f"Alumni profile - {alumnus.full_name}")
    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawString(48, y, alumnus.full_name)
    y -= 24
    pdf.setFont("Helvetica", 10)
    subtitle = " · ".join(value for value in [alumnus.get_field_of_study_display(), alumnus.batch, alumnus.job_title] if value)
    pdf.drawString(48, y, subtitle)
    y -= 34
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(48, y, "Contact and location")
    y -= 18
    pdf.setFont("Helvetica", 10)
    location = " · ".join(v for v in [alumnus.current_city, alumnus.current_country.name] if v)
    for label, value in [("Email", alumnus.email), ("Phone", alumnus.contact_number), ("Location", location), ("Employer", alumnus.employer_organization)]:
        if value:
            pdf.drawString(58, y, f"{label}: {value}")
            y -= 16
    y -= 12
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(48, y, "Skills")
    y -= 18
    pdf.setFont("Helvetica", 10)
    skill_items = AlumniSkill.objects.filter(alumnus=alumnus).select_related("skill")
    pdf.drawString(58, y, ", ".join(f"{item.skill.name} ({item.get_level_display()})" for item in skill_items) or "No skills added yet")
    y -= 30
    pdf.setFont("Helvetica", 8)
    pdf.drawString(48, y, "Generated from the DOECE Alumni Tracker")
    pdf.save()
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="alumni-profile-{alumnus.pk}.pdf"'
    return response


@login_required
def activity_history(request):
    return render(request, "directory/activity_history.html", _shell_context(
        request, activities=request.user.activity_logs.all()[:100]
    ))


def _token_hash(raw):
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@login_required
def api_tokens(request):
    raw_token = None
    form = ApiTokenForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        raw_token = secrets.token_urlsafe(32)
        ApiToken.objects.create(user=request.user, name=form.cleaned_data["name"], token_hash=_token_hash(raw_token))
        messages.success(request, "API token created. Copy it now; it will not be shown again.")
    tokens = ApiToken.objects.filter(user=request.user, revoked_at__isnull=True)
    return render(request, "directory/api_tokens.html", _shell_context(request, form=form, tokens=tokens, raw_token=raw_token))


@login_required
@require_POST
def api_token_revoke(request, token_id):
    token = get_object_or_404(ApiToken, pk=token_id, user=request.user, revoked_at__isnull=True)
    token.revoked_at = timezone.now()
    token.save(update_fields=["revoked_at"])
    messages.success(request, "API token revoked.")
    return redirect("directory:api-tokens")


@login_required
def security(request):
    setting, _created = TwoFactorSetting.objects.get_or_create(user=request.user)
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "send_code":
            code = f"{secrets.randbelow(1000000):06d}"
            TwoFactorCode.objects.filter(user=request.user, purpose="enrollment", used_at__isnull=True).update(used_at=timezone.now())
            TwoFactorCode.objects.create(user=request.user, purpose="enrollment", code_hash=_token_hash(code), expires_at=timezone.now() + timedelta(minutes=10))
            send_mail("DOECE Alumni Tracker verification code", f"Your verification code is {code}. It expires in 10 minutes.", None, [request.user.email])
            messages.info(request, "A verification code was sent to your account email.")
        elif action == "verify":
            form = SecurityCodeForm(request.POST)
            code_record = TwoFactorCode.objects.filter(user=request.user, purpose="enrollment", used_at__isnull=True, expires_at__gte=timezone.now()).first()
            if form.is_valid() and code_record and secrets.compare_digest(code_record.code_hash, _token_hash(form.cleaned_data["code"])):
                code_record.used_at = timezone.now()
                code_record.save(update_fields=["used_at"])
                setting.enabled = True
                setting.save(update_fields=["enabled", "updated_at"])
                messages.success(request, "Email two-step verification is enabled.")
            else:
                messages.error(request, "That verification code is invalid or expired.")
        elif action == "disable":
            setting.enabled = False
            setting.save(update_fields=["enabled", "updated_at"])
            messages.info(request, "Two-step verification disabled.")
        return redirect("directory:security")
    return render(request, "directory/security.html", _shell_context(request, setting=setting, code_form=SecurityCodeForm()))


@department_data_editor_required
def data_conflicts(request):
    conflicts = DataConflict.objects.select_related("record_a", "record_b", "resolved_by")
    if request.method == "POST":
        conflict = get_object_or_404(DataConflict, pk=request.POST.get("conflict_id"), status="open")
        form = ConflictReviewForm(request.POST)
        if form.is_valid():
            conflict.status = form.cleaned_data["status"]
            conflict.resolution_note = form.cleaned_data["resolution_note"]
            conflict.resolved_by = request.user
            conflict.resolved_at = timezone.now()
            conflict.save()
            messages.success(request, "Conflict status updated.")
            return redirect("directory:data-conflicts")
    return render(request, "directory/data_conflicts.html", {
        "conflicts": conflicts[:200],
        "review_form": ConflictReviewForm(),
        "app_alumnus": getattr(request.user, "alumnus_profile", None),
        "nav_active": "report",
    })


@department_data_editor_required
def community_content_moderation(request):
    if request.method == "POST":
        kind = request.POST.get("kind")
        model = {"story": AlumniStory, "resource": Resource}.get(kind)
        item = get_object_or_404(model, pk=request.POST.get("object_id"), status="pending") if model else None
        if item and request.POST.get("status") in {"published", "rejected"}:
            item.status = request.POST["status"]
            item.reviewed_by = request.user
            item.reviewed_at = timezone.now()
            item.save(update_fields=["status", "reviewed_by", "reviewed_at"])
            messages.success(request, "Content moderation action saved.")
            return redirect("directory:content-moderation")
        messages.error(request, "Invalid moderation action.")
    return render(request, "directory/content_moderation.html", {
        "stories": AlumniStory.objects.filter(status="pending").select_related("author"),
        "resources": Resource.objects.filter(status="pending").select_related("submitted_by"),
        "app_alumnus": getattr(request.user, "alumnus_profile", None),
        "nav_active": "report",
    })
