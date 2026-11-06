"""Mentor earnings, derived only from recorded payments, refunds and payouts (docs/PAYMENTS.md §4)."""

from django.conf import settings

from apps.bookings.models import BookingStatus
from apps.common.serializers import money

from .models import Payment, PaymentStatus, Payout, PayoutStatus, Refund, RefundRecordStatus


def _captured_payments(mentor):
    return Payment.objects.filter(booking__mentor=mentor, status=PaymentStatus.CAPTURED).select_related(
        "booking__student"
    )


def mentor_net_cents(payment: Payment) -> int:
    """Mentor share after succeeded refunds and lost disputes (each reverses part of the share)."""
    reversed_share = sum(
        r.mentor_share_reversed_cents
        for r in payment.refunds.all()
        if r.status == RefundRecordStatus.SUCCEEDED
    )
    return max(payment.mentor_share_cents - reversed_share, 0)


def earnings_summary(mentor) -> dict:
    pending = earned = 0
    for payment in _captured_payments(mentor).prefetch_related("refunds"):
        net = mentor_net_cents(payment)
        if payment.booking.status == BookingStatus.COMPLETED:
            earned += net
        else:
            pending += net
    paid_out = sum(p.amount_cents for p in Payout.objects.filter(mentor=mentor, status=PayoutStatus.PAID))
    currency = settings.PLATFORM_CURRENCY
    return {
        "pending": money(pending, currency),
        "available": money(max(earned - paid_out, 0), currency),
        "paid_out": money(paid_out, currency),
        "lifetime": money(earned + pending, currency),
    }


def ledger(mentor) -> list[dict]:
    entries: list[dict] = []
    for payment in _captured_payments(mentor):
        booking = payment.booking
        entries.append(
            {
                "id": f"earning-{payment.pk}",
                "kind": "earning",
                "amount": money(payment.mentor_share_cents, payment.currency),
                "description": f"{booking.service_title} with {booking.student.full_name}",
                "booking_id": booking.pk,
                "created_at": payment.captured_at or payment.created_at,
                "available_at": booking.completed_at or booking.end_at,
            }
        )
    refunds = Refund.objects.filter(
        payment__booking__mentor=mentor,
        status=RefundRecordStatus.SUCCEEDED,
        mentor_share_reversed_cents__gt=0,
    ).select_related("payment__booking")
    for refund in refunds:
        entries.append(
            {
                "id": f"refund-{refund.pk}",
                "kind": "refund_reversal",
                "amount": money(-refund.mentor_share_reversed_cents, refund.payment.currency),
                "description": f"{refund.get_reason_display()}: {refund.payment.booking.service_title}",
                "booking_id": refund.payment.booking_id,
                "created_at": refund.updated_at,
                "available_at": None,
            }
        )
    for payout in Payout.objects.filter(mentor=mentor, status=PayoutStatus.PAID):
        entries.append(
            {
                "id": f"payout-{payout.pk}",
                "kind": "payout",
                "amount": money(-payout.amount_cents, payout.currency),
                "description": f"Payout {payout.external_reference}".strip(),
                "booking_id": None,
                "created_at": payout.paid_at or payout.created_at,
                "available_at": None,
            }
        )
    return sorted(entries, key=lambda e: e["created_at"], reverse=True)
