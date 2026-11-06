"""Read-side queries for mentors: public visibility, search and availability."""

import uuid
from datetime import UTC, datetime, timedelta

from django.conf import settings
from django.db.models import F, Min, OuterRef, Q, QuerySet, Subquery
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .models import (
    AvailabilityException,
    AvailabilityExceptionStatus,
    AvailabilityRule,
    MentorProfile,
    MentorService,
    VerificationStatus,
)
from .slots import Interval, generate_slots

ORDERINGS = {
    "min_price_cents": [F("min_price_cents").asc(nulls_last=True), "id"],
    "-min_price_cents": [F("min_price_cents").desc(nulls_last=True), "id"],
    "-rating_avg": [F("rating_avg").desc(nulls_last=True), "-rating_count", "id"],
    "-years_experience": ["-years_experience", "id"],
}
# "Relevance" until full-text ranking exists: most-reviewed, then longest-verified.
DEFAULT_ORDERING = ["-rating_count", F("verified_at").asc(nulls_last=True), "id"]
NEXT_AVAILABLE_HORIZON_DAYS = 60
# Bookings and exceptions are loaded with this margin around a window, because a slot that
# starts inside the window can extend past its end (session + buffer).
LOOKAROUND = timedelta(days=1)
AVAILABILITY_FILTER_CANDIDATE_LIMIT = 500


def public_mentors() -> QuerySet[MentorProfile]:
    min_price = (
        MentorService.objects.filter(mentor=OuterRef("pk"), is_active=True)
        .values("mentor")
        .annotate(m=Min("price_cents"))
        .values("m")
    )
    return (
        MentorProfile.objects.filter(verification_status=VerificationStatus.APPROVED, user__is_active=True)
        .select_related("user", "profession")
        .prefetch_related("categories", "skills", "languages")
        .annotate(min_price_cents=Subquery(min_price))
    )


def get_public_mentor(identifier: str, queryset: QuerySet[MentorProfile] | None = None) -> MentorProfile:
    """Look up an approved mentor by slug or UUID; 404 otherwise."""
    qs = queryset if queryset is not None else public_mentors()
    try:
        pk = uuid.UUID(identifier)
    except ValueError:
        return get_object_or_404(qs, slug=identifier)
    return get_object_or_404(qs, pk=pk)


def search_mentors(params: dict) -> QuerySet[MentorProfile]:
    qs = public_mentors()
    if q := params.get("q"):
        for term in q.split()[:8]:
            # Many-to-many matches use subqueries: filtering them through JOINs would add a
            # pair of joins per term and multiply rows (skills × categories)^terms.
            qs = qs.filter(
                Q(user__first_name__icontains=term)
                | Q(user__last_name__icontains=term)
                | Q(headline__icontains=term)
                | Q(current_title__icontains=term)
                | Q(current_company__icontains=term)
                | Q(profession__name__icontains=term)
                | Q(pk__in=MentorProfile.objects.filter(skills__name__icontains=term).values("pk"))
                | Q(pk__in=MentorProfile.objects.filter(categories__name__icontains=term).values("pk"))
            )
    if industries := params.get("industry"):
        qs = qs.filter(categories__slug__in=industries)
    if profession := params.get("profession"):
        qs = qs.filter(profession__slug=profession)
    if skills := params.get("skill"):
        qs = qs.filter(skills__slug__in=skills)
    if country := params.get("country"):
        qs = qs.filter(country=country)
    if language := params.get("language"):
        qs = qs.filter(languages__code=language)
    if (price_min := params.get("price_min")) is not None:
        qs = qs.filter(min_price_cents__gte=price_min)
    if (price_max := params.get("price_max")) is not None:
        qs = qs.filter(min_price_cents__lte=price_max)
    qs = qs.distinct()
    return qs.order_by(*ORDERINGS.get(params.get("ordering") or "", DEFAULT_ORDERING))


# ---------------------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------------------


def _busy_intervals(mentor_ids, window_start: datetime, window_end: datetime, now: datetime) -> dict:
    from apps.bookings.models import ACTIVE_STATUSES, Booking, BookingStatus

    rows = (
        Booking.objects.filter(
            mentor_id__in=mentor_ids,
            status__in=ACTIVE_STATUSES,
            blocked_until__gt=window_start,
            start_at__lt=window_end,
        )
        # A lapsed payment hold no longer blocks the slot (it's expired by the scheduler).
        .exclude(status=BookingStatus.PENDING_PAYMENT, hold_expires_at__lt=now)
        .values_list("mentor_id", "start_at", "blocked_until")
    )
    busy: dict = {}
    for mentor_id, start, blocked_until in rows:
        busy.setdefault(mentor_id, []).append(Interval(start, blocked_until))
    return busy


def _exceptions(mentor_ids, window_start: datetime, window_end: datetime) -> tuple[dict, dict]:
    extra: dict = {}
    blocked: dict = {}
    rows = AvailabilityException.objects.filter(
        mentor_id__in=mentor_ids, end_at__gt=window_start, start_at__lt=window_end
    ).values_list("mentor_id", "start_at", "end_at", "status")
    for mentor_id, start, end, status in rows:
        target = extra if status == AvailabilityExceptionStatus.AVAILABLE else blocked
        target.setdefault(mentor_id, []).append(Interval(start, end))
    return extra, blocked


def _rules(mentor_ids) -> dict:
    rules: dict = {}
    for rule in AvailabilityRule.objects.filter(mentor_id__in=mentor_ids):
        rules.setdefault(rule.mentor_id, []).append(rule)
    return rules


def bookable_slots(
    mentor: MentorProfile,
    *,
    duration_minutes: int,
    window_start: datetime,
    window_end: datetime,
    now: datetime | None = None,
) -> list[datetime]:
    """Open start times for one mentor and session length within a window."""
    now = now or timezone.now()
    if not mentor.is_accepting_bookings:
        return []
    ids = [mentor.pk]
    extra, blocked = _exceptions(ids, window_start - LOOKAROUND, window_end + LOOKAROUND)
    busy = _busy_intervals(ids, window_start - LOOKAROUND, window_end + LOOKAROUND, now)
    return generate_slots(
        rules=_rules(ids).get(mentor.pk, []),
        extra_available=extra.get(mentor.pk, []),
        unavailable=blocked.get(mentor.pk, []),
        busy=busy.get(mentor.pk, []),
        duration_minutes=duration_minutes,
        buffer_minutes=mentor.buffer_minutes,
        window_start=window_start,
        window_end=window_end,
        earliest_start=now + timedelta(hours=mentor.min_notice_hours),
        latest_start=now + timedelta(days=mentor.booking_horizon_days),
        step_minutes=settings.SLOT_STEP_MINUTES,
    )


def next_available_map(mentors: list[MentorProfile], now: datetime | None = None) -> dict:
    """{mentor_id: earliest open slot for the mentor's shortest active service, or None}. Batched queries."""
    now = now or timezone.now()
    if not mentors:
        return {}
    ids = [m.pk for m in mentors]
    window_end = now + timedelta(days=NEXT_AVAILABLE_HORIZON_DAYS)
    durations = dict(
        MentorService.objects.filter(mentor_id__in=ids, is_active=True)
        .values("mentor_id")
        .annotate(d=Min("duration_minutes"))
        .values_list("mentor_id", "d")
    )
    rules = _rules(ids)
    extra, blocked = _exceptions(ids, now, window_end + LOOKAROUND)
    busy = _busy_intervals(ids, now, window_end + LOOKAROUND, now)

    result: dict = {}
    for mentor in mentors:
        duration = durations.get(mentor.pk)
        if duration is None or not mentor.is_accepting_bookings:
            result[mentor.pk] = None
            continue
        slots = generate_slots(
            rules=rules.get(mentor.pk, []),
            extra_available=extra.get(mentor.pk, []),
            unavailable=blocked.get(mentor.pk, []),
            busy=busy.get(mentor.pk, []),
            duration_minutes=duration,
            buffer_minutes=mentor.buffer_minutes,
            window_start=now,
            window_end=min(window_end, now + timedelta(days=mentor.booking_horizon_days, minutes=1)),
            earliest_start=now + timedelta(hours=mentor.min_notice_hours),
            latest_start=now + timedelta(days=mentor.booking_horizon_days),
            step_minutes=settings.SLOT_STEP_MINUTES,
        )
        result[mentor.pk] = slots[0] if slots else None
    return result


def utc_day_start(day) -> datetime:
    return datetime(day.year, day.month, day.day, tzinfo=UTC)
