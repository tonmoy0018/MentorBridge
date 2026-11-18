"""
Group seminars: a mentor runs one of their services for several students at a fixed time.

Each student's seat is an ordinary Booking linked to the seminar (`Booking.seminar`), so
payments, refunds, cancellations, reminders and reviews work exactly as for one-to-one
sessions. The seminar itself blocks the mentor's calendar; the per-mentor overlap constraint on
Booking skips seminar registrations, and the student overlap constraint still applies.
"""

from django.db import models
from django.db.models import F, Q

from apps.common.models import TimeStampedModel, UUIDModel
from apps.mentors.models import ALLOWED_DURATIONS, MAX_PRICE_CENTS, SessionFormat

MIN_CAPACITY, MAX_CAPACITY = 2, 100


class SeminarStatus(models.TextChoices):
    SCHEDULED = "scheduled", "Scheduled"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


class Seminar(UUIDModel, TimeStampedModel):
    mentor = models.ForeignKey("mentors.MentorProfile", on_delete=models.CASCADE, related_name="seminars")
    service = models.ForeignKey("mentors.MentorService", on_delete=models.PROTECT, related_name="seminars")
    title = models.CharField(max_length=120)
    description = models.TextField(max_length=1000, blank=True)
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    duration_minutes = models.PositiveSmallIntegerField()
    capacity = models.PositiveSmallIntegerField()
    price_cents = models.PositiveIntegerField(help_text="Per seat.")
    currency = models.CharField(max_length=3)
    format = models.CharField(max_length=10, choices=SessionFormat.choices, default=SessionFormat.ONLINE)
    in_person_area = models.CharField(max_length=120, blank=True)
    # Private: shown only to registered students with a confirmed seat (and the mentor).
    meeting_place = models.CharField(max_length=300, blank=True)
    meeting_url = models.URLField(max_length=300, blank=True, help_text="Defaults to the mentor's link.")
    status = models.CharField(max_length=10, choices=SeminarStatus.choices, default=SeminarStatus.SCHEDULED)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(max_length=1000, blank=True)

    class Meta:
        ordering = ["start_at"]
        constraints = [
            models.CheckConstraint(condition=Q(end_at__gt=F("start_at")), name="seminar_end_after_start"),
            models.CheckConstraint(
                condition=Q(capacity__gte=MIN_CAPACITY, capacity__lte=MAX_CAPACITY),
                name="seminar_capacity_range",
            ),
            models.CheckConstraint(condition=Q(price_cents__lte=MAX_PRICE_CENTS), name="seminar_price_range"),
            models.CheckConstraint(
                condition=Q(duration_minutes__in=ALLOWED_DURATIONS), name="seminar_duration_allowed"
            ),
            models.CheckConstraint(condition=Q(format__in=SessionFormat.values), name="seminar_format_valid"),
            models.CheckConstraint(condition=Q(status__in=SeminarStatus.values), name="seminar_status_valid"),
        ]
        indexes = [models.Index(fields=["mentor", "status", "start_at"])]

    def __str__(self) -> str:
        return f"{self.title} @ {self.start_at:%Y-%m-%d %H:%M} ({self.status})"
