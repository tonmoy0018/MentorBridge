"""
One error envelope for the whole API:

    {"error": {"code": "slot_unavailable", "message": "...", "details": {"fields": {...}}}}
"""

import logging

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.serializers import as_serializer_error
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


class DomainError(exceptions.APIException):
    """A business-rule violation with a stable machine-readable code."""

    status_code = status.HTTP_409_CONFLICT
    default_code = "conflict"
    default_detail = "That action conflicts with the current state."

    def __init__(self, code: str | None = None, message: str | None = None, status_code: int | None = None):
        super().__init__(detail=message or self.default_detail, code=code or self.default_code)
        self.error_code = code or self.default_code
        if status_code is not None:
            self.status_code = status_code


class Conflict(DomainError):
    status_code = status.HTTP_409_CONFLICT


class ServiceUnavailable(DomainError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_code = "service_unavailable"
    default_detail = "This feature is not available right now."


VALIDATION_MESSAGE = "Some of the information you entered needs attention."

CODE_BY_EXCEPTION = [
    (exceptions.ValidationError, "validation_error"),
    (exceptions.NotAuthenticated, "not_authenticated"),
    (exceptions.AuthenticationFailed, "not_authenticated"),
    (exceptions.NotFound, "not_found"),
    (exceptions.MethodNotAllowed, "method_not_allowed"),
    (exceptions.NotAcceptable, "not_acceptable"),
    (exceptions.UnsupportedMediaType, "unsupported_media_type"),
    (exceptions.Throttled, "throttled"),
    (exceptions.ParseError, "parse_error"),
]


def _code_for(exc: exceptions.APIException) -> str:
    if isinstance(exc, DomainError):
        return exc.error_code
    if isinstance(exc, exceptions.PermissionDenied):
        return "csrf_failed" if str(exc.detail).startswith("CSRF Failed") else "permission_denied"
    for cls, code in CODE_BY_EXCEPTION:
        if isinstance(exc, cls):
            return code
    return "error"


def api_exception_handler(exc, context):
    if isinstance(exc, DjangoValidationError):
        exc = exceptions.ValidationError(as_serializer_error(exc))
    elif isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, DjangoPermissionDenied):
        exc = exceptions.PermissionDenied()

    response = drf_exception_handler(exc, context)
    if response is None:
        # Unexpected error: log it with the request id, return a generic message.
        logger.exception("Unhandled API error", exc_info=exc)
        return Response(
            {
                "error": {
                    "code": "server_error",
                    "message": "Something went wrong on our side.",
                    "details": {},
                }
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    code = _code_for(exc)
    details: dict = {}
    if isinstance(exc, exceptions.ValidationError):
        data = response.data
        details["fields"] = data if isinstance(data, dict) else {"non_field_errors": data}
        message = VALIDATION_MESSAGE
        non_field = details["fields"].get("non_field_errors")
        if isinstance(non_field, list) and non_field and len(details["fields"]) == 1:
            message = str(non_field[0])
    else:
        message = str(exc.detail) if not isinstance(exc.detail, (list, dict)) else "Request failed."
    if isinstance(exc, exceptions.Throttled) and exc.wait is not None:
        details["retry_after_seconds"] = int(exc.wait)

    response.data = {"error": {"code": code, "message": message, "details": details}}
    return response
