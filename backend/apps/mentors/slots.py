"""
Pure slot-generation engine (no database access) so it can be unit-tested exhaustively.

Weekly rules are wall-clock times in an IANA timezone; they're expanded day by day with
zoneinfo, so DST changes are handled per date. Everything returned is an aware UTC datetime.
A candidate start `t` is offered only if the whole blocked range [t, t + duration + buffer)
avoids every busy range — the same rule the database exclusion constraint enforces.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo


class RuleLike(Protocol):
    weekday: int
    start_time: time
    end_time: time
    timezone: str


@dataclass(frozen=True, order=True)
class Interval:
    start: datetime
    end: datetime


def _local_dates(window_start: datetime, window_end: datetime, tz: ZoneInfo) -> Iterable[date]:
    day = window_start.astimezone(tz).date() - timedelta(days=1)
    last = window_end.astimezone(tz).date() + timedelta(days=1)
    while day <= last:
        yield day
        day += timedelta(days=1)


def rule_intervals(rules: Iterable[RuleLike], window_start: datetime, window_end: datetime) -> list[Interval]:
    intervals: list[Interval] = []
    for rule in rules:
        tz = ZoneInfo(rule.timezone)
        for day in _local_dates(window_start, window_end, tz):
            if day.weekday() != rule.weekday:
                continue
            start = datetime.combine(day, rule.start_time, tzinfo=tz).astimezone(UTC)
            end = datetime.combine(day, rule.end_time, tzinfo=tz).astimezone(UTC)
            if end > start and end > window_start and start < window_end:
                intervals.append(Interval(start, end))
    return intervals


def merge(intervals: Iterable[Interval]) -> list[Interval]:
    merged: list[Interval] = []
    for interval in sorted(intervals):
        if merged and interval.start <= merged[-1].end:
            merged[-1] = Interval(merged[-1].start, max(merged[-1].end, interval.end))
        else:
            merged.append(interval)
    return merged


def subtract(intervals: Sequence[Interval], blocks: Iterable[Interval]) -> list[Interval]:
    result = list(intervals)
    for block in merge(blocks):
        next_result: list[Interval] = []
        for interval in result:
            if block.end <= interval.start or block.start >= interval.end:
                next_result.append(interval)
                continue
            if interval.start < block.start:
                next_result.append(Interval(interval.start, block.start))
            if block.end < interval.end:
                next_result.append(Interval(block.end, interval.end))
        result = next_result
    return result


def generate_slots(
    *,
    rules: Iterable[RuleLike],
    extra_available: Iterable[Interval] = (),
    unavailable: Iterable[Interval] = (),
    busy: Iterable[Interval] = (),
    duration_minutes: int,
    buffer_minutes: int,
    window_start: datetime,
    window_end: datetime,
    earliest_start: datetime,
    latest_start: datetime,
    step_minutes: int,
) -> list[datetime]:
    """Bookable session start times in [window_start, window_end), sorted, UTC."""
    duration = timedelta(minutes=duration_minutes)
    blocked = timedelta(minutes=duration_minutes + buffer_minutes)
    step = timedelta(minutes=step_minutes)
    busy_list = list(busy)

    available = subtract(
        merge([*rule_intervals(rules, window_start, window_end), *extra_available]), unavailable
    )

    lower = max(window_start, earliest_start)
    slots: list[datetime] = []
    for interval in available:
        t = interval.start
        while t + duration <= interval.end:
            if lower <= t < window_end and t <= latest_start:
                end = t + blocked
                if not any(b.start < end and t < b.end for b in busy_list):
                    slots.append(t)
            t += step
    return sorted(set(slots))
