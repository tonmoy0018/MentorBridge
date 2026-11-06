from rest_framework import authentication


class SessionAuthentication(authentication.SessionAuthentication):
    """
    Django session auth with CSRF enforcement (inherited). Returning an authenticate header
    makes DRF answer unauthenticated requests with 401 (not 403), which lets clients tell
    "please log in" apart from "not allowed".
    """

    def authenticate_header(self, request):
        return 'Session realm="api"'


class EnforceCSRFMixin:
    """
    DRF only enforces CSRF for requests that are already authenticated by session. Login,
    registration and password-reset endpoints are called anonymously, so enforce it there too
    (prevents login CSRF). Test clients created with enforce_csrf_checks=False are exempt.
    """

    def initial(self, request, *args, **kwargs):
        if request.method not in ("GET", "HEAD", "OPTIONS", "TRACE"):
            authentication.SessionAuthentication().enforce_csrf(request)
        super().initial(request, *args, **kwargs)
