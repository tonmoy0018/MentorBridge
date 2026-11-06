import logging

from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.pagination import StandardPagination
from apps.common.permissions import IsAdminRole, IsMentor
from apps.common.schema import AUTHED, E400, E404, E409, errors

from . import selectors, services
from .models import Payment, PaymentStatus, Payout, Refund, RefundReason, RefundRecordStatus
from .providers import InvalidWebhook
from .serializers import (
    AdminPaymentSerializer,
    AdminRefundRequestSerializer,
    EarningsSummarySerializer,
    LedgerEntrySerializer,
    PayoutSerializer,
    RefundSerializer,
)

logger = logging.getLogger(__name__)
ME = ["Mentor self-service"]
ADMIN = ["Admin"]


class EarningsSummaryView(APIView):
    permission_classes = [IsMentor]

    @extend_schema(
        tags=ME,
        summary="My earnings summary",
        description="Mentor share of captured payments, minus refund and dispute reversals, "
        "and paid payouts.",
        responses={200: EarningsSummarySerializer, **AUTHED},
    )
    def get(self, request):
        return Response(selectors.earnings_summary(request.user.mentor_profile))


class LedgerView(APIView):
    permission_classes = [IsMentor]

    @extend_schema(
        tags=ME, summary="My earnings activity", responses={200: LedgerEntrySerializer(many=True), **AUTHED}
    )
    def get(self, request):
        paginator = StandardPagination()
        page = paginator.paginate_queryset(selectors.ledger(request.user.mentor_profile), request, view=self)
        return paginator.get_paginated_response(LedgerEntrySerializer(page, many=True).data)


@extend_schema(tags=ME, summary="My payouts", responses={200: PayoutSerializer(many=True), **AUTHED})
class PayoutListView(generics.ListAPIView):
    permission_classes = [IsMentor]
    serializer_class = PayoutSerializer

    def get_queryset(self):
        return Payout.objects.filter(mentor=self.request.user.mentor_profile)


@method_decorator(csrf_exempt, name="dispatch")
class PaymentWebhookView(APIView):
    """
    Provider → MentorBridge notifications. No session or CSRF (the provider can't have them);
    authenticity comes from the provider's signature, verified before anything is read.
    """

    permission_classes = [permissions.AllowAny]
    authentication_classes: list = []
    throttle_classes: list = []

    @extend_schema(
        tags=["Payments"],
        summary="Payment provider webhook",
        description="Called by the payment provider. The signature header is verified against the "
        "configured webhook secret; unsigned or tampered requests get 400 and change nothing. Each "
        "provider event id is processed once.",
        request=None,
        responses={200: OpenApiResponse(description="Accepted (or already processed)."), **E400},
    )
    def post(self, request, provider):
        from django.conf import settings

        if not settings.PAYMENTS_ENABLED or provider != settings.PAYMENT_PROVIDER:
            return Response(
                {"error": {"code": "not_found", "message": "Unknown provider.", "details": {}}}, status=404
            )
        try:
            outcome = services.process_webhook(request.body, request.headers)
        except InvalidWebhook:
            logger.warning("Rejected webhook with an invalid signature")
            return Response(
                {
                    "error": {
                        "code": "invalid_signature",
                        "message": "Invalid webhook signature.",
                        "details": {},
                    }
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"received": True, "outcome": outcome})


@extend_schema(
    tags=ADMIN,
    summary="List payments (read-only)",
    parameters=[
        OpenApiParameter("status", str, enum=PaymentStatus.values),
        OpenApiParameter("livemode", bool, description="Filter live vs test-mode payments."),
    ],
    responses={200: AdminPaymentSerializer(many=True), **AUTHED},
)
class AdminPaymentListView(generics.ListAPIView):
    permission_classes = [IsAdminRole]
    serializer_class = AdminPaymentSerializer

    def get_queryset(self):
        qs = Payment.objects.select_related("booking__student", "booking__mentor__user").prefetch_related(
            "refunds"
        )
        params = self.request.query_params
        if (value := params.get("status")) in PaymentStatus.values:
            qs = qs.filter(status=value)
        if (live := params.get("livemode")) in ("true", "false"):
            qs = qs.filter(livemode=live == "true")
        return qs


@extend_schema(
    tags=ADMIN, summary="Get a payment", responses={200: AdminPaymentSerializer, **errors(AUTHED, E404)}
)
class AdminPaymentDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAdminRole]
    serializer_class = AdminPaymentSerializer
    queryset = Payment.objects.select_related("booking__student", "booking__mentor__user")


class AdminPaymentRefundView(APIView):
    permission_classes = [IsAdminRole]

    @extend_schema(
        tags=ADMIN,
        summary="Refund a captured payment",
        description="Full refund of what remains, or a partial `amount_cents`. Executed through the "
        "provider (idempotent per refund) and audit-logged. The refund is `pending` until the "
        "provider confirms it.",
        request=AdminRefundRequestSerializer,
        responses={201: RefundSerializer, **errors(E400, AUTHED, E404, E409)},
    )
    def post(self, request, pk):
        payment = get_object_or_404(Payment, pk=pk)
        serializer = AdminRefundRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        refund = services.create_refund(
            payment,
            amount_cents=serializer.validated_data.get("amount_cents"),
            reason=RefundReason.ADMIN,
            actor=request.user,
            note=serializer.validated_data["note"],
        )
        refund.refresh_from_db()
        return Response(RefundSerializer(refund).data, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=ADMIN,
    summary="Refund tracking",
    parameters=[OpenApiParameter("status", str, enum=RefundRecordStatus.values)],
    responses={200: RefundSerializer(many=True), **AUTHED},
)
class AdminRefundListView(generics.ListAPIView):
    permission_classes = [IsAdminRole]
    serializer_class = RefundSerializer

    def get_queryset(self):
        qs = Refund.objects.select_related("payment", "initiated_by")
        if (value := self.request.query_params.get("status")) in RefundRecordStatus.values:
            qs = qs.filter(status=value)
        return qs
