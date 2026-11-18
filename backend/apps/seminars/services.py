"""Seminar operations. Every write goes through here; views stay thin."""

import logging
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.bookings import notifications
from apps.bookings.models import ACTIVE_STATUSES, Booking, BookingEvent, BookingStatus, RefundOutcome
from apps.bookings.services import CONSTRAINT_ERRORS, _check_pending_limits, _constraint_name, _transition
from apps.common.exceptions import Conflict, DomainError, ServiceUnavailable
from apps.common.models import record_audit
from apps.mentors.models import MentorProfile, MentorService, SessionFormat
from apps.mentors.services import _check_currency, check_min_price

from .models import Seminar, SeminarStatus

logger = logging.getLogger(__name__)

MIN_NOTICE = timedelta(hours=1)
MAX_AHEAD = timedelta(days=365)
# Fields that can't change once anyone holds a seat: students registered for these terms.
LOCKED_WHEN_BOOKED = {"start_at", "duration_minutes", "price_cents", "format", "service_id"}


def seats_taken(seminar: Seminar) -> int:
    return seminar.registrations.filter(status__in=ACTIVE_STATUSES).count()


def _check_times(seminar: Seminar, now) -> None:
    if seminar.start_at < now + MIN_NOTICE:
        raise ValidationError({"start_at": "Schedule the seminar at least an hour from now."})
    if seminar.start_at > now + MAX_AHEAD:
        raise ValidationError({"start_at": "Schedule the seminar within the next year."})
    seminar.end_at = seminar.start_at + timedelta(minutes=seminar.duration_minutes)


def _check_free(seminar: Seminar) -> None:
    """The mentor must be free (with buffer). Call with the mentor row locked."""
    buffer = timedelta(minutes=seminar.mentor.buffer_minutes)
    clash = Booking.objects.filter(
        mentor=seminar.mentor,
        status__in=ACTIVE_STATUSES,
        seminar__isnull=True,
        start_at__lt=seminar.end_at + buffer,
        blocked_until__gt=seminar.start_at,
    ).exclude(status=BookingStatus.PENDING_PAYMENT, hold_expires_at__lt=timezone.now())
    if clash.exists():
        raise Conflict("mentor_busy", "You have a session booked at that time.")
    other = Seminar.objects.filter(
        mentor=seminar.mentor,
        status=SeminarStatus.SCHEDULED,
        start_at__lt=seminar.end_at + buffer,
        end_at__gt=seminar.start_at - buffer,
    ).exclude(pk=seminar.pk)
    if other.exists():
        raise Conflict("mentor_busy", "You have another seminar at that time.")


def _check_details(seminar: Seminar) -> None:
    check_min_price(seminar.price_cents)
    if seminar.format == SessionFormat.IN_PERSON:
        seminar.in_person_area = seminar.in_person_area.strip()
        if len(seminar.in_person_area) < 3:
            raise ValidationError(
                {"in_person_area": "Say where the seminar takes place, e.g. a neighbourhood."}
            )
    else:
        seminar.in_person_area = ""


@transaction.atomic
def create_seminar(mentor: MentorProfile, data: dict, *, now=None) -> Seminar:
    now = now or timezone.now()
    data = dict(data)
    service = MentorService.objects.filter(pk=data.pop("service_id"), mentor=mentor, is_active=True).first()
    if service is None:
        raise ValidationError({"service_id": "Choose one of your active services."})
    mentor = MentorProfile.objects.select_for_update().get(pk=mentor.pk)  # serialise with bookings
    seminar = Seminar(
        mentor=mentor,
        service=service,
        title=data.pop("title", "") or service.title,
        currency=_check_currency(data.pop("currency", None)),
        **data,
    )
    _check_details(seminar)
    _check_times(seminar, now)
    _check_free(seminar)
    seminar.save()
    return seminar


@transaction.atomic
def update_seminar(seminar: Seminar, data: dict, *, now=None) -> Seminar:
    now = now or timezone.now()
    MentorProfile.objects.select_for_update().get(pk=seminar.mentor_id)
    seminar = Seminar.objects.select_for_update().select_related("mentor").get(pk=seminar.pk)
    if seminar.status != SeminarStatus.SCHEDULED:
        raise Conflict("invalid_state", "Only scheduled seminars can be changed.")
    data = dict(data)
    taken = seats_taken(seminar)
    if "service_id" in data:
        service = MentorService.objects.filter(pk=data["service_id"], mentor=seminar.mentor).first()
        if service is None:
            raise ValidationError({"service_id": "Choose one of your own services."})
    changing = {k for k, v in data.items() if getattr(seminar, k) != v}
    if taken and changing & LOCKED_WHEN_BOOKED:
        raise Conflict(
            "seminar_has_registrations",
            "Students have registered, so the time, length, price and format can't change. "
            "Cancel the seminar and schedule a new one instead.",
        )
    if data.get("capacity", seminar.capacity) < taken:
        raise ValidationError({"capacity": f"{taken} students have already registered."})
    for field, value in data.items():
        setattr(seminar, field, value)
    _check_details(seminar)
    if {"start_at", "duration_minutes"} & changing:
        _check_times(seminar, now)
        _check_free(seminar)
    seminar.save()
    return seminar


def _cancel_seat(booking: Booking, *, actor, reason: str, now) -> None:
    if booking.price_cents == 0:
        outcome = RefundOutcome.NOT_APPLICABLE
    elif booking.status in (BookingStatus.PENDING_PAYMENT, BookingStatus.REQUESTED):
        outcome = RefundOutcome.NOT_CHARGED
    else:
        outcome = RefundOutcome.FULL_REFUND
    booking = _transition(
        booking,
        BookingStatus.CANCELLED,
        actor=actor,
        note=f"Seminar cancelled: {reason}",
        cancelled_at=now,
        cancelled_by=actor,
        cancellation_reason=reason,
        refund_outcome=outcome,
        meeting_url="",
    )
    from apps.payments.services import on_booking_cancelled

    on_booking_cancelled(booking, actor=actor)
    notifications.seminar_cancelled(booking)


@transaction.atomic
def cancel_seminar(seminar: Seminar, *, actor, reason: str, request=None, now=None) -> Seminar:
    """Cancel a seminar: every seat is cancelled and refunded in full, and each student is told once."""
    now = now or timezone.now()
    reason = reason.strip()
    if not reason:
        raise ValidationError({"reason": ["Tell the students why you're cancelling."]})
    seminar = Seminar.objects.select_for_update().get(pk=seminar.pk)
    if seminar.status != SeminarStatus.SCHEDULED:
        raise Conflict("invalid_state", "This seminar can't be cancelled.")
    if seminar.start_at <= now:
        raise Conflict("invalid_state", "Seminars can't be cancelled after they've started.")
    seats = (
        Booking.objects.select_for_update()
        .select_related("mentor__user", "student", "seminar")
        .filter(seminar=seminar, status__in=ACTIVE_STATUSES)
    )
    for booking in seats:
        _cancel_seat(booking, actor=actor, reason=reason, now=now)
    seminar.status = SeminarStatus.CANCELLED
    seminar.cancelled_at, seminar.cancellation_reason = now, reason
    seminar.save()
    if actor.pk != seminar.mentor.user_id:
        record_audit(actor, "seminar.cancelled_by_admin", seminar, {"seats": len(seats)}, request)
    return seminar


@transaction.atomic
def complete_seminar(seminar: Seminar, *, actor, now=None) -> Seminar:
    """After it has started: confirmed seats are completed (so students can review)."""
    now = now or timezone.now()
    seminar = Seminar.objects.select_for_update().get(pk=seminar.pk)
    if seminar.status != SeminarStatus.SCHEDULED:
        raise Conflict("invalid_state", "This seminar is already closed.")
    if seminar.start_at > now:
        raise Conflict("invalid_state", "A seminar can only be completed after it has started.")
    for booking in Booking.objects.select_for_update().filter(
        seminar=seminar, status=BookingStatus.CONFIRMED
    ):
        _transition(booking, BookingStatus.COMPLETED, actor=actor, completed_at=now)
    seminar.status = SeminarStatus.COMPLETED
    seminar.save()
    return seminar


def register(*, student, seminar_id, now=None) -> Booking:
    """Take a seat. Free seats are confirmed at once; paid seats are held until payment is verified."""
    now = now or timezone.now()
    seminar = Seminar.objects.select_related("mentor__user", "service").filter(pk=seminar_id).first()
    if seminar is None or not seminar.mentor.is_publicly_visible:
        raise DomainError("not_found", "Seminar not found.", status_code=404)
    if settings.REQUIRE_VERIFIED_EMAIL and not student.email_verified:
        raise DomainError("email_not_verified", "Verify your email address before booking.", status_code=403)
    if seminar.price_cents > 0 and not settings.PAYMENTS_ENABLED:
        raise ServiceUnavailable(
            "payments_unavailable", "Paid seminars can't be booked until online payment is available."
        )

    with transaction.atomic():
        # Locking the seminar serialises registrations, so two students can't take the last seat.
        seminar = Seminar.objects.select_for_update().select_related("mentor__user").get(pk=seminar.pk)
        if seminar.status != SeminarStatus.SCHEDULED or seminar.start_at <= now:
            raise Conflict("seminar_closed", "Registration for this seminar is closed.")
        from apps.bookings.services import expire_due

        expire_due(now=now, student=student)  # lapsed payment holds free their seats
        held = Booking.objects.filter(seminar=seminar, status__in=ACTIVE_STATUSES)
        if held.filter(student=student).exists():
            raise Conflict("already_registered", "You've already registered for this seminar.")
        if held.count() >= seminar.capacity:
            raise Conflict("seminar_full", "This seminar is full.")
        paid = seminar.price_cents > 0
        if paid:
            _check_pending_limits(student, seminar.mentor)

        booking = Booking(
            student=student,
            mentor=seminar.mentor,
            service=seminar.service,
            seminar=seminar,
            service_title=seminar.title,
            duration_minutes=seminar.duration_minutes,
            price_cents=seminar.price_cents,
            currency=seminar.currency,
            start_at=seminar.start_at,
            end_at=seminar.end_at,
            blocked_until=seminar.end_at,
            format=seminar.format,
            in_person_area=seminar.in_person_area,
            status=BookingStatus.PENDING_PAYMENT if paid else BookingStatus.CONFIRMED,
        )
        if paid:
            booking.hold_expires_at = now + timedelta(minutes=settings.BOOKING_HOLD_MINUTES)
        else:
            booking.confirmed_at = now
        try:
            with transaction.atomic():
                booking.save()
        except IntegrityError as exc:
            code, message = CONSTRAINT_ERRORS.get(
                _constraint_name(exc) or "", ("conflict", "Booking conflict.")
            )
            raise Conflict(code, message) from exc
        BookingEvent.objects.create(booking=booking, from_status="", to_status=booking.status, actor=student)
        if not paid:
            notifications.confirmed(booking)
    logger.info("Seminar %s: seat %s (%s)", seminar.pk, booking.pk, booking.status)
    return booking


def upcoming_public(mentor_ids, *, now=None):
    now = now or timezone.now()
    return Seminar.objects.filter(
        Q(mentor_id__in=mentor_ids), status=SeminarStatus.SCHEDULED, start_at__gt=now
    ).select_related("service")
