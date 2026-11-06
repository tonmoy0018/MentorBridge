from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.common.serializers import MoneySerializer, money

from .models import Payment, Payout, Refund


class EarningsSummarySerializer(serializers.Serializer):
    pending = MoneySerializer()
    available = MoneySerializer()
    paid_out = MoneySerializer()
    lifetime = MoneySerializer()


class LedgerEntrySerializer(serializers.Serializer):
    id = serializers.CharField()
    kind = serializers.ChoiceField(choices=["earning", "refund_reversal", "payout", "adjustment"])
    amount = MoneySerializer()
    description = serializers.CharField()
    booking_id = serializers.UUIDField(allow_null=True)
    created_at = serializers.DateTimeField()
    available_at = serializers.DateTimeField(allow_null=True)


class PayoutSerializer(serializers.ModelSerializer):
    amount = serializers.SerializerMethodField()

    class Meta:
        model = Payout
        fields = ["id", "amount", "status", "method", "external_reference", "created_at", "paid_at"]

    @extend_schema_field(MoneySerializer)
    def get_amount(self, obj):
        return money(obj.amount_cents, obj.currency)


class CheckoutSerializer(serializers.Serializer):
    payment_id = serializers.UUIDField()
    checkout_url = serializers.URLField()
    expires_at = serializers.DateTimeField()
    livemode = serializers.BooleanField(help_text="False when the provider is in test/sandbox mode.")


def _m(cents, currency):
    return money(cents, currency)


class RefundSerializer(serializers.ModelSerializer):
    amount = serializers.SerializerMethodField()
    commission_reversed = serializers.SerializerMethodField()
    mentor_share_reversed = serializers.SerializerMethodField()
    payment_id = serializers.UUIDField(source="payment.id", read_only=True)
    booking_id = serializers.UUIDField(source="payment.booking_id", read_only=True)
    initiated_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Refund
        fields = [
            "id",
            "payment_id",
            "booking_id",
            "amount",
            "commission_reversed",
            "mentor_share_reversed",
            "reason",
            "status",
            "provider_reference",
            "failure_code",
            "note",
            "initiated_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    @extend_schema_field(MoneySerializer)
    def get_amount(self, obj):
        return _m(obj.amount_cents, obj.payment.currency)

    @extend_schema_field(MoneySerializer)
    def get_commission_reversed(self, obj):
        return _m(obj.commission_reversed_cents, obj.payment.currency)

    @extend_schema_field(MoneySerializer)
    def get_mentor_share_reversed(self, obj):
        return _m(obj.mentor_share_reversed_cents, obj.payment.currency)

    def get_initiated_by_name(self, obj) -> str | None:
        return obj.initiated_by.full_name if obj.initiated_by else None


class AdminPaymentSerializer(serializers.ModelSerializer):
    booking_id = serializers.UUIDField(source="booking.id")
    student_display_name = serializers.CharField(source="booking.student.full_name")
    mentor_display_name = serializers.CharField(source="booking.mentor.user.full_name")
    amount = serializers.SerializerMethodField()
    platform_fee = serializers.SerializerMethodField()
    mentor_share = serializers.SerializerMethodField()
    provider_fee = serializers.SerializerMethodField()
    refunded = serializers.SerializerMethodField()
    refundable = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            "id",
            "booking_id",
            "student_display_name",
            "mentor_display_name",
            "amount",
            "commission_bps",
            "platform_fee",
            "mentor_share",
            "provider_fee",
            "refunded",
            "refundable",
            "status",
            "refund_status",
            "dispute_status",
            "provider",
            "provider_reference",
            "livemode",
            "failure_code",
            "created_at",
            "captured_at",
        ]
        read_only_fields = fields

    @extend_schema_field(MoneySerializer)
    def get_amount(self, obj):
        return _m(obj.amount_cents, obj.currency)

    @extend_schema_field(MoneySerializer)
    def get_platform_fee(self, obj):
        return _m(obj.platform_fee_cents, obj.currency)

    @extend_schema_field(MoneySerializer)
    def get_mentor_share(self, obj):
        return _m(obj.mentor_share_cents, obj.currency)

    @extend_schema_field(MoneySerializer(allow_null=True))
    def get_provider_fee(self, obj):
        return None if obj.provider_fee_cents is None else _m(obj.provider_fee_cents, obj.currency)

    @extend_schema_field(MoneySerializer)
    def get_refunded(self, obj):
        return _m(obj.refunded_amount_cents, obj.currency)

    @extend_schema_field(MoneySerializer)
    def get_refundable(self, obj):
        from .services import refundable_cents

        return _m(refundable_cents(obj) if obj.status == "captured" else 0, obj.currency)


class AdminRefundRequestSerializer(serializers.Serializer):
    amount_cents = serializers.IntegerField(
        min_value=1, required=False, help_text="Omit for a full refund of what remains."
    )
    note = serializers.CharField(max_length=500)
