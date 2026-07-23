from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render

from .filters import AlumnusFilter
from .models import Alumnus


def home(request):
    """Landing page with headline stats about the alumni network."""
    qs = Alumnus.objects.all()
    stats = {
        "total": qs.count(),
        "batches": qs.exclude(batch="").values("batch").distinct().count(),
        "countries": qs.exclude(current_country="").values("current_country").distinct().count(),
        "employers": qs.exclude(employer_organization="").values("employer_organization").distinct().count(),
    }
    top_employers = (
        qs.exclude(employer_organization="")
        .values("employer_organization")
        .annotate(n=Count("id"))
        .order_by("-n")[:6]
    )
    return render(request, "directory/home.html", {"stats": stats, "top_employers": top_employers})


def alumni_list(request):
    """Public alumni directory with the six search filters."""
    base_qs = Alumnus.objects.filter(is_public=True)
    alumni_filter = AlumnusFilter(request.GET, queryset=base_qs)

    paginator = Paginator(alumni_filter.qs, 24)
    page = paginator.get_page(request.GET.get("page"))

    # Preserve active filters across pagination links.
    querystring = request.GET.copy()
    querystring.pop("page", None)

    context = {
        "filter": alumni_filter,
        "page_obj": page,
        "total_results": paginator.count,
        "querystring": querystring.urlencode(),
        "has_query": bool(querystring),
    }
    return render(request, "directory/alumni_list.html", context)


def alumnus_detail(request, pk):
    alumnus = get_object_or_404(Alumnus, pk=pk, is_public=True)
    return render(request, "directory/alumnus_detail.html", {"alumnus": alumnus})


@login_required
def my_profile(request):
    """Show the signed-in user's linked alumnus record, if any."""
    alumnus = getattr(request.user, "alumnus_profile", None)
    return render(request, "directory/my_profile.html", {"alumnus": alumnus})
