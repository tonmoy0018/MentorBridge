"""
Booking lifecycle. All state changes go through `_transition`, which enforces TRANSITIONS
and writes a BookingEvent. Creation runs in a transaction that locks the mentor row, so
concurrent requests for one mentor are serialised; the exclusion constraints are the final
guarantee against overlaps (including across mentors for the same student).
"""

import logging
from datetime import UTC, datetime, timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.common.exceptions import Conflict, DomainError, ServiceUnavailable
from apps.mentors.models import MentorProfile, MentorService
from apps.mentors.selectors import bookable_slots

from . import notifications
from .models import TRANSITIONS, Booking, BookingEvent, BookingStatus, RefundOutcome

logger = logging.getLogger(__name__)

CONSTRAINT_ERRORS = {
    "booking_no_mentor_overlap": (
        "slot_unavailable",
        "That time is no longer available. Please choose another.",
    ),
    "booking_no_student_overlap": ("student_busy", "You already have a session booked at that time."),
}


def _transition(booking: Booking, to: str, *, actor=None, note: str = "", **fields) -> Booking:
    if to not in TRANSITIONS[booking.status]:
        raise Conflict(
            "invalid_state", f"A {booking.get_status_display().lower()} booking can't be changed that way."
        )
    previous = booking.status
    booking.status = to
    for name, value in fields.items():
        setattr(booking, name, value)
    booking.save()
    BookingEvent.objects.create(
        booking=booking, from_status=previous, to_status=to, actor=actor, note=note[:1000]
    )
    return booking


def _lock(booking: Booking) -> Booking:
    return Booking.objects.select_for_update().select_related("mentor__user", "student").get(pk=booking.pk)


def _constraint_name(exc: IntegrityError) -> str | None:
    diag = getattr(getattr(exc, "__cause__", None), "diag", None)
    return getattr(diag, "constraint_name", None)


# --- creation ---------------------------------------------------------------------------


def create_booking(*, student, service_id, start_at: datetime, student_note: str = "", now=None) -> Booking:
    """
    Book `service_id` at `start_at` for `student`. The price, duration and title come from the
    service on the server — never from the client.
    """
    now = now or timezone.now()
    service = MentorService.objects.select_related("mentor__user").filter(pk=service_id).first()
    if service is None or not service.mentor.is_publicly_visible:
        raise NotFound("Service not found.")
    mentor = service.mentor
    if not service.is_active:
        raise Conflict("service_unavailable", "This service is no longer offered.")
    if not mentor.is_accepting_bookings:
        raise Conflict("not_accepting_bookings", "This mentor isn't accepting new bookings right now.")
    if settings.REQUIRE_VERIFIED_EMAIL and not student.email_verified:
        raise DomainError("email_not_verified", "Verify your email address before booking.", status_code=403)
    if service.price_cents > 0 and not settings.PAYMENTS_ENABLED:
        # A hold could never be paid, so don't create one (it would also block the slot).
        raise ServiceUnavailable(
            "payments_unavailable", "Paid sessions can't be booked until online payment is available."
        )

    start_at = start_at.astimezone(UTC)
    if start_at.second or start_at.microsecond:
        raise Conflict("slot_unavailable", "That time isn't one of the mentor's available slots.")
    end_at = start_at + timedelta(minutes=service.duration_minutes)
    blocked_until = end_at + timedelta(minutes=mentor.buffer_minutes)

    with transaction.atomic():
        # Serialise bookings for this mentor; concurrent requests wait here.
        MentorProfile.objects.select_for_update().get(pk=mentor.pk)
        expire_due(now=now, mentor=mentor, student=student)

        slots = bookable_slots(
            mentor,
            duration_minutes=service.duration_minutes,
            window_start=start_at,
            window_end=start_at + timedelta(minutes=1),
            now=now,
        )
        if start_at not in slots:
            raise Conflict("slot_unavailable", "That time is no longer available. Please choose another.")

        if service.price_cents > 0:
            status = BookingStatus.PENDING_PAYMENT
        else:
            status = BookingStatus.CONFIRMED if mentor.auto_accept else BookingStatus.REQUESTED
        booking = Booking(
            student=student,
            mentor=mentor,
            service=service,
            service_title=service.title,
            duration_minutes=service.duration_minutes,
            price_cents=service.price_cents,
            currency=service.currency,
            start_at=start_at,
            end_at=end_at,
            blocked_until=blocked_until,
            status=status,
            student_note=student_note.strip(),
        )
        if status == BookingStatus.PENDING_PAYMENT:
            booking.hold_expires_at = now + timedelta(minutes=settings.BOOKING_HOLD_MINUTES)
        elif status == BookingStatus.REQUESTED:
            booking.respond_by = min(now + timedelta(hours=settings.MENTOR_RESPONSE_HOURS), start_at)
        else:
            booking.confirmed_at = now
            booking.meeting_url = mentor.meeting_url

        try:
            with transaction.atomic():  # savepoint, so the outer transaction stays usable
                booking.save()
        except IntegrityError as exc:
            code, message = CONSTRAINT_ERRORS.get(
                _constraint_name(exc) or "", ("conflict", "Booking conflict.")
            )
            raise Conflict(code, message) from exc
        BookingEvent.objects.create(booking=booking, from_status="", to_status=status, actor=student)
        if status == BookingStatus.REQUESTED:
            notifications.requested(booking)
        elif status == BookingStatus.CONFIRMED:
            notifications.confirmed(booking)
    logger.info("Booking %s created (%s) for mentor %s", booking.pk, status, mentor.pk)
    return booking


# --- mentor actions ---------------------------------------------------------------------


def _require_mentor(booking: Booking, actor) -> None:
    if booking.mentor.user_id != actor.pk:
        raise PermissionDenied("Only the mentor for this booking can do that.")


@transaction.atomic
def accept_booking(booking: Booking, *, actor, now=None) -> Booking:
    now = now or timezone.now()
    booking = _lock(booking)
    _require_mentor(booking, actor)
    if booking.status == BookingStatus.REQUESTED and booking.start_at <= now:
        raise Conflict("invalid_state", "This session has already started.")
    if booking.status != BookingStatus.REQUESTED:
        raise Conflict("invalid_state", "Only booking requests can be accepted.")
    if booking.price_cents > 0:
        # Paid requests exist only once the provider has authorised payment. The money is captured
        # here, through the provider; a failed capture leaves the request untouched.
        from apps.payments.services import capture_for_booking

        capture_for_booking(booking)
    booking = _transition(
        booking,
        BookingStatus.CONFIRMED,
        actor=actor,
        confirmed_at=now,
        respond_by=None,
        meeting_url=booking.mentor.meeting_url,
    )
    notifications.confirmed(booking)
    return booking


def payment_authorized(booking: Booking, payment) -> Booking:
    """
    Called (inside the webhook transaction) when the provider confirms a card authorisation for a
    held booking: the request goes to the mentor, or is confirmed and captured if they auto-accept.
    """
    now = timezone.now()
    booking = _lock(booking)
    if booking.mentor.auto_accept:
        from apps.payments.services import PaymentProviderError, capture_for_booking

        try:
            capture_for_booking(booking)
        except PaymentProviderError:
            logger.warning("Auto-accept capture failed for booking %s; leaving it for the mentor", booking.pk)
        else:
            booking = _transition(
                booking,
                BookingStatus.CONFIRMED,
                note="Paid; auto-accepted.",
                confirmed_at=now,
                hold_expires_at=None,
                meeting_url=booking.mentor.meeting_url,
            )
            notifications.confirmed(booking)
            return booking
    booking = _transition(
        booking,
        BookingStatus.REQUESTED,
        note="Payment authorised by the provider.",
        hold_expires_at=None,
        respond_by=min(now + timedelta(hours=settings.MENTOR_RESPONSE_HOURS), booking.start_at),
    )
    notifications.requested(booking)
    return booking


@transaction.atomic
def decline_booking(booking: Booking, *, actor, reason: str) -> Booking:
    booking = _lock(booking)
    _require_mentor(booking, actor)
    if not reason.strip():
        raise ValidationError({"reason": ["Tell the student why you're declining."]})
    booking = _transition(
        booking,
        BookingStatus.DECLINED,
        actor=actor,
        note=reason,
        respond_by=None,
        cancellation_reason=reason.strip(),
        refund_outcome=RefundOutcome.NOT_CHARGED if booking.price_cents else RefundOutcome.NOT_APPLICABLE,
    )
    from apps.payments.services import release_for_booking

    release_for_booking(booking, reason="declined")
    notifications.declined(booking)
    return booking


@transaction.atomic
def complete_booking(booking: Booking, *, actor, now=None) -> Booking:
    now = now or timezone.now()
    booking = _lock(booking)
    _require_mentor(booking, actor)
    if booking.status == BookingStatus.CONFIRMED and booking.start_at > now:
        raise Conflict("invalid_state", "A session can only be completed after it has started.")
    return _transition(booking, BookingStatus.COMPLETED, actor=actor, completed_at=now)


# --- cancellation -----------------------------------------------------------------------


def cancellation_outcome(booking: Booking, *, by_mentor: bool, now: datetime) -> str:
    """Refund policy (docs/PRODUCT_REQUIREMENTS.md §6.3)."""
    if booking.price_cents == 0:
        return RefundOutcome.NOT_APPLICABLE
    if booking.status in (BookingStatus.PENDING_PAYMENT, BookingStatus.REQUESTED):
        return RefundOutcome.NOT_CHARGED
    if by_mentor:
        return RefundOutcome.FULL_REFUND
    notice = booking.start_at - now
    return (
        RefundOutcome.FULL_REFUND
        if notice >= timedelta(hours=settings.FREE_CANCELLATION_HOURS)
        else RefundOutcome.NO_REFUND
    )


@transaction.atomic
def cancel_booking(booking: Booking, *, actor, reason: str = "", now=None) -> Booking:
    now = now or timezone.now()
    booking = _lock(booking)
    by_mentor = booking.mentor.user_id == actor.pk
    if not by_mentor and booking.student_id != actor.pk:
        raise PermissionDenied("You can't cancel this booking.")
    if booking.start_at <= now:
        raise Conflict("invalid_state", "Sessions can't be cancelled after they've started.")
    if by_mentor:
        if booking.status == BookingStatus.REQUESTED:
            raise Conflict("invalid_state", "Decline the request instead of cancelling it.")
        if not reason.strip():
            raise ValidationError({"reason": ["Tell the student why you're cancelling."]})

    outcome = cancellation_outcome(booking, by_mentor=by_mentor, now=now)
    booking = _transition(
        booking,
        BookingStatus.CANCELLED,
        actor=actor,
        note=reason,
        cancelled_at=now,
        cancelled_by=actor,
        cancellation_reason=reason.strip(),
        refund_outcome=outcome,
        meeting_url="",
    )
    from apps.payments.services import on_booking_cancelled

    on_booking_cancelled(booking, actor=actor)
    notifications.cancelled(booking, actor=actor)
    return booking


@transaction.atomic
def admin_cancel_booking(booking: Booking, *, actor, reason: str, refund: bool, now=None) -> Booking:
    """An administrator cancels any active booking, optionally refunding a captured payment in full."""
    from apps.common.models import record_audit

    now = now or timezone.now()
    booking = _lock(booking)
    if not reason.strip():
        raise ValidationError({"reason": ["Record why the booking is being cancelled."]})
    if booking.price_cents == 0:
        outcome = RefundOutcome.NOT_APPLICABLE
    elif booking.status in (BookingStatus.PENDING_PAYMENT, BookingStatus.REQUESTED):
        outcome = RefundOutcome.NOT_CHARGED
    else:
        outcome = RefundOutcome.FULL_REFUND if refund else RefundOutcome.NO_REFUND
    booking = _transition(
        booking,
        BookingStatus.CANCELLED,
        actor=actor,
        note=f"Cancelled by an administrator: {reason}",
        cancelled_at=now,
        cancelled_by=actor,
        cancellation_reason=reason.strip(),
        refund_outcome=outcome,
        meeting_url="",
    )
    from apps.payments.services import on_booking_cancelled

    on_booking_cancelled(booking, actor=actor)
    notifications.cancelled(booking, actor=actor)
    record_audit(actor, "booking.cancelled_by_admin", booking, {"refund": refund, "outcome": outcome})
    return booking


def expire_booking(booking: Booking, *, note: str) -> Booking | None:
    """Expire one held booking or unanswered request (used by webhooks and the scheduler)."""
    booking = _lock(booking)
    if booking.status not in (BookingStatus.PENDING_PAYMENT, BookingStatus.REQUESTED):
        return None
    was_request = booking.status == BookingStatus.REQUESTED
    booking = _transition(booking, BookingStatus.EXPIRED, note=note)
    from apps.payments.services import release_for_booking

    release_for_booking(booking, reason="expired")
    if was_request:
        notifications.expired(booking)
    return booking


# --- expiry -----------------------------------------------------------------------------


def expire_due(*, now=None, mentor=None, student=None) -> int:
    """
    Expire lapsed payment holds and unanswered requests. Runs from the scheduler
    (`manage.py expire_bookings`) and lazily before each booking is created.
    """
    now = now or timezone.now()
    # Payment holds get a short grace period so a payment completed at the last second (whose
    # webhook may arrive slightly later) still finds its booking.
    hold_cutoff = now - timedelta(minutes=settings.PAYMENT_WEBHOOK_GRACE_MINUTES)
    due = Q(status=BookingStatus.PENDING_PAYMENT, hold_expires_at__lte=hold_cutoff) | Q(
        Q(respond_by__lte=now) | Q(start_at__lte=now), status=BookingStatus.REQUESTED
    )
    qs = Booking.objects.filter(due)
    if mentor is not None or student is not None:
        scope = Q()
        if mentor is not None:
            scope |= Q(mentor=mentor)
        if student is not None:
            scope |= Q(student=student)
        qs = qs.filter(scope)
    count = 0
    with transaction.atomic():
        for booking in qs.select_for_update(skip_locked=True):
            if expire_booking(booking, note="Expired automatically.") is not None:
                count += 1
    return count
