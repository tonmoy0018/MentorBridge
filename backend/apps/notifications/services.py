"""
Transactional email (docs/NOTIFICATIONS.md).

    notify("booking_confirmed_student", user, context, dedupe_key=f"booking.confirmed:{id}:student")

Call it inside the transaction that made the change: the row is created there (so a rollback
removes it) and the email is sent after commit. A repeated event with the same dedupe key is a
no-op. Delivery failures are recorded and retried by `manage.py send_notifications`; logs carry
the notification id and template, never addresses or content.
"""

import logging
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.template.loader import render_to_string
from django.utils import timezone

from .models import EmailNotification, NotificationStatus

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3

# Context keys holding one-time secrets (verification / password-reset links). They're kept only
# until the email is sent, so the table never accumulates usable tokens.
SECRET_CONTEXT_KEYS = frozenset({"link"})

TEMPLATES = {
    "account_verification",
    "password_reset",
    "mentor_verification_approved",
    "mentor_verification_rejected",
    "booking_requested_mentor",
    "booking_confirmed_student",
    "booking_confirmed_mentor",
    "booking_declined_student",
    "booking_cancelled",
    "booking_expired_student",
    "session_reminder",
    "payment_failed",
    "payment_released",
    "refund_initiated",
    "refund_succeeded",
    "refund_failed",
}


def unique_key(prefix: str) -> str:
    """For emails that must go out every time (e.g. each password-reset request)."""
    return f"{prefix}:{uuid.uuid4()}"


def notify(template: str, recipient, context: dict, *, dedupe_key: str) -> EmailNotification | None:
    if template not in TEMPLATES:
        raise ValueError(f"Unknown email template {template!r}")
    if recipient is None or not recipient.is_active:
        return None
    context = {"site_url": settings.FRONTEND_URL, "first_name": recipient.first_name, **context}
    try:
        with transaction.atomic():
            notification = EmailNotification.objects.create(
                dedupe_key=dedupe_key[:200], template=template, recipient=recipient, context=context
            )
    except IntegrityError:
        logger.info("Notification %s already exists; not sending again", dedupe_key[:60])
        return None
    transaction.on_commit(lambda: deliver(notification.pk))
    return notification


def deliver(notification_id) -> bool:
    """Send one queued/failed notification. Never raises: failures are recorded for retry."""
    notification = EmailNotification.objects.select_related("recipient").filter(pk=notification_id).first()
    if notification is None or notification.status in (NotificationStatus.SENT, NotificationStatus.SKIPPED):
        return False
    recipient = notification.recipient
    if recipient is None or not recipient.is_active:
        notification.status = NotificationStatus.SKIPPED
        notification.save(update_fields=["status", "updated_at"])
        return False
    try:
        subject = render_to_string(
            f"notifications/email/{notification.template}.subject.txt",
            notification.context,
            using="email_text",
        )
        body = render_to_string(
            f"notifications/email/{notification.template}.txt", notification.context, using="email_text"
        )
        send_mail(" ".join(subject.split()), body, settings.DEFAULT_FROM_EMAIL, [recipient.email])
    except Exception as exc:
        notification.attempts += 1
        notification.status = NotificationStatus.FAILED
        notification.last_error = type(exc).__name__[:100]
        notification.save(update_fields=["attempts", "status", "last_error", "updated_at"])
        logger.warning(
            "Notification %s (%s) failed: %s", notification.pk, notification.template, notification.last_error
        )
        return False
    notification.attempts += 1
    notification.status = NotificationStatus.SENT
    notification.sent_at = timezone.now()
    notification.last_error = ""
    notification.context = {k: v for k, v in notification.context.items() if k not in SECRET_CONTEXT_KEYS}
    notification.save(update_fields=["attempts", "status", "sent_at", "last_error", "context", "updated_at"])
    logger.info("Notification %s (%s) sent", notification.pk, notification.template)
    return True


def retry_failed() -> int:
    """Retry failed sends (up to MAX_ATTEMPTS) and anything stuck in the queue."""
    stale = timezone.now() - timedelta(minutes=5)
    pending = EmailNotification.objects.filter(
        status=NotificationStatus.FAILED, attempts__lt=MAX_ATTEMPTS
    ) | (EmailNotification.objects.filter(status=NotificationStatus.QUEUED, created_at__lt=stale))
    return sum(deliver(pk) for pk in pending.values_list("pk", flat=True)[:200])


def local_time(when: datetime, user) -> str:
    """Format a UTC instant in the recipient's time zone for an email, e.g. 'Tue 3 Nov 2026, 14:00 (GMT)'."""
    zone = ZoneInfo(getattr(user, "timezone", "UTC") or "UTC")
    local = when.astimezone(zone)
    return f"{local:%a %-d %b %Y, %H:%M} ({local.tzname()})"
