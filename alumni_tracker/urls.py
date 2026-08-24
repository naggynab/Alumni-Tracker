from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from accounts.views import RollNumberPasswordResetView, SecureLoginView, login_2fa
from directory import api_views
from directory import import_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path(
        "accounts/password/reset/",
        RollNumberPasswordResetView.as_view(),
        name="account_reset_password",
    ),
    path("accounts/login/", SecureLoginView.as_view(), name="account_login"),
    path("accounts/login/2fa/", login_2fa, name="account_login_2fa"),
    path("accounts/", include("allauth.urls")),
    path("i18n/", include("django.conf.urls.i18n")),
    path("api/v1/me/", api_views.api_me, name="api-me"),
    path("api/v1/alumni/", api_views.api_alumni, name="api-alumni"),
    path(
        "internal/alumni-import/form/",
        import_views.alumni_import_form,
        name="alumni-import-form",
    ),
    path("internal/alumni-import/", import_views.alumni_import, name="alumni-import"),
    path(
        "internal/alumni-import/status/",
        import_views.alumni_import_status,
        name="alumni-import-status",
    ),
    path("", include("directory.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
