"""OpenAPI extensions (imported in CommonConfig.ready)."""

from drf_spectacular.extensions import OpenApiAuthenticationExtension


class SessionCookieScheme(OpenApiAuthenticationExtension):
    target_class = "apps.common.authentication.SessionAuthentication"
    name = "sessionAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "apiKey",
            "in": "cookie",
            "name": "sessionid",
            "description": "Django session cookie set by `POST /api/v1/auth/login/`. Unsafe methods also "
            "require the `X-CSRFToken` header matching the `csrftoken` cookie.",
        }


# Response fields that are deliberately omitted in some responses.
OPTIONAL_RESPONSE_FIELDS = {"Category": {"mentor_count"}}


def mark_response_fields_required(result, generator, request, public):
    """
    Response serializers always emit every field, but drf-spectacular marks fields with model
    defaults as optional. Mark them required so generated clients (frontend/src/lib/api/
    generated.ts) don't treat always-present fields as maybe-missing. Request schemas are untouched.
    """
    for name, schema in result.get("components", {}).get("schemas", {}).items():
        if name.endswith("Request") or schema.get("type") != "object" or "properties" not in schema:
            continue
        optional = OPTIONAL_RESPONSE_FIELDS.get(name, set())
        schema["required"] = sorted(set(schema["properties"]) - optional)
    return result
