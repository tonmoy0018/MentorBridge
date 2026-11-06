from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import (
    ALLOWED_HOSTS,
    CORS_ALLOWED_ORIGINS,
    CSRF_TRUSTED_ORIGINS,
    DATABASES,
    FRONTEND_URL,
    SECRET_KEY,
    SPECTACULAR_SETTINGS,
    env,
)

DEBUG = False

if not SECRET_KEY or len(SECRET_KEY) < 50 or SECRET_KEY.startswith(("dev-", "change-me")):
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set to a long random value in production.")
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must be set in production.")
if not env("DATABASE_URL", default=""):
    raise ImproperlyConfigured("DATABASE_URL must be set in production.")
if env.bool("DJANGO_DEBUG", default=False):
    raise ImproperlyConfigured("DJANGO_DEBUG must not be enabled in production.")
if "*" in ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must list real host names, not '*'.")
# The browser only ever talks to the public HTTPS origin; anything else here is a mistake.
if not CSRF_TRUSTED_ORIGINS or not all(o.startswith("https://") for o in CSRF_TRUSTED_ORIGINS):
    raise ImproperlyConfigured("DJANGO_CSRF_TRUSTED_ORIGINS must be set to the site's https:// origin(s).")
if not all(o.startswith("https://") for o in CORS_ALLOWED_ORIGINS):
    raise ImproperlyConfigured("CORS_ALLOWED_ORIGINS may only contain https:// origins.")
if not FRONTEND_URL.startswith("https://"):
    raise ImproperlyConfigured("FRONTEND_URL must be the site's https:// URL (it's used in emails).")
# Verification and password-reset emails are essential; don't silently send them nowhere.
if not env("EMAIL_HOST", default="") or env("EMAIL_HOST") == "mailpit":
    raise ImproperlyConfigured("EMAIL_HOST must point at a real SMTP service in production.")
if env("EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend") != (
    "django.core.mail.backends.smtp.EmailBackend"
):
    raise ImproperlyConfigured("Production must use the SMTP email backend.")

DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
# Cut off runaway queries (e.g. an abusive search) instead of letting them saturate PostgreSQL.
# Set DB_STATEMENT_TIMEOUT_MS=0 for one-off commands that legitimately run longer (big migrations).
_statement_timeout_ms = env.int("DB_STATEMENT_TIMEOUT_MS", default=30_000)
if _statement_timeout_ms:
    DATABASES["default"].setdefault("OPTIONS", {})["options"] = (
        f"-c statement_timeout={_statement_timeout_ms}"
    )

if env("STRIPE_API_BASE", default=""):
    raise ImproperlyConfigured("STRIPE_API_BASE is for tests only and must not be set in production.")

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = env.int("DJANGO_SECURE_HSTS_SECONDS", default=60 * 60 * 24 * 365)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = env.bool("DJANGO_SECURE_HSTS_PRELOAD", default=False)

# The OpenAPI schema and docs are only served to staff in production.
SPECTACULAR_SETTINGS = {
    **SPECTACULAR_SETTINGS,
    "SERVE_PERMISSIONS": ["rest_framework.permissions.IsAdminUser"],
}
