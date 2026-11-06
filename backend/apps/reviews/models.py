from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.common.models import TimeStampedModel, UUIDModel


class ReviewStatus(models.TextChoices):
    PUBLISHED = "published", "Published"
    HIDDEN = "hidden", "Hidden by moderators"


class Review(UUIDModel, TimeStampedModel):
    """At most one review per booking, only for completed bookings (enforced in services)."""

    booking = models.OneToOneField("bookings.Booking", on_delete=models.PROTECT, related_name="review")
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reviews")
    mentor = models.ForeignKey("mentors.MentorProfile", on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(max_length=2000, blank=True)
    status = models.CharField(max_length=12, choices=ReviewStatus.choices, default=ReviewStatus.PUBLISHED)
    hidden_reason = models.TextField(max_length=1000, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(condition=Q(rating__gte=1, rating__lte=5), name="review_rating_1_to_5"),
            models.CheckConstraint(condition=Q(status__in=ReviewStatus.values), name="review_status_valid"),
        ]
        indexes = [models.Index(fields=["mentor", "status", "-created_at"])]
