"""Pure slot-engine tests (no database)."""

from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta

from apps.mentors.slots import Interval, generate_slots


@dataclass
class Rule:
    weekday: int
    start_time: time
    end_time: time
    timezone: str = "UTC"


def dt(*args):
    return datetime(*args, tzinfo=UTC)


MONDAY = dt(2026, 11, 2)  # a Monday


def slots(rules, *, busy=(), duration=60, buffer=0, start=MONDAY, days=1, earliest=None, latest=None, **kw):
    return generate_slots(
        rules=rules,
        busy=busy,
        duration_minutes=duration,
        buffer_minutes=buffer,
        window_start=start,
        window_end=start + timedelta(days=days),
        earliest_start=earliest or start,
        latest_start=latest or start + timedelta(days=365),
        step_minutes=30,
        **kw,
    )


def test_slots_fit_inside_weekly_hours():
    result = slots([Rule(0, time(9), time(12))])
    assert result == [dt(2026, 11, 2, h, m) for h, m in [(9, 0), (9, 30), (10, 0), (10, 30), (11, 0)]]


def test_busy_range_plus_buffer_blocks_overlapping_starts():
    busy = [Interval(dt(2026, 11, 2, 10), dt(2026, 11, 2, 11, 15))]  # 10:00 session, 15 min buffer
    result = slots([Rule(0, time(9), time(13))], busy=busy, buffer=15)
    # A 9:00 start would block until 10:15 → overlaps; 11:30 is the first start after the busy range.
    assert dt(2026, 11, 2, 9) not in result
    assert dt(2026, 11, 2, 11) not in result
    assert result[0] == dt(2026, 11, 2, 11, 30)


def test_minimum_notice_and_horizon():
    result = slots([Rule(0, time(9), time(17))], earliest=dt(2026, 11, 2, 12), latest=dt(2026, 11, 2, 14))
    assert result[0] == dt(2026, 11, 2, 12)
    assert result[-1] == dt(2026, 11, 2, 14)


def test_exceptions_add_and_remove_time():
    rules = [Rule(0, time(9), time(12))]
    blocked = slots(rules, unavailable=[Interval(dt(2026, 11, 2, 9), dt(2026, 11, 2, 11))])
    assert blocked == [dt(2026, 11, 2, 11)]
    extra = slots(rules, extra_available=[Interval(dt(2026, 11, 2, 18), dt(2026, 11, 2, 19))])
    assert dt(2026, 11, 2, 18) in extra


def test_rules_follow_daylight_saving_time():
    london_monday_9am = [Rule(0, time(9), time(10), "Europe/London")]
    # 2026-10-26 is the Monday after clocks go back (GMT, UTC+0); 2026-10-19 is in BST (UTC+1).
    before = slots(london_monday_9am, start=dt(2026, 10, 19))
    after = slots(london_monday_9am, start=dt(2026, 10, 26))
    assert before == [dt(2026, 10, 19, 8)]
    assert after == [dt(2026, 10, 26, 9)]


def test_rule_in_other_timezone_crossing_midnight_utc():
    # Monday 08:00–09:00 in Tokyo is Sunday 23:00–00:00 UTC.
    result = slots([Rule(0, time(8), time(9), "Asia/Tokyo")], start=dt(2026, 11, 1), days=2)
    assert result == [dt(2026, 11, 1, 23)]
