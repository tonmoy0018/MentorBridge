"""
Shared settings. Environment-specific modules (dev, test, prod) import from here.
All secrets and deployment values come from environment variables.
"""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parents[2]
env = environ.Env()

SECRET_KEY = env("DJANGO_SECRET_KEY", default="")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])

# The browser talks to Django through the Next.js proxy on the public origin, so CSRF's
# Origin check must trust that origin (e.g. http://localhost:3000).
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])
USE_X_FORWARDED_HOST = env.bool("DJANGO_USE_X_FORWARDED_HOST", default=False)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "rest_framework",
    "drf_spectacular",
    "corsheaders",
    "django_countries",
    "apps.common",
    "apps.users",
    "apps.taxonomy",
    "apps.mentors",
    "apps.students",
    "apps.bookings",
    "apps.payments",
    "apps.reviews",
    "apps.moderation",
    "apps.notifications",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "apps.common.middleware.RequestIDMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    },
    {
        # Plain-text emails: no HTML autoescaping (it would turn "&" in links into "&amp;").
        "NAME": "email_text",
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"autoescape": False},
    },
]

DATABASES = {
    "default": env.db(
        "DATABASE_URL", default="postgres://mentorbridge:mentorbridge@localhost:5433/mentorbridge"
    )
}
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DATABASE_CONN_MAX_AGE", default=60)
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "users.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
PASSWORD_RESET_TIMEOUT = env.int("PASSWORD_RESET_TIMEOUT_SECONDS", default=60 * 60)  # 1 hour
EMAIL_VERIFICATION_TIMEOUT = env.int("EMAIL_VERIFICATION_TIMEOUT_SECONDS", default=60 * 60 * 72)

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"  # all timestamps are stored and served in UTC
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
FILE_UPLOAD_MAX_MEMORY_SIZE = 2_621_440
DATA_UPLOAD_MAX_MEMORY_SIZE = 2_621_440

# Sessions + CSRF (see docs/ARCHITECTURE.md §4.2).
SESSION_COOKIE_AGE = env.int("SESSION_COOKIE_AGE_SECONDS", default=60 * 60 * 24 * 14)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=False)
CSRF_COOKIE_HTTPONLY = False  # the SPA reads it and echoes it in X-CSRFToken
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=False)

# CORS: the frontend is same-origin (Next.js proxies /api/*), so no cross-origin access is
# allowed by default. Add origins only for deliberate cross-origin clients.
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOW_CREDENTIALS = True
CORS_URLS_REGEX = r"^/api/.*$"

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"

# Throttling needs a cache shared by all worker processes: the database cache
# (run `manage.py createcachetable`).
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "django_cache",
    }
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["apps.common.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.StandardPagination",
    "PAGE_SIZE": 20,
    "EXCEPTION_HANDLER": "apps.common.exceptions.api_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "120/min",
        "user": "600/min",
        "auth_login": "10/min",
        "auth_login_email": "5/min",
        "auth_register": "5/hour",
        "password_reset": "5/hour",
        "password_reset_confirm": "10/hour",
        "password_change": "5/hour",
        "email_verify": "10/hour",
        "booking_create": "20/hour",
        "review_create": "20/hour",
        "report_create": "10/hour",
    },
    # Number of trusted reverse proxies in front of Django (Next.js / load balancer), used
    # to read the client IP from X-Forwarded-For for throttling.
    "NUM_PROXIES": env.int("NUM_PROXIES", default=1),
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "MentorBridge API",
    "DESCRIPTION": (
        "REST API for the MentorBridge mentorship marketplace. Authentication uses the Django "
        "session cookie; unsafe requests must send the `X-CSRFToken` header (obtain the cookie "
        "from `GET /api/v1/auth/csrf/`). Errors use the envelope "
        '`{"error": {"code", "message", "details"}}`.'
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": r"/api/v1",
    "POSTPROCESSING_HOOKS": [
        "drf_spectacular.hooks.postprocess_schema_enums",
        "apps.common.openapi.mark_response_fields_required",
    ],
    "ENUM_NAME_OVERRIDES": {
        "RoleEnum": "apps.users.models.Role",
        "BookingStatusEnum": "apps.bookings.models.BookingStatus",
        "VerificationStatusEnum": "apps.mentors.models.VerificationStatus",
        "VerificationRequestStatusEnum": "apps.mentors.models.VerificationRequestStatus",
        "AvailabilityExceptionStatusEnum": "apps.mentors.models.AvailabilityExceptionStatus",
        "PaymentStatusEnum": "apps.payments.models.PaymentStatus",
        "RefundStatusEnum": "apps.payments.models.RefundStatus",
        "RefundRecordStatusEnum": "apps.payments.models.RefundRecordStatus",
        "RefundReasonEnum": "apps.payments.models.RefundReason",
        "DisputeStatusEnum": "apps.payments.models.DisputeStatus",
        "PayoutStatusEnum": "apps.payments.models.PayoutStatus",
        "ReportStatusEnum": "apps.moderation.models.ReportStatus",
        "ReportReasonEnum": "apps.moderation.models.ReportReason",
        "ReportTargetTypeEnum": "apps.moderation.models.ReportTargetType",
        "GoalStatusEnum": "apps.students.models.GoalStatus",
        "ReviewStatusEnum": "apps.reviews.models.ReviewStatus",
    },
}

EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", default="localhost")
EMAIL_PORT = env.int("EMAIL_PORT", default=1025)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=False)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="MentorBridge <no-reply@mentorbridge.local>")

# Public origin of the web app, used to build links in emails.
FRONTEND_URL = env("FRONTEND_URL", default="http://localhost:3000").rstrip("/")
ADMIN_URL = env("DJANGO_ADMIN_URL", default="django-admin/")

# Marketplace rules (docs/PRODUCT_REQUIREMENTS.md §6).
PLATFORM_CURRENCY = env("PLATFORM_CURRENCY", default="USD")
PLATFORM_FEE_BPS = env.int("PLATFORM_FEE_BPS", default=1500)  # 15.00%
# How long a paid booking holds its slot while the student pays. Checkout sessions last at least
# CHECKOUT_MIN_MINUTES (Stripe's minimum is 30), and the hold is extended to match.
BOOKING_HOLD_MINUTES = env.int("BOOKING_HOLD_MINUTES", default=30)
CHECKOUT_MIN_MINUTES = 31
PAYMENT_WEBHOOK_GRACE_MINUTES = env.int("PAYMENT_WEBHOOK_GRACE_MINUTES", default=5)
# Unconfirmed bookings (held for payment or awaiting the mentor) a student may have at once,
# so one account can't block mentors' calendars.
MAX_PENDING_BOOKINGS_PER_STUDENT = env.int("MAX_PENDING_BOOKINGS_PER_STUDENT", default=5)
MAX_PENDING_BOOKINGS_PER_MENTOR_PAIR = env.int("MAX_PENDING_BOOKINGS_PER_MENTOR_PAIR", default=2)
# Card authorisations last about 7 days, so mentors must respond well within that.
MENTOR_RESPONSE_HOURS = env.int("MENTOR_RESPONSE_HOURS", default=48)
if not 1 <= MENTOR_RESPONSE_HOURS <= 120:
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured(
        "MENTOR_RESPONSE_HOURS must be between 1 and 120 (card authorisations expire)."
    )
FREE_CANCELLATION_HOURS = env.int("FREE_CANCELLATION_HOURS", default=24)
SLOT_STEP_MINUTES = env.int("SLOT_STEP_MINUTES", default=30)
AVAILABILITY_MAX_RANGE_DAYS = 31
REQUIRE_VERIFIED_EMAIL = env.bool("REQUIRE_VERIFIED_EMAIL", default=False)
# Online payments (docs/PAYMENTS.md). Empty PAYMENT_PROVIDER = payments off: paid sessions can't be
# booked (503 `payments_unavailable`) and free sessions work normally. "stripe" needs both keys;
# use test-mode keys (sk_test_…) for development. Payments made with test keys are never counted
# as revenue.
IMPLEMENTED_PAYMENT_PROVIDERS: frozenset[str] = frozenset({"stripe"})
PAYMENT_PROVIDER = env("PAYMENT_PROVIDER", default="")
STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY", default="")
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET", default="")
STRIPE_API_BASE = env("STRIPE_API_BASE", default="")  # tests only: point at stripe-mock
if PAYMENT_PROVIDER:
    from django.core.exceptions import ImproperlyConfigured

    if PAYMENT_PROVIDER not in IMPLEMENTED_PAYMENT_PROVIDERS:
        raise ImproperlyConfigured(f"PAYMENT_PROVIDER={PAYMENT_PROVIDER!r} is not implemented.")
    if PAYMENT_PROVIDER == "stripe" and not (
        STRIPE_SECRET_KEY.startswith(("sk_test_", "sk_live_", "rk_test_", "rk_live_"))
        and STRIPE_WEBHOOK_SECRET.startswith("whsec_")
    ):
        raise ImproperlyConfigured(
            "PAYMENT_PROVIDER=stripe needs STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET."
        )
PAYMENTS_ENABLED = bool(PAYMENT_PROVIDER)
PAYMENTS_LIVEMODE = PAYMENTS_ENABLED and STRIPE_SECRET_KEY.startswith(("sk_live_", "rk_live_"))

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"request_id": {"()": "apps.common.middleware.RequestIDLogFilter"}},
    "formatters": {
        "standard": {
            "format": "%(asctime)s %(levelname)s %(name)s request_id=%(request_id)s %(message)s",
        }
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "standard", "filters": ["request_id"]}
    },
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", default="INFO")},
    "loggers": {"django.db.backends": {"level": "WARNING"}},
}
