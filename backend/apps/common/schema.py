"""Shared OpenAPI response declarations so every endpoint documents its error envelope."""

from drf_spectacular.utils import OpenApiResponse

from .serializers import ErrorResponseSerializer


def _err(description: str) -> OpenApiResponse:
    return OpenApiResponse(ErrorResponseSerializer, description=description)


E400 = {400: _err("Validation error (`validation_error`); field errors in `details.fields`.")}
E401 = {401: _err("Not logged in (`not_authenticated`).")}
E403 = {403: _err("Wrong role or CSRF failure (`permission_denied`, `csrf_failed`).")}
E404 = {404: _err("Not found, or not visible to you (`not_found`).")}
E409 = {409: _err("Conflicts with the current state (e.g. `slot_unavailable`, `invalid_state`).")}
E429 = {429: _err("Rate limited (`throttled`); see the Retry-After header.")}
AUTHED = {**E401, **E403}


def errors(*groups: dict) -> dict:
    merged: dict = {}
    for group in groups:
        merged.update(group)
    return merged
