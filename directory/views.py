from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from .filters import AlumnusFilter
from .models import Alumnus


def home(request):
    """Landing page: hero + inline 'Find Alumni' search form."""
    context = {
        "filter": AlumnusFilter(queryset=Alumnus.objects.filter(is_public=True)),
        "nav_active": "home",
    }
    return render(request, "directory/home.html", context)


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
    return render(request, "directory/alumnus_detail.html", {"alumnus": alumnus})


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
