import uuid

from django.conf import settings
from django.db import models


class UUIDModel(models.Model):
    """Non-enumerable primary keys for anything exposed in URLs."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class AuditLogEntry(models.Model):
    """Append-only record of administrative and trust-sensitive actions."""

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    action = models.CharField(max_length=60)
    target_type = models.CharField(max_length=40)
    target_id = models.CharField(max_length=64)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["target_type", "target_id"]), models.Index(fields=["action"])]

    def __str__(self) -> str:
        return f"{self.action} {self.target_type}:{self.target_id}"


def record_audit(actor, action: str, target, metadata: dict | None = None, request=None) -> AuditLogEntry:
    """Write an audit entry. `metadata` must not contain secrets or payment data."""
    ip = request.META.get("REMOTE_ADDR") if request is not None else None
    return AuditLogEntry.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        target_type=target._meta.label_lower,
        target_id=str(target.pk),
        metadata=metadata or {},
        ip_address=ip,
    )
