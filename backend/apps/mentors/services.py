"""Mentor-side business operations (profile, services, availability, verification)."""

from collections import defaultdict

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.text import slugify
from PIL import Image, UnidentifiedImageError

from apps.common.exceptions import Conflict
from apps.common.models import record_audit
from apps.notifications.services import notify

from .models import (
    AvailabilityRule,
    MentorProfile,
    MentorService,
    VerificationRequest,
    VerificationRequestStatus,
    VerificationStatus,
)

MAX_AVATAR_BYTES = 2 * 1024 * 1024
AVATAR_FORMATS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}
MAX_RULES_PER_DAY = 12


def create_mentor_profile(user) -> MentorProfile:
    base = slugify(f"{user.first_name} {user.last_name}")[:60] or "mentor"
    slug, n = base, 1
    while MentorProfile.objects.filter(slug=slug).exists():
        n += 1
        slug = f"{base}-{n}"
    return MentorProfile.objects.create(user=user, slug=slug, timezone=user.timezone)


PUBLIC_FIELDS = {"headline", "current_title", "current_company", "profession", "bio"}


@transaction.atomic
def update_profile(mentor: MentorProfile, data: dict, *, actor, request=None) -> MentorProfile:
    """Apply validated profile changes. `verification_status` can never be set here."""
    data = dict(data)
    categories = data.pop("categories", None)
    skills = data.pop("skills", None)
    languages = data.pop("languages", None)
    data.pop("verification_status", None)
    data.pop("verified_at", None)

    old_timezone = mentor.timezone
    changed_public = sorted(f for f in PUBLIC_FIELDS if f in data and getattr(mentor, f) != data[f])
    for field, value in data.items():
        setattr(mentor, field, value)
    mentor.save()

    if categories is not None:
        mentor.categories.set(categories)
    if skills is not None:
        mentor.skills.set(skills)
    if languages is not None:
        mentor.languages.set(languages)
    if mentor.timezone != old_timezone:
        # Weekly hours keep their wall-clock times in the new zone, as the UI describes.
        mentor.availability_rules.update(timezone=mentor.timezone)
    if mentor.verification_status == VerificationStatus.APPROVED and changed_public:
        record_audit(
            actor, "mentor.profile.updated_after_approval", mentor, {"fields": changed_public}, request
        )
    return mentor


# --- services --------------------------------------------------------------------------


def _check_currency(currency: str | None) -> str:
    currency = (currency or settings.PLATFORM_CURRENCY).upper()
    if currency != settings.PLATFORM_CURRENCY:
        raise ValidationError({"currency": f"Prices must be in {settings.PLATFORM_CURRENCY}."})
    return currency


def create_service(mentor: MentorProfile, data: dict) -> MentorService:
    return MentorService.objects.create(
        mentor=mentor, currency=_check_currency(data.pop("currency", None)), **data
    )


def update_service(service: MentorService, data: dict) -> MentorService:
    if "currency" in data:
        service.currency = _check_currency(data.pop("currency"))
    for field, value in data.items():
        setattr(service, field, value)
    service.save()
    return service


def delete_service(service: MentorService) -> None:
    """Services with bookings are kept for history; deactivate them instead."""
    if service.bookings.exists():
        raise Conflict("service_in_use", "This service has bookings. Hide it instead of deleting it.")
    service.delete()


# --- availability ----------------------------------------------------------------------


def validate_rules(rules: list[dict]) -> None:
    by_day: dict[int, list[dict]] = defaultdict(list)
    for rule in rules:
        if rule["end_time"] <= rule["start_time"]:
            raise ValidationError({"rules": "Each end time must be after its start time."})
        by_day[rule["weekday"]].append(rule)
    for weekday, day_rules in by_day.items():
        if len(day_rules) > MAX_RULES_PER_DAY:
            raise ValidationError({"rules": f"Use at most {MAX_RULES_PER_DAY} time ranges per day."})
        ordered = sorted(day_rules, key=lambda r: r["start_time"])
        for prev, cur in zip(ordered, ordered[1:], strict=False):
            if cur["start_time"] < prev["end_time"]:
                raise ValidationError({"rules": f"Time ranges overlap on weekday {weekday}."})


@transaction.atomic
def replace_availability_rules(mentor: MentorProfile, rules: list[dict]) -> list[AvailabilityRule]:
    validate_rules(rules)
    mentor.availability_rules.all().delete()
    return AvailabilityRule.objects.bulk_create(
        [AvailabilityRule(mentor=mentor, timezone=mentor.timezone, **rule) for rule in rules]
    )


# --- verification ----------------------------------------------------------------------


def missing_profile_items(mentor: MentorProfile) -> list[str]:
    missing = []
    if len(mentor.headline.strip()) < 10:
        missing.append("a headline")
    if len(mentor.bio.strip()) < 50:
        missing.append("a bio of at least 50 characters")
    if not mentor.current_title.strip():
        missing.append("your current job title")
    if mentor.profession_id is None:
        missing.append("your profession")
    if not mentor.country:
        missing.append("your country")
    if not mentor.categories.exists():
        missing.append("at least one industry")
    if not mentor.skills.exists():
        missing.append("at least one skill")
    if not mentor.languages.exists():
        missing.append("at least one language")
    if not mentor.meeting_url:
        missing.append("a default meeting link")
    if settings.REQUIRE_VERIFIED_EMAIL and not mentor.user.email_verified:
        missing.append("a verified email address")
    return missing


@transaction.atomic
def submit_for_verification(
    mentor: MentorProfile, *, evidence_note: str, actor, request=None
) -> VerificationRequest:
    mentor = MentorProfile.objects.select_for_update().get(pk=mentor.pk)
    if mentor.verification_status == VerificationStatus.PENDING:
        raise Conflict("already_exists", "Your profile is already under review.")
    if mentor.verification_status == VerificationStatus.APPROVED:
        raise Conflict("invalid_state", "Your profile is already approved.")
    if mentor.verification_status == VerificationStatus.SUSPENDED:
        raise Conflict("invalid_state", "Suspended profiles can't be submitted. Contact support.")
    if missing := missing_profile_items(mentor):
        raise ValidationError("Complete your profile before submitting: add " + ", ".join(missing) + ".")
    try:
        verification = VerificationRequest.objects.create(
            mentor=mentor, evidence_note=evidence_note, submitted_at=timezone.now()
        )
    except IntegrityError as exc:  # concurrent submission
        raise Conflict("already_exists", "Your profile is already under review.") from exc
    mentor.verification_status = VerificationStatus.PENDING
    mentor.save(update_fields=["verification_status", "updated_at"])
    record_audit(
        actor, "mentor.verification.submitted", mentor, {"request_id": str(verification.pk)}, request
    )
    return verification


def _lock_pending(verification: VerificationRequest) -> VerificationRequest:
    locked = VerificationRequest.objects.select_for_update().select_related("mentor").get(pk=verification.pk)
    if locked.status != VerificationRequestStatus.PENDING:
        raise Conflict("invalid_state", "This request has already been reviewed.")
    return locked


@transaction.atomic
def approve_verification(verification: VerificationRequest, *, actor, request=None) -> VerificationRequest:
    verification = _lock_pending(verification)
    now = timezone.now()
    verification.status = VerificationRequestStatus.APPROVED
    verification.reviewed_by, verification.reviewed_at = actor, now
    verification.save()
    mentor = verification.mentor
    mentor.verification_status, mentor.verified_at = VerificationStatus.APPROVED, now
    mentor.save(update_fields=["verification_status", "verified_at", "updated_at"])
    record_audit(actor, "mentor.verification.approved", mentor, {"request_id": str(verification.pk)}, request)
    notify(
        "mentor_verification_approved",
        mentor.user,
        {"slug": mentor.slug},
        dedupe_key=f"mentor.verification.approved:{verification.pk}",
    )
    return verification


@transaction.atomic
def reject_verification(
    verification: VerificationRequest, *, actor, reason: str, request=None
) -> VerificationRequest:
    verification = _lock_pending(verification)
    verification.status = VerificationRequestStatus.REJECTED
    verification.reviewed_by, verification.reviewed_at = actor, timezone.now()
    verification.decision_reason = reason
    verification.save()
    mentor = verification.mentor
    mentor.verification_status = VerificationStatus.REJECTED
    mentor.save(update_fields=["verification_status", "updated_at"])
    record_audit(actor, "mentor.verification.rejected", mentor, {"request_id": str(verification.pk)}, request)
    notify(
        "mentor_verification_rejected",
        mentor.user,
        {"reason": reason},
        dedupe_key=f"mentor.verification.rejected:{verification.pk}",
    )
    return verification


# --- avatar ----------------------------------------------------------------------------


def set_avatar(mentor: MentorProfile, upload) -> MentorProfile:
    """Validate the actual image content (not the filename or client content type)."""
    if upload.size > MAX_AVATAR_BYTES:
        raise ValidationError({"avatar": "Use an image of 2 MB or less."})
    try:
        with Image.open(upload) as image:
            image.verify()
            fmt = image.format
            width, height = image.size
    except (UnidentifiedImageError, OSError) as exc:
        raise ValidationError({"avatar": "Upload a JPEG, PNG or WebP image."}) from exc
    if fmt not in AVATAR_FORMATS:
        raise ValidationError({"avatar": "Upload a JPEG, PNG or WebP image."})
    if width > 4000 or height > 4000:
        raise ValidationError({"avatar": "Use an image no larger than 4000×4000 pixels."})
    upload.seek(0)
    old = mentor.avatar.name if mentor.avatar else None
    mentor.avatar.save(f"avatar.{AVATAR_FORMATS[fmt]}", upload, save=True)
    if old:
        mentor.avatar.storage.delete(old)
    return mentor


def clear_avatar(mentor: MentorProfile) -> MentorProfile:
    if mentor.avatar:
        mentor.avatar.delete(save=True)
    return mentor
