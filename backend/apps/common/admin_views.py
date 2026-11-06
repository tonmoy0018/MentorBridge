from datetime import UTC, datetime, time, timedelta

from django.conf import settings
from django.db.models import Count, Sum
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import generics, serializers
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AuditLogEntry
from .permissions import IsAdminRole
from .schema import AUTHED, E400, errors
from .serializers import MoneySerializer, money


class AuditLogEntrySerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = AuditLogEntry
        fields = ["id", "action", "target_type", "target_id", "metadata", "actor_name", "created_at"]
        read_only_fields = fields

    def get_actor_name(self, obj) -> str:
        return obj.actor.full_name if obj.actor else "System"


@extend_schema(
    tags=["Admin"],
    summary="Audit log",
    parameters=[OpenApiParameter("action", str), OpenApiParameter("target_type", str)],
    responses={200: AuditLogEntrySerializer(many=True), **AUTHED},
)
class AdminAuditLogView(generics.ListAPIView):
    permission_classes = [IsAdminRole]
    serializer_class = AuditLogEntrySerializer

    def get_queryset(self):
        qs = AuditLogEntry.objects.select_related("actor")
        params = self.request.query_params
        if action := params.get("action", "").strip()[:60]:
            qs = qs.filter(action__startswith=action)
        if target := params.get("target_type", "").strip()[:40]:
            qs = qs.filter(target_type=target)
        return qs


def _count_fields(name: str, choices_path: str):
    from django.utils.module_loading import import_string

    choices = import_string(choices_path)
    return inline_serializer(name, {value: serializers.IntegerField() for value in choices.values})


def _counts(qs, field: str, choices) -> dict:
    found = dict(qs.values_list(field).annotate(n=Count("pk")))
    return {value: found.get(value, 0) for value in choices}


def _parse_day(value: str | None, name: str):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValidationError({name: ["Use YYYY-MM-DD."]}) from exc


def _finance_fields() -> dict:
    # A new dict each time: DRF's serializer metaclass pops the fields out of the dict it's given.
    return {
        "gross_booking_value": MoneySerializer(),
        "platform_commission": MoneySerializer(),
        "refunds": MoneySerializer(),
        "net_platform_revenue": MoneySerializer(),
        "provider_fees": MoneySerializer(),
        "captured_payments": serializers.IntegerField(),
    }


class AdminStatsView(APIView):
    permission_classes = [IsAdminRole]

    @extend_schema(
        tags=["Admin"],
        summary="Marketplace statistics",
        description="Counts are totals; `period` covers `from`..`to` (UTC dates, inclusive, default the "
        "last 30 days). Money is split into `live` and `test`: test-mode (sandbox) payments are never "
        "revenue. `gross_booking_value`, `platform_fees` and `refunds` at the top level are live totals.",
        parameters=[OpenApiParameter("from", str), OpenApiParameter("to", str)],
        responses={
            200: inline_serializer(
                "AdminStats",
                {
                    "users": _count_fields("UserCounts", "apps.users.models.Role"),
                    "mentors_by_status": _count_fields(
                        "MentorStatusCounts", "apps.mentors.models.VerificationStatus"
                    ),
                    "bookings_by_status": _count_fields(
                        "BookingStatusCounts", "apps.bookings.models.BookingStatus"
                    ),
                    "gross_booking_value": MoneySerializer(),
                    "platform_fees": MoneySerializer(),
                    "refunds": MoneySerializer(),
                    "period": inline_serializer(
                        "StatsPeriod",
                        {
                            "from": serializers.DateField(),
                            "to": serializers.DateField(),
                            "new_users": serializers.IntegerField(),
                            "bookings_created": serializers.IntegerField(),
                            "sessions_completed": serializers.IntegerField(),
                            "live": inline_serializer("PeriodFinanceLive", _finance_fields()),
                            "test": inline_serializer("PeriodFinanceTest", _finance_fields()),
                        },
                    ),
                },
            ),
            **errors(E400, AUTHED),
        },
    )
    def get(self, request):
        from apps.bookings.models import Booking, BookingStatus
        from apps.mentors.models import MentorProfile, VerificationStatus
        from apps.users.models import Role, User

        today = timezone.now().date()
        end = _parse_day(request.query_params.get("to"), "to") or today
        start = _parse_day(request.query_params.get("from"), "from") or end - timedelta(days=29)
        if start > end:
            raise ValidationError({"from": ["`from` must be on or before `to`."]})
        start_dt = datetime.combine(start, time.min, tzinfo=UTC)
        end_dt = datetime.combine(end + timedelta(days=1), time.min, tzinfo=UTC)

        currency = settings.PLATFORM_CURRENCY
        all_time_live = _finance(None, None, livemode=True)
        return Response(
            {
                "users": _counts(User.objects.all(), "role", Role.values),
                "mentors_by_status": _counts(
                    MentorProfile.objects.all(), "verification_status", VerificationStatus.values
                ),
                "bookings_by_status": _counts(Booking.objects.all(), "status", BookingStatus.values),
                "gross_booking_value": money(all_time_live["gross_booking_value"]["amount_cents"], currency),
                "platform_fees": money(all_time_live["net_platform_revenue"]["amount_cents"], currency),
                "refunds": money(all_time_live["refunds"]["amount_cents"], currency),
                "period": {
                    "from": start,
                    "to": end,
                    "new_users": User.objects.filter(created_at__gte=start_dt, created_at__lt=end_dt).count(),
                    "bookings_created": Booking.objects.filter(
                        created_at__gte=start_dt, created_at__lt=end_dt
                    ).count(),
                    "sessions_completed": Booking.objects.filter(
                        status=BookingStatus.COMPLETED, completed_at__gte=start_dt, completed_at__lt=end_dt
                    ).count(),
                    "live": _finance(start_dt, end_dt, livemode=True),
                    "test": _finance(start_dt, end_dt, livemode=False),
                },
            }
        )


def _finance(start, end, *, livemode: bool) -> dict:
    """Captured gross, commission and refunds (by when they happened) for live or test payments."""
    from apps.payments.models import Payment, PaymentStatus, Refund, RefundRecordStatus

    currency = settings.PLATFORM_CURRENCY
    payments = Payment.objects.filter(status=PaymentStatus.CAPTURED, livemode=livemode)
    refunds = Refund.objects.filter(status=RefundRecordStatus.SUCCEEDED, payment__livemode=livemode)
    if start is not None:
        payments = payments.filter(captured_at__gte=start, captured_at__lt=end)
        refunds = refunds.filter(updated_at__gte=start, updated_at__lt=end)
    p = payments.aggregate(
        gross=Sum("amount_cents"),
        fee=Sum("platform_fee_cents"),
        prov=Sum("provider_fee_cents"),
        n=Count("pk"),
    )
    r = refunds.aggregate(amount=Sum("amount_cents"), commission=Sum("commission_reversed_cents"))
    commission = p["fee"] or 0
    return {
        "gross_booking_value": money(p["gross"] or 0, currency),
        "platform_commission": money(commission, currency),
        "refunds": money(r["amount"] or 0, currency),
        "net_platform_revenue": money(commission - (r["commission"] or 0), currency),
        "provider_fees": money(p["prov"] or 0, currency),
        "captured_payments": p["n"],
    }
