from django.conf import settings
from django.db import connection
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import permissions, serializers
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = []

    @extend_schema(
        tags=["Operations"],
        summary="Liveness and database check",
        responses={
            200: inline_serializer(
                "Health", {"status": serializers.CharField(), "db": serializers.CharField()}
            )
        },
    )
    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            db = "ok"
        except Exception:  # noqa: BLE001 - report, don't raise
            db = "unavailable"
        return Response(
            {"status": "ok" if db == "ok" else "degraded", "db": db}, status=200 if db == "ok" else 503
        )


class PublicConfigView(APIView):
    """Marketplace settings the web app needs to explain rules before users act."""

    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=["Operations"],
        summary="Public marketplace configuration",
        responses={
            200: inline_serializer(
                "PublicConfig",
                {
                    "payments_livemode": serializers.BooleanField(
                        help_text="False when payments run in the provider's test/sandbox mode."
                    ),
                    "payments_enabled": serializers.BooleanField(
                        help_text="False until a payment provider is integrated; paid sessions "
                        "can't be booked."
                    ),
                    "currency": serializers.CharField(),
                    "booking_hold_minutes": serializers.IntegerField(),
                    "mentor_response_hours": serializers.IntegerField(),
                    "free_cancellation_hours": serializers.IntegerField(),
                    "require_verified_email": serializers.BooleanField(),
                },
            )
        },
    )
    def get(self, request):
        return Response(
            {
                "payments_enabled": settings.PAYMENTS_ENABLED,
                "payments_livemode": settings.PAYMENTS_LIVEMODE,
                "currency": settings.PLATFORM_CURRENCY,
                "booking_hold_minutes": settings.BOOKING_HOLD_MINUTES,
                "mentor_response_hours": settings.MENTOR_RESPONSE_HOURS,
                "free_cancellation_hours": settings.FREE_CANCELLATION_HOURS,
                "require_verified_email": settings.REQUIRE_VERIFIED_EMAIL,
            }
        )
