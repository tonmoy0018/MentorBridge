from django.conf import settings
from rest_framework import serializers


class MoneySerializer(serializers.Serializer):
    """Money as integer minor units + ISO currency. Never floats."""

    amount_cents = serializers.IntegerField()
    currency = serializers.CharField()


def money(amount_cents: int, currency: str | None = None) -> dict:
    return {"amount_cents": int(amount_cents), "currency": currency or settings.PLATFORM_CURRENCY}


class ErrorDetailSerializer(serializers.Serializer):
    code = serializers.CharField()
    message = serializers.CharField()
    details = serializers.DictField()


class ErrorResponseSerializer(serializers.Serializer):
    error = ErrorDetailSerializer()


class ReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=1000, required=False, allow_blank=True, trim_whitespace=True)


class RequiredReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=1000, trim_whitespace=True)
