"""Small read-only JSON API authenticated by personal bearer tokens."""

import hashlib

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

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
            "batch": alumnus.batch if alumnus else "",
            "program": alumnus.field_of_study if alumnus else "",
        },
    })


@require_GET
def api_alumni(request):
    token = _token_from_request(request)
    if not token:
        return _unauthorized()
    records = Alumnus.objects.filter(is_public=True)
    if request.GET.get("q"):
        query = request.GET["q"].strip()
        records = records.filter(first_name__icontains=query) | records.filter(last_name__icontains=query)
    if request.GET.get("batch"):
        records = records.filter(batch=request.GET["batch"])
    if request.GET.get("program"):
        records = records.filter(field_of_study=request.GET["program"])
    data = [
        {
            "id": record.pk,
            "name": record.full_name,
            "batch": record.batch,
            "program": record.field_of_study,
            "city": record.current_city,
            "country": str(record.current_country),
            "profile_url": record.get_absolute_url(),
        }
        for record in records.order_by("batch", "last_name", "first_name")[:100]
    ]
    return JsonResponse({"count": len(data), "results": data})
