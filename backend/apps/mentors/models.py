from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django_countries.fields import CountryField

from apps.common.models import TimeStampedModel, UUIDModel
from apps.taxonomy.models import Category, Language, Profession, Skill

ALLOWED_DURATIONS = (15, 30, 45, 60, 90, 120, 180)
MAX_PRICE_CENTS = 1_000_000  # 10,000.00 in the platform currency


class VerificationStatus(models.TextChoices):
    DRAFT = "draft", "Not submitted"
    PENDING = "pending", "Under review"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Changes needed"
    SUSPENDED = "suspended", "Suspended"


def avatar_upload_to(instance, filename):
    # Random, non-guessable names; the original filename is discarded.
    import uuid

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"
    return f"avatars/{uuid.uuid4().hex}.{ext}"


class MentorProfile(UUIDModel, TimeStampedModel):
    """
    A mentor's professional profile. Publicly listed only when
    verification_status = approved AND the user is active. `verification_status` is never
    writable through the mentor API: only the admin verification workflow changes it.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mentor_profile"
    )
    slug = models.SlugField(max_length=80, unique=True)
    headline = models.CharField(max_length=140, blank=True)
    bio = models.TextField(blank=True)
    current_title = models.CharField("professional title", max_length=120, blank=True)
    current_company = models.CharField(max_length=120, blank=True)
    profession = models.ForeignKey(
        Profession, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    categories = models.ManyToManyField(Category, blank=True, related_name="mentors")
    skills = models.ManyToManyField(Skill, through="MentorSkill", blank=True, related_name="mentors")
    languages = models.ManyToManyField(Language, blank=True, related_name="mentors")
    years_experience = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(60)])
    country = CountryField(blank=True)
    city = models.CharField("location", max_length=100, blank=True)
    timezone = models.CharField(max_length=64, default="UTC")
    linkedin_url = models.URLField(blank=True)
    avatar = models.ImageField(upload_to=avatar_upload_to, blank=True)
    meeting_url = models.URLField(max_length=300, blank=True)

    verification_status = models.CharField(
        max_length=16, choices=VerificationStatus.choices, default=VerificationStatus.DRAFT
    )
    verified_at = models.DateTimeField(null=True, blank=True)

    is_accepting_bookings = models.BooleanField(default=True)
    auto_accept = models.BooleanField(default=False)
    min_notice_hours = models.PositiveSmallIntegerField(default=24, validators=[MaxValueValidator(336)])
    booking_horizon_days = models.PositiveSmallIntegerField(
        default=60, validators=[MinValueValidator(1), MaxValueValidator(180)]
    )
    buffer_minutes = models.PositiveSmallIntegerField(default=15, validators=[MaxValueValidator(120)])

    # Admin-only commission override in basis points (1500 = 15%). Null = platform default.
    commission_bps = models.PositiveIntegerField(
        null=True, blank=True, validators=[MaxValueValidator(10_000)], help_text="Admin-only override."
    )

    # Denormalised from published reviews; maintained by apps.reviews.services.
    rating_avg = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    rating_count = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(years_experience__lte=60), name="mentor_years_experience_range"
            ),
            models.CheckConstraint(condition=Q(min_notice_hours__lte=336), name="mentor_min_notice_range"),
            models.CheckConstraint(
                condition=Q(booking_horizon_days__gte=1, booking_horizon_days__lte=180),
                name="mentor_horizon_range",
            ),
            models.CheckConstraint(condition=Q(buffer_minutes__lte=120), name="mentor_buffer_range"),
            models.CheckConstraint(
                condition=Q(verification_status__in=VerificationStatus.values),
                name="mentor_verification_status_valid",
            ),
        ]
        indexes = [models.Index(fields=["verification_status"]), models.Index(fields=["country"])]

    def __str__(self) -> str:
        return f"{self.user.full_name} ({self.slug})"

    @property
    def display_name(self) -> str:
        return self.user.full_name

    @property
    def is_publicly_visible(self) -> bool:
        return self.verification_status == VerificationStatus.APPROVED and self.user.is_active


class MentorSkill(models.Model):
    """Associates a mentor with a professional skill."""

    mentor = models.ForeignKey(MentorProfile, on_delete=models.CASCADE, related_name="mentor_skills")
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name="mentor_skills")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["mentor", "skill"], name="mentor_skill_unique")]

    def __str__(self) -> str:
        return f"{self.mentor_id}: {self.skill_id}"


class ExperienceKind(models.TextChoices):
    WORK = "work", "Work"
    EDUCATION = "education", "Education"


class MentorExperience(UUIDModel, TimeStampedModel):
    mentor = models.ForeignKey(MentorProfile, on_delete=models.CASCADE, related_name="experiences")
    kind = models.CharField(max_length=12, choices=ExperienceKind.choices, default=ExperienceKind.WORK)
    title = models.CharField(max_length=120)
    organization = models.CharField(max_length=120)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    description = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["-start_date"]
        constraints = [
            models.CheckConstraint(
                condition=Q(end_date__isnull=True) | Q(end_date__gte=models.F("start_date")),
                name="experience_end_after_start",
            )
        ]


class MentorService(UUIDModel, TimeStampedModel):
    """A bookable offering. Bookings snapshot title/duration/price, so edits never change past bookings."""

    mentor = models.ForeignKey(MentorProfile, on_delete=models.CASCADE, related_name="services")
    title = models.CharField(max_length=120)
    description = models.TextField(max_length=1000)
    duration_minutes = models.PositiveSmallIntegerField()
    price_cents = models.PositiveIntegerField()
    currency = models.CharField(max_length=3)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["price_cents", "duration_minutes"]
        constraints = [
            models.CheckConstraint(
                condition=Q(duration_minutes__in=ALLOWED_DURATIONS), name="service_duration_allowed"
            ),
            models.CheckConstraint(condition=Q(price_cents__lte=MAX_PRICE_CENTS), name="service_price_range"),
            models.CheckConstraint(condition=Q(currency__regex=r"^[A-Z]{3}$"), name="service_currency_iso"),
        ]
        indexes = [models.Index(fields=["mentor", "is_active"])]

    def __str__(self) -> str:
        return self.title


class AvailabilityRule(UUIDModel, TimeStampedModel):
    """
    Weekly recurring availability, as wall-clock times in `timezone` (an IANA zone kept in
    sync with the mentor's profile timezone). Rules only describe *when a mentor can be
    booked*; double-booking is prevented by constraints on Booking, not here.
    """

    mentor = models.ForeignKey(MentorProfile, on_delete=models.CASCADE, related_name="availability_rules")
    weekday = models.PositiveSmallIntegerField(help_text="0 = Monday … 6 = Sunday")
    start_time = models.TimeField()
    end_time = models.TimeField()
    timezone = models.CharField(max_length=64)

    class Meta:
        ordering = ["weekday", "start_time"]
        constraints = [
            models.CheckConstraint(condition=Q(weekday__lte=6), name="availability_rule_weekday_range"),
            models.CheckConstraint(
                condition=Q(end_time__gt=models.F("start_time")), name="availability_rule_end_after_start"
            ),
        ]


class AvailabilityExceptionStatus(models.TextChoices):
    AVAILABLE = "available", "Extra availability"
    UNAVAILABLE = "unavailable", "Unavailable"


class AvailabilityException(UUIDModel, TimeStampedModel):
    """A specific period that adds to (`available`) or blocks (`unavailable`) the weekly rules."""

    mentor = models.ForeignKey(
        MentorProfile, on_delete=models.CASCADE, related_name="availability_exceptions"
    )
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    status = models.CharField(max_length=12, choices=AvailabilityExceptionStatus.choices)
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["start_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(end_at__gt=models.F("start_at")), name="availability_exception_order"
            ),
        ]
        indexes = [models.Index(fields=["mentor", "start_at"])]


class VerificationRequestStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    WITHDRAWN = "withdrawn", "Withdrawn"


class VerificationRequest(UUIDModel, TimeStampedModel):
    mentor = models.ForeignKey(MentorProfile, on_delete=models.CASCADE, related_name="verification_requests")
    status = models.CharField(
        max_length=12, choices=VerificationRequestStatus.choices, default=VerificationRequestStatus.PENDING
    )
    evidence_note = models.TextField(max_length=2000, blank=True)
    submitted_at = models.DateTimeField()
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    decision_reason = models.TextField(max_length=2000, blank=True)

    class Meta:
        ordering = ["-submitted_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["mentor"],
                condition=Q(status=VerificationRequestStatus.PENDING),
                name="one_pending_verification_per_mentor",
            )
        ]
