from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.bookings.models import Booking
from apps.common.exceptions import Conflict
from apps.common.models import record_audit
from apps.mentors.models import MentorProfile
from apps.reviews.models import Review, ReviewStatus
from apps.users.models import User

from .models import Report, ReportStatus, ReportTargetType


def resolve_target(reporter, target_type: str, target_id) -> tuple[object, str]:
    """Find the reported object, but only if the reporter is allowed to see it (else 404)."""
    if target_type == ReportTargetType.REVIEW:
        review = (
            Review.objects.filter(pk=target_id, status=ReviewStatus.PUBLISHED)
            .select_related("mentor__user")
            .first()
        )
        if review:
            return review, f"Review on {review.mentor.user.full_name}'s profile"
    elif target_type == ReportTargetType.MENTOR_PROFILE:
        mentor = MentorProfile.objects.filter(pk=target_id).select_related("user").first()
        if mentor and mentor.is_publicly_visible:
            return mentor, f"Mentor profile: {mentor.user.full_name}"
    elif target_type == ReportTargetType.BOOKING:
        booking = Booking.objects.filter(pk=target_id).select_related("mentor__user").first()
        if booking and booking.is_participant(reporter):
            return booking, f"Booking: {booking.service_title} with {booking.mentor.user.full_name}"
    elif target_type == ReportTargetType.USER:
        # Only people you've had a booking with can be reported, so ids can't be probed.
        user = User.objects.filter(pk=target_id).first()
        shared = user and (
            Booking.objects.filter(student=reporter, mentor__user=user).exists()
            or Booking.objects.filter(student=user, mentor__user=reporter).exists()
        )
        if shared:
            return user, f"User: {user.full_name}"
    raise NotFound("We couldn't find that item.")


def create_report(*, reporter, target_type: str, target_id, reason: str, details: str) -> Report:
    _, label = resolve_target(reporter, target_type, target_id)
    try:
        with transaction.atomic():
            return Report.objects.create(
                reporter=reporter,
                target_type=target_type,
                target_id=target_id,
                target_label=label[:200],
                reason=reason,
                details=details.strip(),
            )
    except IntegrityError as exc:
        raise Conflict("already_exists", "You've already reported this, and it's being reviewed.") from exc


@transaction.atomic
def resolve_report(
    report: Report, *, actor, resolution: str, note: str, hide_review: bool, request=None
) -> Report:
    report = Report.objects.select_for_update().get(pk=report.pk)
    if report.status not in (ReportStatus.OPEN, ReportStatus.IN_REVIEW):
        raise Conflict("invalid_state", "This report has already been resolved.")
    if hide_review:
        if report.target_type != ReportTargetType.REVIEW or resolution != ReportStatus.ACTIONED:
            raise Conflict("invalid_action", "Only actioned review reports can hide a review.")
        from apps.reviews.services import set_review_visibility

        review = Review.objects.get(pk=report.target_id)
        set_review_visibility(review, hidden=True, reason=note)
    report.status = resolution
    report.resolution_note = note
    report.resolved_by = actor
    report.resolved_at = timezone.now()
    report.save()
    record_audit(actor, f"report.{resolution}", report, {"hide_review": hide_review}, request)
    return report
