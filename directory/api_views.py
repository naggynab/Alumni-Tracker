"""Small read-only JSON API authenticated by personal bearer tokens."""

import hashlib

from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from .choices import batch_year_variants, normalize_city, normalize_institution
from .filters import get_filter_option_data
from .models import Alumnus, ApiToken


def _token_from_request(request):
    header = request.headers.get("Authorization", "")
    if not header.lower().startswith("bearer "):
        return None
    raw = header.split(" ", 1)[1].strip()
    if not raw:
        return None
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    token = ApiToken.objects.select_related("user").filter(
        token_hash=digest, revoked_at__isnull=True
    ).first()
    if token:
        token.last_used_at = timezone.now()
        token.save(update_fields=["last_used_at"])
    return token


def _unauthorized():
    response = JsonResponse({"detail": "Use a valid Authorization: Bearer <token> header."}, status=401)
    response["WWW-Authenticate"] = "Bearer"
    return response


@require_GET
def api_me(request):
    token = _token_from_request(request)
    if not token:
        return _unauthorized()
    alumnus = getattr(token.user, "alumnus_profile", None)
    return JsonResponse({
        "account": {"id": token.user.pk, "email": token.user.email},
        "profile": {
            "id": alumnus.pk if alumnus else None,
            "name": alumnus.full_name if alumnus else "",
            "first_name": alumnus.first_name if alumnus else "",
            "last_name": alumnus.last_name if alumnus else "",
            "batch": alumnus.batch if alumnus else "",
            "program": alumnus.field_of_study if alumnus else "",
            "program_display": alumnus.program_display if alumnus else "",
            "university": alumnus.further_study_institution if alumnus else "",
        },
    })


@require_GET
def api_alumni(request):
    token = _token_from_request(request)
    if not token:
        return _unauthorized()
    records = Alumnus.objects.filter(is_public=True)
    if request.GET.get("q"):
        for term in request.GET["q"].strip().split():
            records = records.filter(
                Q(first_name__icontains=term)
                | Q(middle_name__icontains=term)
                | Q(last_name__icontains=term)
                | Q(class_roll_no__icontains=term)
                | Q(roll_number_canonical__icontains=term)
            )
    if request.GET.get("batch"):
        records = records.filter(batch__in=batch_year_variants(request.GET["batch"]))
    if request.GET.get("program"):
        records = records.filter(field_of_study=request.GET["program"])
    if request.GET.get("country"):
        records = records.filter(current_country=request.GET["country"].strip())
    city = request.GET.get("city") or request.GET.get("current_city")
    if city:
        records = records.filter(
            Q(current_city_canonical=normalize_city(city))
            | Q(current_city__iexact=city.strip())
        )
    organization = request.GET.get("organization") or request.GET.get("employer")
    if organization:
        records = records.filter(
            employer_organization__icontains=organization.strip()
        )
    if request.GET.get("university"):
        university = request.GET["university"].strip()
        normalized_university = normalize_institution(university)
        option_data = get_filter_option_data(Alumnus.objects.filter(is_public=True))
        raw_values = option_data["university_raw_values"].get(normalized_university, ())
        records = records.filter(
            Q(further_study_institution_canonical=normalized_university)
            | Q(further_study_institution__in=raw_values)
        )
    data = [
        {
            "id": record.pk,
            "name": record.full_name,
            "first_name": record.first_name,
            "last_name": record.last_name,
            "batch": record.batch,
            "program": record.field_of_study,
            "program_display": record.program_display,
            "university": record.further_study_institution,
            "city": record.current_city,
            "country": str(record.current_country),
            "profile_url": record.get_absolute_url(),
        }
        for record in records.order_by("batch", "last_name", "first_name")[:100]
    ]
    return JsonResponse({"count": len(data), "results": data})
