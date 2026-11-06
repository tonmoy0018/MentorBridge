from django.conf import settings
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField, RangeBoundary, RangeOperators
from django.db import models
from django.db.models import F, Func, Q

from apps.common.models import TimeStampedModel, UUIDModel


class TsTzRange(Func):
    function = "TSTZRANGE"
    output_field = DateTimeRangeField()


class BookingStatus(models.TextChoices):
    PENDING_PAYMENT = "pending_payment", "Awaiting payment"
    REQUESTED = "requested", "Awaiting mentor"
    CONFIRMED = "confirmed", "Confirmed"
    COMPLETED = "completed", "Completed"
    DECLINED = "declined", "Declined"
    CANCELLED = "cancelled", "Cancelled"
    EXPIRED = "expired", "Expired"


# Statuses that hold a time slot. The exclusion constraints below only consider these.
ACTIVE_STATUSES = (BookingStatus.PENDING_PAYMENT, BookingStatus.REQUESTED, BookingStatus.CONFIRMED)

# The only allowed state transitions (docs/PRODUCT_REQUIREMENTS.md §6.1).
TRANSITIONS: dict[str, frozenset[str]] = {
    BookingStatus.PENDING_PAYMENT: frozenset(
        {BookingStatus.REQUESTED, BookingStatus.CONFIRMED, BookingStatus.CANCELLED, BookingStatus.EXPIRED}
    ),
    BookingStatus.REQUESTED: frozenset(
        {BookingStatus.CONFIRMED, BookingStatus.DECLINED, BookingStatus.CANCELLED, BookingStatus.EXPIRED}
    ),
    BookingStatus.CONFIRMED: frozenset({BookingStatus.COMPLETED, BookingStatus.CANCELLED}),
    BookingStatus.COMPLETED: frozenset(),
    BookingStatus.DECLINED: frozenset(),
    BookingStatus.CANCELLED: frozenset(),
    BookingStatus.EXPIRED: frozenset(),
}


class RefundOutcome(models.TextChoices):
    NOT_APPLICABLE = "", "Not applicable"
    NOT_CHARGED = "not_charged", "Not charged"
    FULL_REFUND = "full_refund", "Full refund"
    NO_REFUND = "no_refund", "No refund"


class Booking(UUIDModel, TimeStampedModel):
    """
    One session between a student and a mentor. Service details and price are snapshotted
    at booking time. `blocked_until` = end + mentor buffer; PostgreSQL exclusion constraints
    reject any overlap of active bookings for the same mentor (including buffer) or the same
    student, regardless of application code.
    """

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="bookings")
    mentor = models.ForeignKey("mentors.MentorProfile", on_delete=models.PROTECT, related_name="bookings")
    service = models.ForeignKey("mentors.MentorService", on_delete=models.PROTECT, related_name="bookings")

    service_title = models.CharField(max_length=120)
    duration_minutes = models.PositiveSmallIntegerField()
    price_cents = models.PositiveIntegerField()
    currency = models.CharField(max_length=3)

    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    blocked_until = models.DateTimeField()

    status = models.CharField(max_length=20, choices=BookingStatus.choices)
    student_note = models.TextField(max_length=1000, blank=True)
    meeting_url = models.URLField(max_length=300, blank=True)

    hold_expires_at = models.DateTimeField(null=True, blank=True)
    respond_by = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    cancellation_reason = models.TextField(max_length=1000, blank=True)
    refund_outcome = models.CharField(max_length=16, choices=RefundOutcome.choices, blank=True, default="")

    class Meta:
        ordering = ["start_at"]
        constraints = [
            models.CheckConstraint(condition=Q(end_at__gt=F("start_at")), name="booking_end_after_start"),
            models.CheckConstraint(
                condition=Q(blocked_until__gte=F("end_at")), name="booking_blocked_after_end"
            ),
            models.CheckConstraint(condition=Q(status__in=BookingStatus.values), name="booking_status_valid"),
            ExclusionConstraint(
                name="booking_no_mentor_overlap",
                expressions=[
                    ("mentor", RangeOperators.EQUAL),
                    (TsTzRange("start_at", "blocked_until", RangeBoundary()), RangeOperators.OVERLAPS),
                ],
                condition=Q(status__in=ACTIVE_STATUSES),
            ),
            ExclusionConstraint(
                name="booking_no_student_overlap",
                expressions=[
                    ("student", RangeOperators.EQUAL),
                    (TsTzRange("start_at", "end_at", RangeBoundary()), RangeOperators.OVERLAPS),
                ],
                condition=Q(status__in=ACTIVE_STATUSES),
            ),
        ]
        indexes = [
            models.Index(fields=["student", "start_at"]),
            models.Index(fields=["mentor", "start_at"]),
            models.Index(fields=["status", "hold_expires_at"]),
            models.Index(fields=["status", "respond_by"]),
        ]

    def __str__(self) -> str:
        return f"{self.service_title} @ {self.start_at:%Y-%m-%d %H:%M} ({self.status})"

    def is_participant(self, user) -> bool:
        return user.pk == self.student_id or user.pk == self.mentor.user_id


class BookingEvent(models.Model):
    """Append-only audit trail of status changes."""

    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="events")
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    note = models.TextField(max_length=1000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self) -> str:
        return f"{self.from_status or 'new'} → {self.to_status}"
