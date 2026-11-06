"""Booking emails (docs/NOTIFICATIONS.md). Each has a dedupe key, so re-processing never re-sends."""

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from apps.notifications.services import local_time, notify

from .models import Booking, RefundOutcome


def _price(booking: Booking) -> str:
    if booking.price_cents == 0:
        return ""
    return f"{booking.price_cents / 100:,.2f} {booking.currency}"


def _base(booking: Booking, recipient) -> dict:
    return {
        "service_title": booking.service_title,
        "mentor_name": booking.mentor.user.full_name,
        "student_name": booking.student.full_name,
        "when": local_time(booking.start_at, recipient),
        "paid": booking.price_cents > 0,
        "price": _price(booking),
        "free_cancellation_hours": settings.FREE_CANCELLATION_HOURS,
    }


def requested(booking: Booking) -> None:
    mentor_user = booking.mentor.user
    context = {
        **_base(booking, mentor_user),
        "note": booking.student_note,
        "respond_by": local_time(booking.respond_by, mentor_user) if booking.respond_by else "",
    }
    notify("booking_requested_mentor", mentor_user, context, dedupe_key=f"booking.requested:{booking.pk}")


def confirmed(booking: Booking) -> None:
    student, mentor_user = booking.student, booking.mentor.user
    notify(
        "booking_confirmed_student",
        student,
        _base(booking, student),
        dedupe_key=f"booking.confirmed:{booking.pk}:student",
    )
    notify(
        "booking_confirmed_mentor",
        mentor_user,
        _base(booking, mentor_user),
        dedupe_key=f"booking.confirmed:{booking.pk}:mentor",
    )


def declined(booking: Booking) -> None:
    student = booking.student
    context = {**_base(booking, student), "reason": booking.cancellation_reason}
    notify("booking_declined_student", student, context, dedupe_key=f"booking.declined:{booking.pk}")


REFUND_TEXT = {
    RefundOutcome.FULL_REFUND: (
        "A full refund is being processed; you'll get a separate email when it completes."
    ),
    RefundOutcome.NO_REFUND: (
        "This cancellation was inside the free-cancellation window before the session, "
        "so it isn't refunded under the cancellation policy."
    ),
    RefundOutcome.NOT_CHARGED: "No payment was taken for this booking.",
    RefundOutcome.NOT_APPLICABLE: "",
}


def cancelled(booking: Booking, *, actor) -> None:
    """Tell the participants who didn't cancel (both, if an admin cancelled)."""
    by_mentor = actor.pk == booking.mentor.user_id
    by_student = actor.pk == booking.student_id
    cancelled_by = "the mentor" if by_mentor else "the student" if by_student else "MentorBridge"
    recipients = []
    if not by_student:
        recipients.append(("student", booking.student))
    if not by_mentor:
        recipients.append(("mentor", booking.mentor.user))
    for role, user in recipients:
        context = {
            **_base(booking, user),
            "cancelled_by": cancelled_by,
            "reason": booking.cancellation_reason,
            "refund_text": REFUND_TEXT.get(booking.refund_outcome, "") if role == "student" else "",
        }
        notify("booking_cancelled", user, context, dedupe_key=f"booking.cancelled:{booking.pk}:{role}")


def expired(booking: Booking) -> None:
    student = booking.student
    notify(
        "booking_expired_student",
        student,
        _base(booking, student),
        dedupe_key=f"booking.expired:{booking.pk}",
    )


def send_session_reminders(*, hours_ahead: int = 24, now=None) -> int:
    """Remind both participants of confirmed sessions starting within `hours_ahead` hours. Idempotent."""
    from .models import BookingStatus

    now = now or timezone.now()
    upcoming = Booking.objects.filter(
        status=BookingStatus.CONFIRMED, start_at__gt=now, start_at__lte=now + timedelta(hours=hours_ahead)
    ).select_related("student", "mentor__user")
    sent = 0
    for booking in upcoming:
        for role, user, other in (
            ("student", booking.student, booking.mentor.user.full_name),
            ("mentor", booking.mentor.user, booking.student.full_name),
        ):
            context = {**_base(booking, user), "other_name": other}
            if notify("session_reminder", user, context, dedupe_key=f"booking.reminder:{booking.pk}:{role}"):
                sent += 1
    return sent
