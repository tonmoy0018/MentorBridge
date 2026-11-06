from rest_framework.throttling import ScopedRateThrottle, SimpleRateThrottle


class IPScopedThrottle(ScopedRateThrottle):
    """Scoped throttle keyed on client IP even for authenticated users."""

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class LoginEmailThrottle(SimpleRateThrottle):
    """Limits login attempts per target account, regardless of the attacker's IP."""

    scope = "auth_login_email"

    def get_cache_key(self, request, view):
        # upper(), not lower(): it folds the same look-alikes PostgreSQL's UPPER() does for the
        # case-insensitive account lookup (e.g. "ſ" → "S"), so variants share one bucket.
        email = str(request.data.get("email", "")).strip().upper() if hasattr(request, "data") else ""
        if not email:
            return None
        return self.cache_format % {"scope": self.scope, "ident": email}
