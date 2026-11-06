from django.conf import settings
from django.db import models

from apps.common.models import TimeStampedModel, UUIDModel


class NotificationStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    SENT = "sent", "Sent"
    FAILED = "failed", "Failed"
    SKIPPED = "skipped", "Skipped"


class EmailNotification(UUIDModel, TimeStampedModel):
    """
    One email we intend to send. `dedupe_key` is unique, so processing the same event twice (e.g. a
    repeated webhook) can't send a second email. The rendered body isn't stored; `context` holds only
    the values the template needs (names, titles, times, links).
    """

    dedupe_key = models.CharField(max_length=200, unique=True)
    template = models.CharField(max_length=60)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="email_notifications"
    )
    context = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=10, choices=NotificationStatus.choices, default=NotificationStatus.QUEUED
    )
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.CharField(max_length=100, blank=True, help_text="Exception type only, never content.")
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "created_at"])]

    def __str__(self) -> str:
        return f"{self.template} → {self.recipient_id} ({self.status})"
