from rest_framework.throttling import ScopedRateThrottle, SimpleRateThrottle


class IPScopedThrottle(ScopedRateThrottle):
    """Scoped throttle keyed on client IP even for authenticated users."""

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class LoginEmailThrottle(SimpleRateThrottle):
    """Limits login attempts per target account, regardless of the attacker's IP."""

    scope = "auth_login_email"

    def get_cache_key(self, request, view):
        email = str(request.data.get("email", "")).strip().lower() if hasattr(request, "data") else ""
        if not email:
            return None
        return self.cache_format % {"scope": self.scope, "ident": email}
