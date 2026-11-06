"""
Payment records. Rows are created when a student starts checkout and are advanced ONLY by the
payment provider: signature-verified webhooks, or authenticated server-to-server API responses
(capture, cancel, refund). There is no API to set a payment's status, and Django admin shows
these rows read-only. No card numbers, CVCs or credentials are stored, only the provider's
opaque references. See docs/PAYMENTS.md.
"""

from django.conf import settings
from django.db import models
from django.db.models import F, Q

from apps.common.models import TimeStampedModel, UUIDModel


class PaymentStatus(models.TextChoices):
    CREATED = "created", "Checkout started"
    FAILED = "failed", "Attempt failed"  # the student can retry in the same checkout
    AUTHORIZED = "authorized", "Authorised"
    CAPTURED = "captured", "Captured"
    CANCELLED = "cancelled", "Cancelled"  # checkout expired or authorisation released


class RefundStatus(models.TextChoices):
    NONE = "none", "No refund"
    PENDING = "pending", "Refund pending"
    PARTIAL = "partial", "Partly refunded"
    FULL = "full", "Refunded"
    FAILED = "failed", "Refund failed"


class DisputeStatus(models.TextChoices):
    NONE = "none", "No dispute"
    OPEN = "open", "Dispute open"
    WON = "won", "Dispute won"
    LOST = "lost", "Dispute lost"


# A booking may have at most one payment in these states at a time.
OPEN_PAYMENT_STATUSES = (
    PaymentStatus.CREATED,
    PaymentStatus.FAILED,
    PaymentStatus.AUTHORIZED,
    PaymentStatus.CAPTURED,
)

# Allowed status changes. Anything else (e.g. a late "authorised" event after capture) is ignored.
PAYMENT_TRANSITIONS: dict[str, frozenset[str]] = {
    PaymentStatus.CREATED: frozenset(
        {PaymentStatus.FAILED, PaymentStatus.AUTHORIZED, PaymentStatus.CAPTURED, PaymentStatus.CANCELLED}
    ),
    PaymentStatus.FAILED: frozenset(
        {PaymentStatus.AUTHORIZED, PaymentStatus.CAPTURED, PaymentStatus.CANCELLED}
    ),
    PaymentStatus.AUTHORIZED: frozenset({PaymentStatus.CAPTURED, PaymentStatus.CANCELLED}),
    PaymentStatus.CAPTURED: frozenset(),
    PaymentStatus.CANCELLED: frozenset(),
}


class Payment(UUIDModel, TimeStampedModel):
    """
    One checkout for one booking, with its accounting breakdown:

        amount_cents (gross) = platform_fee_cents (commission) + mentor_share_cents

    The commission rate is snapshotted in `commission_bps` when checkout starts. Provider fees are
    recorded when the provider reports them and are borne by the platform (not deducted from the
    mentor share). Refunds and lost disputes are recorded as Refund rows that reverse commission and
    mentor share proportionally.
    """

    booking = models.ForeignKey("bookings.Booking", on_delete=models.PROTECT, related_name="payments")
    provider = models.CharField(max_length=20)
    livemode = models.BooleanField(
        default=False, help_text="False for provider test/sandbox mode. Test payments are never revenue."
    )
    checkout_reference = models.CharField(
        max_length=255, unique=True, null=True, blank=True, help_text="Provider checkout session id."
    )
    checkout_url = models.URLField(max_length=1000, blank=True)
    checkout_expires_at = models.DateTimeField(null=True, blank=True)
    provider_reference = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
        help_text="Provider payment id (e.g. a Stripe PaymentIntent).",
    )

    amount_cents = models.PositiveIntegerField(help_text="Gross booking value charged to the student.")
    currency = models.CharField(max_length=3)
    commission_bps = models.PositiveIntegerField(
        help_text="Platform commission in basis points (1500 = 15%)."
    )
    platform_fee_cents = models.PositiveIntegerField(help_text="Platform commission on the gross amount.")
    mentor_share_cents = models.PositiveIntegerField(help_text="Gross minus commission.")
    provider_fee_cents = models.PositiveIntegerField(
        null=True, blank=True, help_text="Processing fee reported by the provider, when known."
    )

    status = models.CharField(max_length=16, choices=PaymentStatus.choices, default=PaymentStatus.CREATED)
    refund_status = models.CharField(max_length=10, choices=RefundStatus.choices, default=RefundStatus.NONE)
    refunded_amount_cents = models.PositiveIntegerField(default=0, help_text="Sum of succeeded refunds.")
    dispute_status = models.CharField(max_length=8, choices=DisputeStatus.choices, default=DisputeStatus.NONE)
    authorized_at = models.DateTimeField(null=True, blank=True)
    captured_at = models.DateTimeField(null=True, blank=True)
    failure_code = models.CharField(max_length=100, blank=True, help_text="Provider decline/error code only.")

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(condition=Q(amount_cents__gt=0), name="payment_amount_positive"),
            models.CheckConstraint(condition=Q(commission_bps__lte=10_000), name="payment_commission_range"),
            models.CheckConstraint(
                condition=Q(platform_fee_cents__lte=F("amount_cents")), name="payment_fee_le_amount"
            ),
            models.CheckConstraint(
                condition=Q(platform_fee_cents=F("amount_cents") - F("mentor_share_cents")),
                name="payment_breakdown_adds_up",
            ),
            models.CheckConstraint(
                condition=Q(refunded_amount_cents__lte=F("amount_cents")), name="payment_refund_le_amount"
            ),
            models.UniqueConstraint(
                fields=["booking"],
                condition=Q(status__in=OPEN_PAYMENT_STATUSES),
                name="one_open_payment_per_booking",
            ),
        ]
        indexes = [models.Index(fields=["status", "livemode"])]

    def __str__(self) -> str:
        return f"{self.provider}:{self.provider_reference or self.pk} {self.status}"


class RefundReason(models.TextChoices):
    STUDENT_CANCELLATION = "student_cancellation", "Student cancelled"
    MENTOR_CANCELLATION = "mentor_cancellation", "Mentor cancelled"
    ADMIN = "admin", "Issued by an administrator"
    DISPUTE_LOST = "dispute_lost", "Dispute lost"
    SYSTEM = "system", "Automatic: the booking couldn't go ahead"


class RefundRecordStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    SUCCEEDED = "succeeded", "Succeeded"
    FAILED = "failed", "Failed"


class Refund(UUIDModel, TimeStampedModel):
    """
    Money returned to the student (or taken back through a lost dispute). The amount reverses the
    commission and mentor share in proportion to the gross amount.
    """

    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="refunds")
    amount_cents = models.PositiveIntegerField()
    commission_reversed_cents = models.PositiveIntegerField()
    mentor_share_reversed_cents = models.PositiveIntegerField()
    reason = models.CharField(max_length=24, choices=RefundReason.choices)
    status = models.CharField(
        max_length=10, choices=RefundRecordStatus.choices, default=RefundRecordStatus.PENDING
    )
    provider_reference = models.CharField(max_length=255, unique=True, null=True, blank=True)
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    note = models.CharField(max_length=500, blank=True)
    failure_code = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(condition=Q(amount_cents__gt=0), name="refund_amount_positive"),
            models.CheckConstraint(
                condition=Q(amount_cents=F("commission_reversed_cents") + F("mentor_share_reversed_cents")),
                name="refund_breakdown_adds_up",
            ),
        ]

    def __str__(self) -> str:
        return f"Refund {self.amount_cents} {self.status}"


class WebhookEvent(models.Model):
    """
    Every provider notification we accept, keyed by the provider's event id. The unique key makes
    processing idempotent: a duplicate delivery finds the existing row and changes nothing. Only
    identifiers are stored, not the payload (which can contain customer details).
    """

    provider = models.CharField(max_length=20)
    event_id = models.CharField(max_length=255)
    event_type = models.CharField(max_length=100)
    object_reference = models.CharField(max_length=255, blank=True)
    livemode = models.BooleanField(default=False)
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    outcome = models.CharField(max_length=60, blank=True)

    class Meta:
        ordering = ["-received_at"]
        constraints = [
            models.UniqueConstraint(fields=["provider", "event_id"], name="webhook_event_unique"),
        ]

    def __str__(self) -> str:
        return f"{self.provider}:{self.event_type}:{self.event_id}"


class PayoutStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PAID = "paid", "Paid"
    FAILED = "failed", "Failed"
    CANCELLED = "cancelled", "Cancelled"


class Payout(UUIDModel, TimeStampedModel):
    """
    Money paid out to a mentor, recorded by staff (manual payouts). Automatic payouts need a
    provider and connected-account setup that hasn't been chosen (docs/PAYMENTS.md §6).
    """

    mentor = models.ForeignKey("mentors.MentorProfile", on_delete=models.PROTECT, related_name="payouts")
    amount_cents = models.PositiveIntegerField()
    currency = models.CharField(max_length=3)
    status = models.CharField(max_length=10, choices=PayoutStatus.choices, default=PayoutStatus.PENDING)
    method = models.CharField(max_length=20, default="manual")
    external_reference = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.CheckConstraint(condition=Q(amount_cents__gt=0), name="payout_amount_positive")]
