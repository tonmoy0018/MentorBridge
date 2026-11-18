from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.bookings.serializers import BookingMentorSerializer
from apps.common.serializers import MoneySerializer, money
from apps.mentors.models import SessionFormat

from .models import (
    MAX_DISCOUNT_PERCENT,
    MAX_SESSIONS,
    MAX_VALIDITY_DAYS,
    MIN_SESSIONS,
    MIN_VALIDITY_DAYS,
    MentorPackage,
    PackagePurchase,
    PurchaseStatus,
)


class PackageServiceSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    title = serializers.CharField()
    duration_minutes = serializers.IntegerField()


class FormatPricesSerializer(serializers.Serializer):
    online = MoneySerializer(allow_null=True, help_text="Null if the session isn't offered online.")
    in_person = MoneySerializer(allow_null=True, help_text="Null if the session isn't offered in person.")


class PackageSerializer(serializers.ModelSerializer):
    """A multi-session option of a service, priced for each format the service is offered in."""

    title = serializers.CharField(read_only=True)
    prices = serializers.SerializerMethodField()
    regular_prices = serializers.SerializerMethodField(help_text="The same sessions booked one by one.")
    service = serializers.SerializerMethodField()

    class Meta:
        model = MentorPackage
        fields = [
            "id",
            "title",
            "session_count",
            "discount_percent",
            "validity_days",
            "prices",
            "regular_prices",
            "service",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def _per_format(self, obj, cents):
        service = obj.service
        return {
            f: money(cents(f), service.currency) if service.offers(f) else None
            for f in (SessionFormat.ONLINE, SessionFormat.IN_PERSON)
        }

    @extend_schema_field(FormatPricesSerializer)
    def get_prices(self, obj):
        return self._per_format(obj, obj.price_cents)

    @extend_schema_field(FormatPricesSerializer)
    def get_regular_prices(self, obj):
        return self._per_format(obj, obj.regular_cents)

    @extend_schema_field(PackageServiceSerializer)
    def get_service(self, obj):
        service = obj.service
        return {"id": str(service.pk), "title": service.title, "duration_minutes": service.duration_minutes}


class PackageWriteSerializer(serializers.Serializer):
    service_id = serializers.UUIDField()
    session_count = serializers.IntegerField(min_value=MIN_SESSIONS, max_value=MAX_SESSIONS)
    discount_percent = serializers.IntegerField(min_value=0, max_value=MAX_DISCOUNT_PERCENT)
    validity_days = serializers.IntegerField(min_value=MIN_VALIDITY_DAYS, max_value=MAX_VALIDITY_DAYS)
    is_active = serializers.BooleanField(default=True)


class PurchaseRequestSerializer(serializers.Serializer):
    format = serializers.ChoiceField(
        choices=SessionFormat.choices, required=False, help_text="Defaults to online when offered."
    )


class PackagePurchaseSerializer(serializers.ModelSerializer):
    """A student's package with its remaining sessions. Expects `with_usage()` annotations."""

    format = serializers.ChoiceField(choices=SessionFormat.choices, read_only=True)
    status = serializers.ChoiceField(choices=PurchaseStatus.choices, read_only=True)
    price = serializers.SerializerMethodField()
    sessions_used = serializers.SerializerMethodField()
    sessions_remaining = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()
    mentor = serializers.SerializerMethodField()
    service_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = PackagePurchase
        fields = [
            "id",
            "title",
            "format",
            "status",
            "session_count",
            "sessions_used",
            "sessions_remaining",
            "duration_minutes",
            "price",
            "expires_at",
            "is_expired",
            "mentor",
            "service_id",
            "created_at",
        ]
        read_only_fields = fields

    def _used(self, obj) -> int:
        used = getattr(obj, "sessions_used", None)
        return obj.used_count() if used is None else used

    @extend_schema_field(MoneySerializer)
    def get_price(self, obj):
        return money(obj.price_cents, obj.currency)

    def get_sessions_used(self, obj) -> int:
        return self._used(obj)

    def get_sessions_remaining(self, obj) -> int:
        return max(obj.session_count - self._used(obj), 0)

    def get_is_expired(self, obj) -> bool:
        return obj.expires_at is not None and obj.expires_at <= timezone.now()

    @extend_schema_field(BookingMentorSerializer)
    def get_mentor(self, obj):
        mentor = obj.mentor
        request = self.context.get("request")
        avatar = None
        if mentor.avatar:
            avatar = request.build_absolute_uri(mentor.avatar.url) if request else mentor.avatar.url
        return {
            "id": str(mentor.pk),
            "slug": mentor.slug,
            "display_name": mentor.user.full_name,
            "headline": mentor.current_title or mentor.headline,
            "avatar_url": avatar,
        }


class PurchaseResponseSerializer(serializers.Serializer):
    purchase = PackagePurchaseSerializer()
    checkout_url = serializers.URLField(
        allow_null=True, help_text="Pay here; the bundle becomes usable once payment is confirmed."
    )
