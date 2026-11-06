"""
Brute-force protection for the Django admin login, which sits outside the API and its throttles.
Failed attempts are counted per client IP and per account (cache-backed, so it holds across
gunicorn workers); a successful login doesn't count.
"""

from functools import wraps

from django.core.cache import cache
from django.http import HttpResponse
from rest_framework.throttling import BaseThrottle

WINDOW_SECONDS = 15 * 60
MAX_FAILURES_PER_IP = 10
MAX_FAILURES_PER_ACCOUNT = 5


def _keys(request) -> list[tuple[str, int]]:
    ip = BaseThrottle().get_ident(request)  # honours NUM_PROXIES like the API throttles
    keys = [(f"admin-login:ip:{ip}", MAX_FAILURES_PER_IP)]
    username = request.POST.get("username", "").strip().upper()
    if username:
        keys.append((f"admin-login:user:{username}", MAX_FAILURES_PER_ACCOUNT))
    return keys


def throttle_admin_login(login_view):
    @wraps(login_view)
    def view(request, *args, **kwargs):
        if request.method != "POST":
            return login_view(request, *args, **kwargs)
        keys = _keys(request)
        if any(cache.get(key, 0) >= limit for key, limit in keys):
            return HttpResponse("Too many failed login attempts. Try again later.", status=429)
        response = login_view(request, *args, **kwargs)
        if response.status_code != 302:  # the admin redirects only on success
            for key, _ in keys:
                cache.add(key, 0, WINDOW_SECONDS)
                cache.incr(key)
        return response

    return view
