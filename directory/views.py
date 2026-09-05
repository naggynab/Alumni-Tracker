import csv
import logging

from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.http import Http404, JsonResponse, StreamingHttpResponse
from django.views.decorators.http import require_GET
from django.utils import timezone
from django.shortcuts import get_object_or_404, render

from .filters import AlumnusFilter, get_filter_option_data
from .forms import ReportFilterForm
from .audit import log_department_action
from .models import AlumniFavorite, Alumnus, ClaimReview, FollowUp
from .permissions import (
    department_admin_required,
    department_data_editor_required,
    department_required,
)
from .profile import profile_completeness
from .stats import build_comparison, build_data_quality, build_report
from .workflow_forms import (
    ClaimReviewForm,
    ComparisonForm,
    DataQualityFilterForm,
    FollowUpForm,
)

User = get_user_model()
logger = logging.getLogger(__name__)


def home(request):
    """Landing page: hero + inline 'Find Alumni' search form."""
    context = {
        "filter": AlumnusFilter(queryset=Alumnus.objects.filter(is_public=True)),
        "nav_active": "home",
    }
    return render(request, "directory/home.html", context)


@require_GET
def alumni_filter_options(request):
    """Return public, database-backed options for the Find Alumni filters."""
    try:
        data = get_filter_option_data(Alumnus.objects.filter(is_public=True))
        country = (request.GET.get("country", "") or "").strip()
        payload = {
            "countries": [
                {"value": value, "label": label}
                for value, label in data["countries"]
            ],
            "cities": [
                {"value": value, "label": label}
                for value, label in data["cities_by_country"].get(country, [])
            ],
            "universities": [
                {"value": value, "label": label}
                for value, label in data["universities"]
            ],
        }
        return JsonResponse(payload)
    except Exception:
        logger.exception("Unable to load alumni filter options")
        return JsonResponse(
            {"detail": "Unable to load alumni filter options."}, status=500
        )


def alumni_list(request):
    """The yearbook: search portal with the seven filters + results."""
    base_qs = Alumnus.objects.filter(is_public=True)
    alumni_filter = AlumnusFilter(request.GET, queryset=base_qs)

    paginator = Paginator(alumni_filter.qs, 24)
    page = paginator.get_page(request.GET.get("page"))

    querystring = request.GET.copy()
    querystring.pop("page", None)

    context = {
        "filter": alumni_filter,
        "page_obj": page,
        "total_results": paginator.count,
        "querystring": querystring.urlencode(),
        "has_query": bool(querystring),
        "nav_active": "yearbook",
        # Logged-in alumni see the sidebar shell; visitors see the public one.
        "base_template": "base_app.html" if request.user.is_authenticated else "base.html",
        "app_alumnus": getattr(request.user, "alumnus_profile", None),
    }
    return render(request, "directory/alumni_list.html", context)


def alumnus_detail(request, pk):
    alumnus = get_object_or_404(Alumnus, pk=pk, is_public=True)
    is_favorite = bool(
        request.user.is_authenticated
        and AlumniFavorite.objects.filter(user=request.user, alumnus=alumnus).exists()
    )
    return render(request, "directory/alumnus_detail.html", {"alumnus": alumnus, "is_favorite": is_favorite})


def _graduation_year(alumnus):
    """Derive a graduation year from the BS enrollment batch (enroll + 4)."""
    batch = (alumnus.batch or "").strip()
    if not batch.isdigit():
        return None
    year = int(batch)
    enrolled = 2000 + year if year < 100 else year
    return enrolled + 4


@login_required
def my_profile(request):
    """Show the signed-in user's linked alumnus record, if any."""
    alumnus = getattr(request.user, "alumnus_profile", None)
    context = {
        "alumnus": alumnus,
        "app_alumnus": alumnus,
        "grad_year": _graduation_year(alumnus) if alumnus else None,
        "nav_active": "profile",
    }
    return render(request, "directory/my_profile.html", context)


@login_required
def profile_completeness_page(request):
    """Show completeness guidance without changing the existing profile page."""
    alumnus = getattr(request.user, "alumnus_profile", None)
    context = {
        "alumnus": alumnus,
        "completeness": profile_completeness(alumnus) if alumnus else None,
        "app_alumnus": alumnus,
        "nav_active": "profile",
    }
    return render(request, "directory/profile_completeness.html", context)


@department_required
def department_report(request):
    """Aggregate alumni numbers for department staff.

    Unlike the public yearbook this counts every record, claimed or not, and
    ignores `is_public` — the department needs complete figures.
    """
    form, queryset = _report_selection(request)
    log_department_action(request, "report_view", request.GET)

    context = {
        "form": form,
        "report": build_report(queryset),
        "selection": form.summary(),
        "is_filtered": any(form.data.get(name) for name in form.fields),
        "campus_total": Alumnus.objects.count(),
        "app_alumnus": getattr(request.user, "alumnus_profile", None),
        "nav_active": "report",
    }
    return render(request, "directory/department_report.html", context)


@department_required
def department_data_quality(request):
    """Show missing-field, duplicate-key and follow-up indicators."""
    form = DataQualityFilterForm(request.GET)
    queryset = Alumnus.objects.all()
    if form.is_valid():
        if form.cleaned_data.get("scope") == "claimed":
            queryset = queryset.filter(user_account__isnull=False)
        elif form.cleaned_data.get("scope") == "unclaimed":
            queryset = queryset.filter(user_account__isnull=True)
    log_department_action(request, "data_quality_view", request.GET)
    return render(
        request,
        "directory/data_quality.html",
        {
            "form": form,
            "quality": build_data_quality(queryset),
            "app_alumnus": getattr(request.user, "alumnus_profile", None),
            "nav_active": "report",
        },
    )


@department_required
def department_report_compare(request):
    """Compare two cohorts using the same aggregate definitions as the report."""
    form = ComparisonForm(request.GET or None)
    comparison = None
    if form.is_valid():
        base = Alumnus.objects.all()
        if form.cleaned_data.get("field_of_study"):
            base = base.filter(field_of_study=form.cleaned_data["field_of_study"])
        queryset_a = base.filter(batch=form.cleaned_data["batch_a"])
        queryset_b = base.filter(batch=form.cleaned_data["batch_b"])
        comparison = build_comparison(
            queryset_a,
            queryset_b,
            label_a=f"Batch {form.cleaned_data['batch_a']}",
            label_b=f"Batch {form.cleaned_data['batch_b']}",
        )
    log_department_action(request, "report_compare_view", request.GET)
    return render(
        request,
        "directory/report_compare.html",
        {
            "form": form,
            "comparison": comparison,
            "app_alumnus": getattr(request.user, "alumnus_profile", None),
            "nav_active": "report",
        },
    )


@department_required
def follow_up_queue(request):
    """List open officer work items and likely records needing contact."""
    status = request.GET.get("status", "open")
    followups = FollowUp.objects.select_related("alumnus", "updated_by")
    if status in dict(FollowUp.STATUS_CHOICES):
        followups = followups.filter(status=status)
    else:
        status = "open"
        followups = followups.filter(status=status)
    candidates = (
        Alumnus.objects.filter(
            current_country="",
        )
        .filter(user_account__isnull=True)
        .exclude(follow_up__isnull=False)
        .order_by("batch", "last_name", "first_name")[:20]
    )
    log_department_action(request, "follow_up_queue_view", request.GET)
    return render(
        request,
        "directory/follow_up_queue.html",
        {
            "followups": followups[:100],
            "candidates": candidates,
            "status": status,
            "status_choices": FollowUp.STATUS_CHOICES,
            "app_alumnus": getattr(request.user, "alumnus_profile", None),
            "nav_active": "report",
        },
    )


@department_data_editor_required
def follow_up_create(request, alumnus_id):
    alumnus = get_object_or_404(Alumnus, pk=alumnus_id)
    followup, created = FollowUp.objects.get_or_create(
        alumnus=alumnus,
        defaults={"created_by": request.user, "reason": "Missing data"},
    )
    if created:
        log_department_action(request, "follow_up_create", {"alumnus_id": alumnus_id})
    return redirect("directory:follow-up-edit", pk=followup.pk)


@department_data_editor_required
def follow_up_edit(request, pk):
    followup = get_object_or_404(
        FollowUp.objects.select_related("alumnus"), pk=pk
    )
    if request.method == "POST":
        form = FollowUpForm(request.POST, instance=followup)
        if form.is_valid():
            followup = form.save(commit=False)
            followup.updated_by = request.user
            followup.save()
            log_department_action(
                request,
                "follow_up_update",
                {"follow_up_id": pk, "status": followup.status},
            )
            messages.success(request, "Follow-up saved.")
            return redirect("directory:follow-up-queue")
    else:
        form = FollowUpForm(instance=followup)
    return render(
        request,
        "directory/follow_up_edit.html",
        {
            "form": form,
            "followup": followup,
            "app_alumnus": getattr(request.user, "alumnus_profile", None),
            "nav_active": "report",
        },
    )


@department_required
def department_verification(request):
    status = request.GET.get("status", "pending")
    reviews = ClaimReview.objects.select_related("alumnus", "claimant", "reviewer")
    if status in dict(ClaimReview.STATUS_CHOICES):
        reviews = reviews.filter(status=status)
    else:
        status = "pending"
        reviews = reviews.filter(status=status)
    log_department_action(request, "verification_queue_view", request.GET)
    return render(
        request,
        "directory/verification_queue.html",
        {
            "reviews": reviews[:100],
            "status": status,
            "status_choices": ClaimReview.STATUS_CHOICES,
            "can_review": request.user.is_superuser
            or request.user.groups.filter(
                name__in={
                    settings.DEPARTMENT_DATA_EDITOR_GROUP,
                    settings.DEPARTMENT_ADMIN_GROUP,
                }
            ).exists(),
            "app_alumnus": getattr(request.user, "alumnus_profile", None),
            "nav_active": "report",
        },
    )


@department_data_editor_required
def department_verification_review(request, review_id):
    review = get_object_or_404(ClaimReview, pk=review_id)
    if request.method != "POST":
        return redirect("directory:department-verification")
    form = ClaimReviewForm(request.POST, instance=review)
    if form.is_valid():
        review = form.save(commit=False)
        review.reviewer = request.user if review.status != "pending" else None
        review.reviewed_at = timezone.now() if review.status != "pending" else None
        review.save()
        if review.status == "rejected" and review.alumnus.user_account_id == review.claimant_id:
            review.alumnus.user_account = None
            review.alumnus.save(update_fields=["user_account", "date_modified"])
        log_department_action(
            request,
            "claim_review_update",
            {"review_id": review_id, "status": review.status},
        )
        messages.success(request, "Claim review updated.")
    else:
        messages.error(request, "The claim review could not be saved.")
    return redirect("directory:department-verification")


@department_admin_required
def department_roles(request):
    """Small role-management screen; the same roles are also CLI-manageable."""
    role_groups = (
        ("report", settings.DEPARTMENT_GROUP_NAME, "View reports"),
        ("editor", settings.DEPARTMENT_DATA_EDITOR_GROUP, "Edit workflow records"),
        ("admin", settings.DEPARTMENT_ADMIN_GROUP, "Manage roles"),
    )
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        role = request.POST.get("role", "")
        action = request.POST.get("action", "add")
        group_name = dict((key, name) for key, name, _label in role_groups).get(role)
        user = User.objects.filter(email__iexact=email).first()
        if not group_name or not user or action not in {"add", "remove"}:
            messages.error(request, "Choose a valid role and existing user email.")
        else:
            group, _created = Group.objects.get_or_create(name=group_name)
            if action == "add":
                group.user_set.add(user)
            else:
                group.user_set.remove(user)
            log_department_action(
                request,
                f"role_{action}",
                {"email": email, "role": role},
            )
            messages.success(request, f"Role {action}ed for {email}.")
        return redirect("directory:department-roles")

    memberships = []
    for key, group_name, label in role_groups:
        group = Group.objects.filter(name=group_name).first()
        memberships.append(
            {
                "key": key,
                "name": group_name,
                "label": label,
                "users": list(group.user_set.order_by("email") if group else []),
            }
        )
    return render(
        request,
        "directory/department_roles.html",
        {
            "memberships": memberships,
            "app_alumnus": getattr(request.user, "alumnus_profile", None),
            "nav_active": "report",
        },
    )


class _CsvEcho:
    """File-like sink that lets csv.writer produce StreamingHttpResponse rows."""

    def write(self, value):
        return value


def _report_selection(request):
    form = ReportFilterForm(request.GET)
    queryset = Alumnus.objects.all()
    if form.is_valid():
        queryset = form.apply(queryset)
    return form, queryset


def _export_rows(report, breakdown):
    if breakdown == "full":
        rows = [("section", "label", "total", "share", "detail", "detail_share")]
        rows.append(("headline", "total alumni", report["total"], "", "", ""))
        rows.append(("headline", "registered accounts", report["registered"], "", "", ""))
        rows.append(("headline", "living in Nepal", report["in_nepal"], report["in_nepal_percent"], "", ""))
        rows.append(("headline", "living abroad", report["abroad"], report["abroad_percent"], "", ""))
        for section, key in (
            ("batches", "by_batch"),
            ("countries", "by_country"),
            ("cities", "by_city"),
            ("districts", "by_district"),
            ("programs", "by_field"),
            ("employment", "by_employment"),
            ("employers", "by_employer"),
            ("study countries", "by_study_country"),
            ("study institutions", "by_study_institution"),
        ):
            for row in report[key]:
                rows.append(
                    (
                        section,
                        row["label"],
                        row["total"],
                        row.get("share", ""),
                        row.get("abroad", ""),
                        row.get("abroad_share", ""),
                    )
                )
        for row in report["adoption"]:
            rows.append(("adoption", row["batch"], row["total"], row["claimed_share"], row["claimed"], row["unclaimed"]))
        for row in report["missing_data"]:
            rows.append(("missing data", row["label"], row["total"], row["share"], "", ""))
        return rows

    mapping = {
        "country": ("label", "total", "share"),
        "city": ("label", "total", "share"),
        "district": ("label", "total", "share"),
        "field": ("label", "total", "share", "in_nepal", "abroad", "unknown"),
        "employment": ("label", "total", "share"),
        "employer": ("label", "total", "share"),
        "study_country": ("label", "total", "share"),
        "study_institution": ("label", "total", "share"),
        "batch": ("label", "total", "abroad", "abroad_share"),
        "adoption": ("batch", "total", "claimed", "unclaimed", "claimed_share"),
        "missing_data": ("label", "total", "share"),
    }
    report_keys = {
        "country": "by_country",
        "city": "by_city",
        "district": "by_district",
        "field": "by_field",
        "employment": "by_employment",
        "employer": "by_employer",
        "study_country": "by_study_country",
        "study_institution": "by_study_institution",
        "batch": "by_batch",
        "adoption": "adoption",
        "missing_data": "missing_data",
    }
    if breakdown not in mapping:
        raise Http404("Unknown report export.")
    columns = mapping[breakdown]
    rows = [columns]
    for row in report[report_keys[breakdown]]:
        rows.append(tuple(row.get(column, "") for column in columns))
    return rows


@department_required
def department_report_export(request, breakdown):
    """Stream one aggregate report section as CSV to a department officer."""
    form, queryset = _report_selection(request)
    log_department_action(request, f"report_export:{breakdown}", request.GET)
    report = build_report(queryset)
    rows = _export_rows(report, breakdown)
    pseudo_buffer = _CsvEcho()
    writer = csv.writer(pseudo_buffer)
    response = StreamingHttpResponse(
        (writer.writerow(row) for row in rows),
        content_type="text/csv; charset=utf-8",
    )
    response["Content-Disposition"] = (
        f'attachment; filename="department-report-{breakdown}.csv"'
    )
    return response
