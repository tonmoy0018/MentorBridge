from django.conf import settings
from django.db import models
from django.db.models import Q
from django_countries.fields import CountryField

from apps.common.models import TimeStampedModel, UUIDModel
from apps.taxonomy.models import Category


class StudentProfile(UUIDModel, TimeStampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="student_profile"
    )
    headline = models.CharField(max_length=120, blank=True)
    education = models.CharField(
        max_length=200, blank=True, help_text="e.g. BSc Economics, University of Leeds"
    )
    bio = models.TextField(max_length=2000, blank=True)
    country = CountryField(blank=True)
    interests = models.ManyToManyField(Category, blank=True, related_name="interested_students")

    def __str__(self) -> str:
        return f"StudentProfile({self.user.email})"


class SavedMentor(models.Model):
    """A student's bookmark of a mentor (wishlist)."""

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_mentors"
    )
    mentor = models.ForeignKey("mentors.MentorProfile", on_delete=models.CASCADE, related_name="saved_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["student", "mentor"], name="saved_mentor_unique")]

    def __str__(self) -> str:
        return f"{self.student_id} saved {self.mentor_id}"


class GoalStatus(models.TextChoices):
    NOT_STARTED = "not_started", "Not started"
    IN_PROGRESS = "in_progress", "In progress"
    ACHIEVED = "achieved", "Achieved"
    ARCHIVED = "archived", "Archived"


class CareerGoal(UUIDModel, TimeStampedModel):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="career_goals"
    )
    title = models.CharField(max_length=140)
    description = models.TextField(max_length=1000, blank=True)
    status = models.CharField(max_length=16, choices=GoalStatus.choices, default=GoalStatus.NOT_STARTED)
    target_date = models.DateField(null=True, blank=True)
    achieved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(condition=Q(status__in=GoalStatus.values), name="goal_status_valid")
        ]
        indexes = [models.Index(fields=["student", "status"])]
