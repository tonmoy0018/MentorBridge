"""
Payment workflow (docs/PAYMENTS.md §3):

1. The student books a paid service → booking `pending_payment` (slot held).
2. `start_checkout` creates a Payment with the server-side amount and commission breakdown and asks
   the provider for a checkout session; the student pays on the provider's page.
3. The provider sends a signed webhook. `process_webhook` verifies it, records the event id (so a
   duplicate is a no-op), checks the amount and currency, and moves payment and booking forward:
   authorised → booking `requested` (or `confirmed` and captured, if the mentor auto-accepts).
4. Mentor accepts → `capture_for_booking`; mentor declines / request expires → authorisation released.
5. Cancellations follow the refund policy → `create_refund`; refunds complete from webhooks.

A browser redirect back from checkout never changes anything: only verified provider data does.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.utils import timezone

from apps.common.exceptions import Conflict, DomainError
from apps.common.models import record_audit

from . import commission
from .models import (
    PAYMENT_TRANSITIONS,
    DisputeStatus,
    Payment,
    PaymentStatus,
    Refund,
    RefundReason,
    RefundRecordStatus,
    RefundStatus,
    WebhookEvent,
)
from .providers import EventKind, ProviderError, ProviderEvent, get_provider

logger = logging.getLogger(__name__)


class PaymentProviderError(DomainError):
    status_code = 502
    default_code = "payment_provider_error"
    default_detail = "The payment provider couldn't complete the request. Please try again."


def _provider():
    return get_provider()


def _provider_or_none():
    """For clean-up paths (releasing holds): never crash if payments were switched off meanwhile."""
    try:
        return get_provider()
    except ImproperlyConfigured:
        logger.error("Payment clean-up skipped: no payment provider is configured")
        return None


def _set_status(payment: Payment, status: str, **fields) -> bool:
    """Apply an allowed transition; return False (and change nothing) for a stale or invalid one."""
    if status == payment.status:
        return False
    if status not in PAYMENT_TRANSITIONS[payment.status]:
        logger.info("Ignoring payment %s transition %s → %s", payment.pk, payment.status, status)
        return False
    payment.status = status
    for name, value in fields.items():
        setattr(payment, name, value)
    payment.save()
    return True


# --- checkout ---------------------------------------------------------------------------------


def start_checkout(booking, *, student) -> Payment:
    """Create (or reuse) the checkout for a held booking. Returns the Payment with a checkout URL."""
    from apps.bookings.models import Booking, BookingStatus

    if not settings.PAYMENTS_ENABLED:
        raise DomainError("payments_unavailable", "Online payment isn't available yet.", status_code=503)
    now = timezone.now()
    with transaction.atomic():
        booking = Booking.objects.select_for_update().select_related("mentor").get(pk=booking.pk)
        if booking.student_id != student.pk:
            raise Conflict("invalid_state", "This booking isn't yours.")
        if booking.status != BookingStatus.PENDING_PAYMENT or booking.price_cents == 0:
            raise Conflict("invalid_state", "This booking isn't awaiting payment.")
        if booking.hold_expires_at and booking.hold_expires_at <= now:
            raise Conflict("hold_expired", "This time is no longer held. Please choose a time again.")

        existing = booking.payments.filter(status__in=[PaymentStatus.CREATED, PaymentStatus.FAILED]).first()
        if (
            existing
            and existing.checkout_url
            and existing.checkout_expires_at
            and existing.checkout_expires_at > now
        ):
            return existing  # repeated clicks reuse the same checkout
        if booking.payments.filter(status__in=[PaymentStatus.AUTHORIZED, PaymentStatus.CAPTURED]).exists():
            raise Conflict("already_paid", "This booking has already been paid.")
        if existing:
            _set_status(existing, PaymentStatus.CANCELLED, failure_code="checkout_replaced")

        split = commission.breakdown(booking.price_cents, commission.commission_bps_for(booking.mentor))
        provider = _provider()
        payment = Payment.objects.create(
            booking=booking,
            provider=provider.name,
            livemode=provider.livemode,
            amount_cents=split.gross_cents,
            currency=booking.currency,
            commission_bps=split.commission_bps,
            platform_fee_cents=split.commission_cents,
            mentor_share_cents=split.mentor_share_cents,
        )
        # Providers require a minimum checkout lifetime (Stripe: 30 minutes); keep the slot held
        # for at least that long so a student who is paying never loses the slot mid-checkout.
        expires_at = max(
            booking.hold_expires_at or now, now + timedelta(minutes=settings.CHECKOUT_MIN_MINUTES)
        )
        return_base = f"{settings.FRONTEND_URL}/dashboard/student/bookings"
        try:
            session = provider.create_checkout(
                payment=payment,
                booking=booking,
                success_url=f"{return_base}?checkout={booking.pk}",
                cancel_url=f"{return_base}?checkout={booking.pk}&cancelled=1",
                expires_at=expires_at,
            )
        except ProviderError as exc:
            # Rolls back the new Payment row; the booking keeps its hold and the student can retry.
            raise PaymentProviderError() from exc
        payment.checkout_reference = session.reference
        payment.checkout_url = session.url
        payment.checkout_expires_at = session.expires_at
        payment.save()
        if booking.hold_expires_at is None or session.expires_at > booking.hold_expires_at:
            booking.hold_expires_at = session.expires_at
            booking.save(update_fields=["hold_expires_at", "updated_at"])
        return payment


# --- webhooks ---------------------------------------------------------------------------------


def process_webhook(body: bytes, headers) -> str:
    """
    Verify and apply one provider notification. Returns a short outcome for logging/tests.
    Raises InvalidWebhook (→ 400) if the signature doesn't verify. Idempotent per event id.
    """
    provider = _provider()
    event = provider.parse_webhook(body, headers)  # raises InvalidWebhook
    with transaction.atomic():
        record, created = WebhookEvent.objects.select_for_update().get_or_create(
            provider=provider.name,
            event_id=event.event_id,
            defaults={
                "event_type": event.raw_type,
                "object_reference": event.object_reference[:255],
                "livemode": event.livemode,
            },
        )
        if not created and record.processed_at is not None:
            return "duplicate"
        outcome = _apply_event(event, provider)
        record.processed_at = timezone.now()
        record.outcome = outcome[:60]
        record.save(update_fields=["processed_at", "outcome"])
    logger.info("Webhook %s (%s): %s", event.event_id, event.raw_type, outcome)
    return outcome


def _find_payment(event: ProviderEvent) -> Payment | None:
    qs = Payment.objects.select_for_update().select_related("booking__mentor__user", "booking__student")
    if event.payment_id:
        try:
            payment = qs.filter(pk=event.payment_id).first()
        except Exception:  # malformed UUID in metadata
            payment = None
        if payment:
            return payment
    if event.provider_payment_reference:
        payment = qs.filter(provider_reference=event.provider_payment_reference).first()
        if payment:
            return payment
    if event.checkout_reference:
        return qs.filter(checkout_reference=event.checkout_reference).first()
    return None


def _amount_matches(payment: Payment, event: ProviderEvent) -> bool:
    return event.amount_cents == payment.amount_cents and (event.currency or "") == payment.currency


def _apply_event(event: ProviderEvent, provider) -> str:
    if event.kind == EventKind.IGNORED:
        return "ignored"
    payment = _find_payment(event)
    if payment is None:
        logger.warning("Webhook %s refers to no known payment", event.event_id)
        return "unknown_payment"
    if event.livemode != payment.livemode:
        logger.error("Webhook %s mode doesn't match payment %s", event.event_id, payment.pk)
        return "mode_mismatch"
    if event.provider_payment_reference and not payment.provider_reference:
        payment.provider_reference = event.provider_payment_reference
        payment.save(update_fields=["provider_reference", "updated_at"])

    handler = {
        EventKind.CHECKOUT_COMPLETED: _on_checkout_completed,
        EventKind.CHECKOUT_EXPIRED: _on_checkout_expired,
        EventKind.PAYMENT_AUTHORIZED: _on_authorized,
        EventKind.PAYMENT_CAPTURED: _on_captured,
        EventKind.PAYMENT_FAILED: _on_failed,
        EventKind.PAYMENT_CANCELLED: _on_cancelled,
        EventKind.REFUND_SUCCEEDED: _on_refund_result,
        EventKind.REFUND_FAILED: _on_refund_result,
        EventKind.DISPUTE_OPENED: _on_dispute,
        EventKind.DISPUTE_WON: _on_dispute,
        EventKind.DISPUTE_LOST: _on_dispute,
    }[event.kind]
    return handler(payment, event, provider)


def _on_checkout_completed(payment, event, provider) -> str:
    # Linking only; the authorisation itself arrives as its own event.
    return "linked"


def _on_checkout_expired(payment, event, provider) -> str:
    from apps.bookings.models import BookingStatus
    from apps.bookings.services import expire_booking

    changed = _set_status(
        payment, PaymentStatus.CANCELLED, failure_code=payment.failure_code or "checkout_expired"
    )
    if payment.booking.status == BookingStatus.PENDING_PAYMENT:
        expire_booking(payment.booking, note="Checkout expired without payment.")
    return "checkout_expired" if changed else "noop"


def _on_authorized(payment, event, provider) -> str:
    from apps.bookings.models import BookingStatus
    from apps.bookings.services import payment_authorized

    if payment.status == PaymentStatus.CANCELLED:
        # Paid on a checkout we'd already given up on (hold expired, booking cancelled, checkout
        # replaced): the money must not stay held, so release the authorisation straight away.
        _release(payment, provider, failure_code=payment.failure_code or "booking_unavailable")
        _notify_payment(payment, "payment_released", key=f"payment.released:{payment.pk}")
        return "released_late_payment"
    if not _amount_matches(payment, event):
        logger.error("Payment %s authorised amount/currency mismatch; releasing", payment.pk)
        _set_status(payment, PaymentStatus.AUTHORIZED, authorized_at=timezone.now())
        _release(payment, provider, failure_code="amount_mismatch")
        return "amount_mismatch_released"
    if not _set_status(payment, PaymentStatus.AUTHORIZED, authorized_at=timezone.now(), failure_code=""):
        return "noop"
    booking = payment.booking
    if booking.status != BookingStatus.PENDING_PAYMENT:
        # Paid too late (hold expired, booking cancelled): never charge for a slot we can't honour.
        _release(payment, provider, failure_code="booking_unavailable")
        _notify_payment(payment, "payment_released", key=f"payment.released:{payment.pk}")
        return "released_late_payment"
    payment_authorized(booking, payment)
    return "authorized"


def _on_captured(payment, event, provider) -> str:
    if not _amount_matches(payment, event):
        logger.error("Payment %s captured amount mismatch", payment.pk)
        return "amount_mismatch"
    changed = _set_status(payment, PaymentStatus.CAPTURED, captured_at=payment.captured_at or timezone.now())
    return "captured" if changed else "noop"


def _on_failed(payment, event, provider) -> str:
    if payment.status not in (PaymentStatus.CREATED, PaymentStatus.FAILED):
        return "noop"
    payment.failure_code = (event.failure_code or "payment_failed")[:100]
    if payment.status == PaymentStatus.CREATED:
        _set_status(payment, PaymentStatus.FAILED)
    else:
        payment.save(update_fields=["failure_code", "updated_at"])
    _notify_payment(payment, "payment_failed", key=f"payment.failed:{event.event_id}")
    return "failed"


def _on_cancelled(payment, event, provider) -> str:
    from apps.bookings.models import BookingStatus
    from apps.bookings.services import expire_booking

    changed = _set_status(payment, PaymentStatus.CANCELLED, failure_code=payment.failure_code or "cancelled")
    booking = payment.booking
    # An authorisation that lapses (≈7 days) or is cancelled before capture ends the request.
    if changed and booking.status in (BookingStatus.PENDING_PAYMENT, BookingStatus.REQUESTED):
        expire_booking(booking, note="Payment authorisation was cancelled.")
    return "cancelled" if changed else "noop"


def _on_refund_result(payment, event, provider) -> str:
    refund = None
    if event.refund_id:
        refund = Refund.objects.select_for_update().filter(pk=event.refund_id, payment=payment).first()
    if refund is None and event.refund_reference:
        refund = Refund.objects.select_for_update().filter(provider_reference=event.refund_reference).first()
    if refund is None:
        # A refund made outside MentorBridge (e.g. in the provider dashboard): record it.
        if event.kind != EventKind.REFUND_SUCCEEDED or not event.amount_cents:
            return "unknown_refund"
        reversed_commission, reversed_share = commission.proportional_reversal(payment, event.amount_cents)
        refund = Refund.objects.create(
            payment=payment,
            amount_cents=event.amount_cents,
            commission_reversed_cents=reversed_commission,
            mentor_share_reversed_cents=reversed_share,
            reason=RefundReason.ADMIN,
            provider_reference=event.refund_reference,
            note="Recorded from a provider-side refund.",
        )
    succeeded = event.kind == EventKind.REFUND_SUCCEEDED
    return _finish_refund(refund, succeeded=succeeded, failure_code=event.failure_code)


def _on_dispute(payment, event, provider) -> str:
    status = {
        EventKind.DISPUTE_OPENED: DisputeStatus.OPEN,
        EventKind.DISPUTE_WON: DisputeStatus.WON,
        EventKind.DISPUTE_LOST: DisputeStatus.LOST,
    }[event.kind]
    if payment.dispute_status == status:
        return "noop"
    payment.dispute_status = status
    payment.save(update_fields=["dispute_status", "updated_at"])
    if status == DisputeStatus.LOST:
        # The provider has returned the money to the cardholder: reverse it like a refund.
        remaining = payment.amount_cents - payment.refunded_amount_cents
        amount = min(event.amount_cents or remaining, remaining)
        if amount > 0:
            reversed_commission, reversed_share = commission.proportional_reversal(payment, amount)
            refund = Refund.objects.create(
                payment=payment,
                amount_cents=amount,
                commission_reversed_cents=reversed_commission,
                mentor_share_reversed_cents=reversed_share,
                reason=RefundReason.DISPUTE_LOST,
                note="Dispute lost.",
            )
            _finish_refund(refund, succeeded=True, notify=False)
    record_audit(None, f"payment.dispute.{status}", payment, {"event_id": event.event_id})
    return f"dispute_{status}"


# --- capture, release, refunds ----------------------------------------------------------------


def _open_payment(booking, status) -> Payment | None:
    return Payment.objects.select_for_update().filter(booking=booking, status=status).first()


def capture_for_booking(booking) -> Payment | None:
    """
    Capture the authorised payment for a paid booking (mentor accepted, or auto-accept). Server-to-
    server and authenticated, so a successful response is trusted; the matching webhook is a no-op.
    Raises Conflict if there's nothing authorised, PaymentProviderError if the capture fails.
    """
    if booking.price_cents == 0:
        return None
    payment = _open_payment(booking, PaymentStatus.AUTHORIZED)
    if payment is None:
        raise Conflict("payment_required", "This booking has no authorised payment to capture.")
    try:
        result = _provider().capture(payment)
    except ProviderError as exc:
        payment.failure_code = exc.code[:100]
        payment.save(update_fields=["failure_code", "updated_at"])
        raise PaymentProviderError() from exc
    _set_status(
        payment,
        PaymentStatus.CAPTURED,
        captured_at=timezone.now(),
        provider_fee_cents=result.provider_fee_cents,
        failure_code="",
    )
    return payment


def _release(payment: Payment, provider, *, failure_code: str) -> None:
    try:
        provider.cancel_authorization(payment)
    except ProviderError as exc:
        # The authorisation lapses on its own (≈7 days); the provider will then send a cancel event.
        logger.warning("Couldn't release payment %s now: %s", payment.pk, exc.code)
        payment.failure_code = f"release_failed:{exc.code}"[:100]
        payment.save(update_fields=["failure_code", "updated_at"])
        return
    _set_status(payment, PaymentStatus.CANCELLED, failure_code=failure_code)


def release_for_booking(booking, *, reason: str) -> None:
    """Release an uncaptured authorisation (declined, expired or cancelled before acceptance)."""
    if booking.price_cents == 0:
        return
    authorized = _open_payment(booking, PaymentStatus.AUTHORIZED)
    open_checkouts = list(
        Payment.objects.select_for_update().filter(
            booking=booking, status__in=[PaymentStatus.CREATED, PaymentStatus.FAILED]
        )
    )
    if authorized is None and not open_checkouts:
        return
    provider = _provider_or_none()
    if provider is None:
        return
    if authorized is not None:
        _release(authorized, provider, failure_code=reason)
    # A checkout that's still open can't be paid any more either.
    for open_checkout in open_checkouts:
        try:
            provider.expire_checkout(open_checkout)
        except ProviderError as exc:
            logger.warning("Couldn't expire checkout for payment %s: %s", open_checkout.pk, exc.code)
        _set_status(open_checkout, PaymentStatus.CANCELLED, failure_code=reason)


def refundable_cents(payment: Payment) -> int:
    in_flight = payment.refunds.filter(status__in=[RefundRecordStatus.PENDING, RefundRecordStatus.SUCCEEDED])
    return payment.amount_cents - sum(r.amount_cents for r in in_flight)


def create_refund(
    payment: Payment, *, amount_cents: int | None, reason: str, actor=None, note: str = ""
) -> Refund:
    """
    Refund a captured payment (fully by default). The Refund row is committed before the provider is
    called, so the provider's idempotency key (`refund-<id>`) makes retries safe and nothing is
    refunded without a record. Completion comes from the provider (response or webhook).
    """
    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(pk=payment.pk)
        if payment.status != PaymentStatus.CAPTURED:
            raise Conflict("not_refundable", "Only captured payments can be refunded.")
        available = refundable_cents(payment)
        amount = available if amount_cents is None else amount_cents
        if amount <= 0 or amount > available:
            raise Conflict("refund_too_large", f"At most {available} can be refunded.")
        reversed_commission, reversed_share = commission.proportional_reversal(payment, amount)
        refund = Refund.objects.create(
            payment=payment,
            amount_cents=amount,
            commission_reversed_cents=reversed_commission,
            mentor_share_reversed_cents=reversed_share,
            reason=reason,
            initiated_by=actor,
            note=note[:500],
        )
        _refresh_refund_status(payment)
        if actor is not None:
            record_audit(
                actor,
                "payment.refund.created",
                payment,
                {"refund_id": str(refund.pk), "amount_cents": amount},
            )
        _notify_payment(payment, "refund_initiated", key=f"refund.initiated:{refund.pk}", amount_cents=amount)

    try:
        result = _provider().refund(refund)
    except ProviderError as exc:
        with transaction.atomic():
            refund = Refund.objects.select_for_update().get(pk=refund.pk)
            _finish_refund(refund, succeeded=False, failure_code=exc.code)
        return refund
    with transaction.atomic():
        refund = Refund.objects.select_for_update().get(pk=refund.pk)
        if not refund.provider_reference:
            refund.provider_reference = result.reference
            refund.save(update_fields=["provider_reference", "updated_at"])
        if result.succeeded or result.failed:
            _finish_refund(refund, succeeded=result.succeeded, failure_code=result.failure_code)
    return refund


def _finish_refund(refund: Refund, *, succeeded: bool, failure_code: str = "", notify: bool = True) -> str:
    if refund.status != RefundRecordStatus.PENDING:
        return "noop"
    payment = Payment.objects.select_for_update().get(pk=refund.payment_id)
    refund.status = RefundRecordStatus.SUCCEEDED if succeeded else RefundRecordStatus.FAILED
    refund.failure_code = "" if succeeded else (failure_code or "refund_failed")[:100]
    refund.save(update_fields=["status", "failure_code", "updated_at"])
    if succeeded:
        payment.refunded_amount_cents += refund.amount_cents
        payment.save(update_fields=["refunded_amount_cents", "updated_at"])
    _refresh_refund_status(payment)
    if notify:
        template = "refund_succeeded" if succeeded else "refund_failed"
        _notify_payment(
            payment, template, key=f"refund.{refund.status}:{refund.pk}", amount_cents=refund.amount_cents
        )
    if not succeeded:
        record_audit(
            None, "payment.refund.failed", payment, {"refund_id": str(refund.pk), "code": refund.failure_code}
        )
    return f"refund_{refund.status}"


def _refresh_refund_status(payment: Payment) -> None:
    refunds = list(payment.refunds.all())
    if any(r.status == RefundRecordStatus.PENDING for r in refunds):
        status = RefundStatus.PENDING
    elif payment.refunded_amount_cents >= payment.amount_cents:
        status = RefundStatus.FULL
    elif payment.refunded_amount_cents > 0:
        status = RefundStatus.PARTIAL
    elif any(r.status == RefundRecordStatus.FAILED for r in refunds):
        status = RefundStatus.FAILED
    else:
        status = RefundStatus.NONE
    if payment.refund_status != status:
        payment.refund_status = status
        payment.save(update_fields=["refund_status", "updated_at"])


def on_booking_cancelled(booking, *, actor=None) -> None:
    """Apply the cancellation's money outcome: release an authorisation or refund a capture."""
    from apps.bookings.models import RefundOutcome

    if booking.price_cents == 0:
        return
    release_for_booking(booking, reason="booking_cancelled")
    if booking.refund_outcome != RefundOutcome.FULL_REFUND:
        return
    payment = Payment.objects.filter(booking=booking, status=PaymentStatus.CAPTURED).first()
    if payment is None or refundable_cents(payment) == 0:
        return
    is_mentor = actor is not None and actor.pk == booking.mentor.user_id
    reason = RefundReason.MENTOR_CANCELLATION if is_mentor else RefundReason.STUDENT_CANCELLATION
    if actor is not None and getattr(actor, "role", "") == "admin":
        reason = RefundReason.ADMIN
    # After commit, so the cancellation stands even if the provider is down. `robust`: a failure is
    # logged (and the payment stays refundable by an admin) instead of failing the request.
    transaction.on_commit(
        lambda: create_refund(payment, amount_cents=None, reason=reason, actor=None), robust=True
    )


# --- notifications ----------------------------------------------------------------------------


def _notify_payment(payment: Payment, template: str, *, key: str, amount_cents: int | None = None) -> None:
    from apps.common.serializers import money
    from apps.notifications.services import local_time, notify

    booking = payment.booking
    student = booking.student
    amount = money(amount_cents if amount_cents is not None else payment.amount_cents, payment.currency)
    context = {
        "service_title": booking.service_title,
        "mentor_name": booking.mentor.user.full_name,
        "when": local_time(booking.start_at, student),
        "hold_until": local_time(booking.hold_expires_at, student) if booking.hold_expires_at else "",
        "amount": f"{amount['amount_cents'] / 100:,.2f} {amount['currency']}",
    }
    notify(template, student, context, dedupe_key=key)
