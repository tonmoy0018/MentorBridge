"""
Marketplace commission (docs/PAYMENTS.md §4). All amounts are integer minor units (cents).

    commission   = round_half_up(gross × commission_bps / 10 000)
    mentor share = gross − commission

Example: $40.00 at 1500 bps (15%) → commission $6.00, mentor share $34.00.
"""

from dataclasses import dataclass

from django.conf import settings

BPS = 10_000


@dataclass(frozen=True)
class Breakdown:
    gross_cents: int
    commission_bps: int
    commission_cents: int
    mentor_share_cents: int


def _round_half_up_div(numerator: int, denominator: int) -> int:
    return (numerator * 2 + denominator) // (denominator * 2)


def breakdown(gross_cents: int, commission_bps: int) -> Breakdown:
    if gross_cents < 0:
        raise ValueError("gross_cents must be non-negative")
    if not 0 <= commission_bps <= BPS:
        raise ValueError("commission_bps must be between 0 and 10000")
    commission = _round_half_up_div(gross_cents * commission_bps, BPS)
    return Breakdown(gross_cents, commission_bps, commission, gross_cents - commission)


def commission_bps_for(mentor) -> int:
    """The mentor's admin-set override, or the platform default."""
    override = getattr(mentor, "commission_bps", None)
    return settings.PLATFORM_FEE_BPS if override is None else override


def proportional_reversal(payment, amount_cents: int) -> tuple[int, int]:
    """
    Split a refund (or lost dispute) of `amount_cents` into (commission reversed, mentor share
    reversed), in proportion to the original breakdown. The last refund absorbs rounding so the
    totals never exceed what was recorded.
    """
    already = payment.refunds.filter(status__in=["pending", "succeeded"])
    commission_left = payment.platform_fee_cents - sum(r.commission_reversed_cents for r in already)
    remaining = payment.amount_cents - sum(r.amount_cents for r in already)
    if amount_cents == remaining:
        commission = commission_left
    else:
        commission = min(
            _round_half_up_div(payment.platform_fee_cents * amount_cents, payment.amount_cents),
            commission_left,
        )
    return commission, amount_cents - commission
