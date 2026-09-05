"""
Django settings for alumni_tracker project.

A campus-wide Alumni Tracking System for IOE Pulchowk Campus. Alumni sign in
securely (email/password with verification, or Google) and everyone can search
the alumni directory by name, batch, field of study, current city, employer,
and country.
"""

from pathlib import Path
import os

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Load environment variables from a local .env file if present.
load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


# --- Core -------------------------------------------------------------------
SECRET_KEY = os.environ.get(
    "SECRET_KEY", "django-insecure-dev-key-change-me-in-production-000000000000"
)
DEBUG = env_bool("DEBUG", True)
_configured_hosts = [h.strip() for h in os.environ.get("ALLOWED_HOSTS", "").split(",") if h.strip()]
if DEBUG and not _configured_hosts:
    _configured_hosts = ["*"]
RENDER_EXTERNAL_HOSTNAME = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "").strip()
if RENDER_EXTERNAL_HOSTNAME and RENDER_EXTERNAL_HOSTNAME not in _configured_hosts:
    _configured_hosts.append(RENDER_EXTERNAL_HOSTNAME)
ALLOWED_HOSTS = _configured_hosts
CSRF_TRUSTED_ORIGINS = [
    o for o in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if o
]


# --- Applications -----------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "django.contrib.humanize",
    # Third party
    "django_filters",
    "django_countries",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    # Local
    "directory",
    "accounts",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "directory.middleware.DepartmentOnlyAccessMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "directory.middleware.ActivityMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "alumni_tracker.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "directory.context_processors.department_access",
            ],
        },
    },
]

WSGI_APPLICATION = "alumni_tracker.wsgi.application"


# --- Database ---------------------------------------------------------------
# Defaults to SQLite for easy local development. Set DATABASE_URL (e.g. a
# Postgres URL) to override, matching the production data sources.
DATABASES = {
    "default": dj_database_url.config(
        default=os.environ.get("DATABASE_URL", f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
        conn_max_age=600,
    )
}


# --- Password validation ----------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
    {"NAME": "accounts.validators.PasswordComplexityValidator"},
]


# --- Internationalization ---------------------------------------------------
LANGUAGE_CODE = "en-us"
LANGUAGES = (("en", "English"), ("ne", "नेपाली"))
TIME_ZONE = "Asia/Kathmandu"
USE_I18N = True
USE_TZ = True


# --- Static & media ---------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "alumni_tracker.storage.ForgivingManifestStaticFilesStorage"},
}
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# --- Authentication (django-allauth) ----------------------------------------
SITE_ID = 1
AUTHENTICATION_BACKENDS = [
    "accounts.authentication.RollNumberBackend",
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

LOGIN_REDIRECT_URL = "/me/"
LOGOUT_REDIRECT_URL = "/"
LOGIN_URL = "/accounts/login/"

# Roll number/password sign-in. The email address remains the account's recovery
# email and is used by django-allauth's password-reset flow.
ACCOUNT_AUTHENTICATION_METHOD = "email"
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_FORMS = {
    "login": "accounts.forms.RollNumberLoginForm",
    "reset_password": "accounts.forms.RollNumberPasswordResetForm",
}
ACCOUNT_EMAIL_VERIFICATION = os.environ.get("ACCOUNT_EMAIL_VERIFICATION", "optional")
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_SESSION_REMEMBER = True
# Throttle brute-force login attempts (the case study asked for this).
ACCOUNT_RATE_LIMITS = {"login_failed": "5/5m"}

# --- Department report access -----------------------------------------------
# The aggregate report is restricted to department staff. Grant access by
# listing exact addresses, by trusting a whole email domain, or by adding the
# account to the Django group named below (manageable from the admin).
DEPARTMENT_EMAILS = [
    e.strip().lower()
    for e in os.environ.get("DEPARTMENT_EMAILS", "").split(",")
    if e.strip()
]
DEPARTMENT_EMAIL_DOMAINS = [
    d.strip().lower().lstrip("@")
    for d in os.environ.get(
        "DEPARTMENT_EMAIL_DOMAINS", ""
    ).split(",")
    if d.strip()
]
DEPARTMENT_GROUP_NAME = os.environ.get("DEPARTMENT_GROUP_NAME", "Department Staff")
DEPARTMENT_DATA_EDITOR_GROUP = os.environ.get(
    "DEPARTMENT_DATA_EDITOR_GROUP", "Alumni Data Editors"
)
DEPARTMENT_ADMIN_GROUP = os.environ.get(
    "DEPARTMENT_ADMIN_GROUP", "Alumni Administrators"
)

# Department reports contain campus-wide aggregate information, including
# unclaimed and private records. Keep a separate audit trail for report views
# and aggregate exports.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "department_audit_file": {
            "class": "logging.FileHandler",
            "filename": str(LOG_DIR / "department_audit.log"),
            "formatter": "department_audit",
            "level": "INFO",
        },
    },
    "formatters": {
        "department_audit": {
            "format": "{asctime} {levelname} {message}",
            "style": "{",
        },
    },
    "loggers": {
        "directory.audit": {
            "handlers": ["department_audit_file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}


GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
SOCIALACCOUNT_PROVIDERS = {}
if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET:
    SOCIALACCOUNT_PROVIDERS["google"] = {
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
        "APP": {
            "client_id": GOOGLE_CLIENT_ID,
            "secret": GOOGLE_CLIENT_SECRET,
            "key": "",
        },
    }
SOCIALACCOUNT_ADAPTER = "accounts.adapters.RegisteredAlumniSocialAccountAdapter"
SOCIALACCOUNT_LOGIN_ON_GET = True
# Google is an identity provider with verified email addresses. When it is
# configured, allow a verified Google email to sign in to the matching existing
# account and connect the provider automatically.
SOCIALACCOUNT_EMAIL_AUTHENTICATION = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = SOCIALACCOUNT_EMAIL_AUTHENTICATION

# Email delivery: choose `resend` or `smtp` explicitly. Without a provider,
# existing SMTP deployments continue to work when EMAIL_ENABLED is true; local
# development otherwise uses console output.
EMAIL_PROVIDER = os.environ.get("EMAIL_PROVIDER", "").strip().lower()
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
if EMAIL_PROVIDER == "resend":
    EMAIL_BACKEND = "alumni_tracker.email_backend.ResendEmailBackend"
    DEFAULT_FROM_EMAIL = os.environ.get(
        "DEFAULT_FROM_EMAIL", "onboarding@resend.dev"
    ) or "onboarding@resend.dev"
elif EMAIL_PROVIDER == "smtp" or (not EMAIL_PROVIDER and env_bool("EMAIL_ENABLED", False)):
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
    EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
    EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
    EMAIL_TIMEOUT = int(os.environ.get("EMAIL_TIMEOUT", "10"))
    EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
    # Google displays App Passwords in four groups separated by spaces. SMTP
    # expects the underlying 16-character value, so accept either form.
    EMAIL_HOST_PASSWORD = "".join(os.environ.get("EMAIL_HOST_PASSWORD", "").split())
    DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER)
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"


# --- Security (enabled when DEBUG is off) -----------------------------------
if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    CSRF_COOKIE_SAMESITE = "Lax"
    SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", str(60 * 60 * 24 * 365)))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", True)
    SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", False)
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
    X_FRAME_OPTIONS = "DENY"
