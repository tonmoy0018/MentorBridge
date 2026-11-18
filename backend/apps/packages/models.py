"""
Session bundles ("packages"): a mentor offers N sessions of one service at a discount, used within
a validity period. A student's PackagePurchase snapshots the terms; each session is an ordinary
Booking linked to the purchase (with price 0, since the package covers it).

Credits are derived from the bookings, never stored: a session counts as used while it is active
or completed, or when the student cancelled too late for a refund. Declined, expired and other
cancelled sessions give the credit back.
"""

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Count, Q

from apps.common.models import TimeStampedModel, UUIDModel
from apps.mentors.models import SessionFormat

MIN_SESSIONS, MAX_SESSIONS = 2, 24
MIN_VALIDITY_DAYS, MAX_VALIDITY_DAYS = 7, 365


MAX_DISCOUNT_PERCENT = 50


class MentorPackage(UUIDModel, TimeStampedModel):
    """
    A multi-session option of one service: `session_count` sessions with `discount_percent` off,
    to be used within `validity_days`. The price follows the service's price in whichever format
    (online or in person) the student chooses; see `price_cents`.
    """

    mentor = models.ForeignKey("mentors.MentorProfile", on_delete=models.CASCADE, related_name="packages")
    service = models.ForeignKey("mentors.MentorService", on_delete=models.PROTECT, related_name="packages")
    session_count = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(MIN_SESSIONS), MaxValueValidator(MAX_SESSIONS)]
    )
    discount_percent = models.PositiveSmallIntegerField(
        default=0, validators=[MaxValueValidator(MAX_DISCOUNT_PERCENT)]
    )
    validity_days = models.PositiveSmallIntegerField(
        default=60, validators=[MinValueValidator(MIN_VALIDITY_DAYS), MaxValueValidator(MAX_VALIDITY_DAYS)]
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["session_count"]
        constraints = [
            models.CheckConstraint(
                condition=Q(session_count__gte=MIN_SESSIONS, session_count__lte=MAX_SESSIONS),
                name="package_session_count_range",
            ),
            models.CheckConstraint(
                condition=Q(validity_days__gte=MIN_VALIDITY_DAYS, validity_days__lte=MAX_VALIDITY_DAYS),
                name="package_validity_range",
            ),
            models.CheckConstraint(
                condition=Q(discount_percent__lte=MAX_DISCOUNT_PERCENT), name="package_discount_range"
            ),
            models.UniqueConstraint(fields=["service", "session_count"], name="package_unique_per_service"),
        ]
        indexes = [models.Index(fields=["mentor", "is_active"])]

    def __str__(self) -> str:
        return self.title

    @property
    def title(self) -> str:
        return f"{self.session_count} × {self.service.title}"

    def regular_cents(self, session_format: str) -> int:
        return self.service.price_for(session_format) * self.session_count

    def price_cents(self, session_format: str) -> int:
        """Rounded to the cent; never more than the sessions booked one by one."""
        return round(self.regular_cents(session_format) * (100 - self.discount_percent) / 100)


def used_sessions_q(prefix: str = "") -> Q:
    """Bookings that consume a package credit (see module docstring)."""
    from apps.bookings.models import ACTIVE_STATUSES, BookingStatus, RefundOutcome

    return Q(**{f"{prefix}status__in": [*ACTIVE_STATUSES, BookingStatus.COMPLETED]}) | Q(
        **{f"{prefix}status": BookingStatus.CANCELLED, f"{prefix}refund_outcome": RefundOutcome.NO_REFUND}
    )


class PackagePurchaseQuerySet(models.QuerySet):
    def with_usage(self):
        return self.annotate(sessions_used=Count("bookings", filter=used_sessions_q("bookings__")))


class PurchaseStatus(models.TextChoices):
    PENDING_PAYMENT = "pending_payment", "Awaiting payment"
    ACTIVE = "active", "Active"
    CANCELLED = "cancelled", "Cancelled"  # checkout expired or abandoned; nothing charged
    REFUNDED = "refunded", "Refunded"


class PackagePurchase(UUIDModel, TimeStampedModel):
    """
    A student's bundle. Terms are snapshotted, so later edits never change it. Paid bundles start
    `pending_payment` and become `active` (usable, with `expires_at` set) only when the payment
    provider confirms the payment.
    """

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="package_purchases"
    )
    package = models.ForeignKey(MentorPackage, on_delete=models.PROTECT, related_name="purchases")
    mentor = models.ForeignKey("mentors.MentorProfile", on_delete=models.PROTECT, related_name="+")
    service = models.ForeignKey("mentors.MentorService", on_delete=models.PROTECT, related_name="+")
    format = models.CharField(max_length=10, choices=SessionFormat.choices)
    title = models.CharField(max_length=120)
    session_count = models.PositiveSmallIntegerField()
    duration_minutes = models.PositiveSmallIntegerField()
    price_cents = models.PositiveIntegerField()
    currency = models.CharField(max_length=3)
    status = models.CharField(max_length=16, choices=PurchaseStatus.choices, default=PurchaseStatus.ACTIVE)
    expires_at = models.DateTimeField(null=True, blank=True, help_text="Set when the bundle becomes active.")

    objects = PackagePurchaseQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["student", "expires_at"])]

    def __str__(self) -> str:
        return f"{self.title} for {self.student_id}"

    def used_count(self) -> int:
        return self.bookings.filter(used_sessions_q()).count()
