from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.common.models import TimeStampedModel, UUIDModel


class ReportTargetType(models.TextChoices):
    REVIEW = "review", "Review"
    MENTOR_PROFILE = "mentor_profile", "Mentor profile"
    USER = "user", "User"
    BOOKING = "booking", "Booking"


class ReportReason(models.TextChoices):
    SPAM = "spam", "Spam"
    INAPPROPRIATE = "inappropriate", "Inappropriate"
    MISLEADING = "misleading", "Misleading"
    HARASSMENT = "harassment", "Harassment"
    NO_SHOW = "no_show", "No-show"
    OTHER = "other", "Other"


class ReportStatus(models.TextChoices):
    OPEN = "open", "Open"
    IN_REVIEW = "in_review", "In review"
    ACTIONED = "actioned", "Actioned"
    DISMISSED = "dismissed", "Dismissed"


UNRESOLVED = (ReportStatus.OPEN, ReportStatus.IN_REVIEW)


class Report(UUIDModel, TimeStampedModel):
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="reports_made"
    )
    target_type = models.CharField(max_length=20, choices=ReportTargetType.choices)
    target_id = models.UUIDField()
    target_label = models.CharField(max_length=200)
    reason = models.CharField(max_length=20, choices=ReportReason.choices)
    details = models.TextField(max_length=2000, blank=True)
    status = models.CharField(max_length=12, choices=ReportStatus.choices, default=ReportStatus.OPEN)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    resolution_note = models.TextField(max_length=2000, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["reporter", "target_type", "target_id"],
                condition=Q(status__in=UNRESOLVED),
                name="one_open_report_per_reporter_target",
            )
        ]
        indexes = [models.Index(fields=["status", "created_at"])]
