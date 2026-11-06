from decimal import ROUND_HALF_UP, Decimal

from django.db import IntegrityError, transaction
from django.db.models import Avg, Count

from apps.bookings.models import Booking, BookingStatus
from apps.common.exceptions import Conflict
from apps.mentors.models import MentorProfile

from .models import Review, ReviewStatus


def recalculate_rating(mentor: MentorProfile) -> None:
    stats = mentor.reviews.filter(status=ReviewStatus.PUBLISHED).aggregate(
        avg=Avg("rating"), count=Count("id")
    )
    mentor.rating_count = stats["count"]
    mentor.rating_avg = (
        Decimal(stats["avg"]).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if stats["avg"] is not None
        else None
    )
    mentor.save(update_fields=["rating_avg", "rating_count", "updated_at"])


@transaction.atomic
def create_review(*, booking: Booking, student, rating: int, comment: str) -> Review:
    """Only the booking's student may review it, once, after it has been completed."""
    booking = Booking.objects.select_for_update().select_related("mentor").get(pk=booking.pk)
    if booking.student_id != student.pk:
        raise Conflict("not_eligible", "You can only review sessions you attended.")
    if booking.status != BookingStatus.COMPLETED:
        raise Conflict("not_eligible", "You can review a session once it has been completed.")
    if Review.objects.filter(booking=booking).exists():
        raise Conflict("already_exists", "You've already reviewed this session.")
    try:
        with transaction.atomic():
            review = Review.objects.create(
                booking=booking,
                student=student,
                mentor=booking.mentor,
                rating=rating,
                comment=comment.strip(),
            )
    except IntegrityError as exc:
        raise Conflict("already_exists", "You've already reviewed this session.") from exc
    mentor = MentorProfile.objects.select_for_update().get(pk=booking.mentor_id)
    recalculate_rating(mentor)
    return review


@transaction.atomic
def set_review_visibility(review: Review, *, hidden: bool, reason: str = "") -> Review:
    review.status = ReviewStatus.HIDDEN if hidden else ReviewStatus.PUBLISHED
    review.hidden_reason = reason if hidden else ""
    review.save(update_fields=["status", "hidden_reason", "updated_at"])
    recalculate_rating(MentorProfile.objects.select_for_update().get(pk=review.mentor_id))
    return review
