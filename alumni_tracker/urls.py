from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from accounts.views import RollNumberPasswordResetView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path(
        "accounts/password/reset/",
        RollNumberPasswordResetView.as_view(),
        name="account_reset_password",
    ),
    path("accounts/", include("allauth.urls")),
    path("", include("directory.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
