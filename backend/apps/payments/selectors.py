"""Mentor earnings, derived only from recorded payments, refunds and payouts (docs/PAYMENTS.md §4)."""

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from apps.bookings.models import BookingStatus
from apps.common.serializers import money

from .models import Payment, PaymentStatus, Payout, PayoutStatus, Refund, RefundRecordStatus


def _for_mentor(mentor, prefix: str = "") -> Q:
    return Q(**{f"{prefix}booking__mentor": mentor}) | Q(**{f"{prefix}package_purchase__mentor": mentor})


def _captured_payments(mentor):
    return Payment.objects.filter(_for_mentor(mentor), status=PaymentStatus.CAPTURED).select_related(
        "booking__student", "package_purchase__student", "package_purchase__service"
    )


def _is_earned(payment: Payment) -> bool:
    """A session's share is earned once it's completed; a bundle's once it's used up or expired."""
    if payment.booking_id:
        return payment.booking.status == BookingStatus.COMPLETED
    purchase = payment.package_purchase
    if purchase.expires_at and purchase.expires_at <= timezone.now():
        return True
    return purchase.bookings.filter(status=BookingStatus.COMPLETED).count() >= purchase.session_count


def _available_at(payment: Payment):
    if payment.booking_id:
        return payment.booking.completed_at or payment.booking.end_at
    return payment.package_purchase.expires_at


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
        if _is_earned(payment):
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
        entries.append(
            {
                "id": f"earning-{payment.pk}",
                "kind": "earning",
                "amount": money(payment.mentor_share_cents, payment.currency),
                "description": f"{payment.title} with {payment.student.full_name}",
                "booking_id": payment.booking_id,
                "created_at": payment.captured_at or payment.created_at,
                "available_at": _available_at(payment),
            }
        )
    refunds = Refund.objects.filter(
        _for_mentor(mentor, "payment__"),
        status=RefundRecordStatus.SUCCEEDED,
        mentor_share_reversed_cents__gt=0,
    ).select_related("payment__booking", "payment__package_purchase")
    for refund in refunds:
        entries.append(
            {
                "id": f"refund-{refund.pk}",
                "kind": "refund_reversal",
                "amount": money(-refund.mentor_share_reversed_cents, refund.payment.currency),
                "description": f"{refund.get_reason_display()}: {refund.payment.title}",
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
