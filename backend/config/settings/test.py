from .base import *  # noqa: F403
from .base import BASE_DIR, env

DEBUG = False
SECRET_KEY = "test-secret-key-not-for-production-0123456789abcdefghijklmnop"  # noqa: S105
ALLOWED_HOSTS = ["testserver", "localhost"]
CSRF_TRUSTED_ORIGINS = ["http://localhost:3000"]

DATABASES = {
    "default": env.db(
        "DATABASE_URL", default="postgres://mentorbridge:mentorbridge@localhost:5433/mentorbridge"
    )
}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # fast, tests only
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
MEDIA_ROOT = BASE_DIR / ".test-media"
FRONTEND_URL = "http://localhost:3000"
# Most tests use free sessions to stay clear of payments; the minimum price has its own tests.
MIN_SESSION_PRICE_CENTS = 0
