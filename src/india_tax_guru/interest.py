"""Interest for shortfall in advance tax — sections 234B and 234C.

Edge cases handled:
- s.234C carries a statutory TOLERANCE on the first two instalments: no interest is
  charged if at least 12% of the assessed tax was paid by 15 June, or at least 36% by
  15 September, even though the nominal requirements are 15% and 45%. Treating the
  nominal figures as hard requirements charges interest the law does not.
- Rule 119A: the amount on which interest is computed is rounded DOWN to the nearest
  hundred rupees before applying the rate, in both s.234B and s.234C.
- s.234C is charged checkpoint by checkpoint: a shortfall at an early instalment that is
  made good later still attracts interest for the months it was short, so netting only
  the year-end position understates the charge.
- s.234B applies only where advance tax paid is less than 90% of the assessed tax, at 1%
  per month (simple) on the shortfall from 1 April of the assessment year until payment.
- KNOWN LIMITATION: s.234C has a further carve-out where the shortfall arises from
  capital gains, lottery winnings, or first-time business income that arose AFTER the
  instalment due date. Modelling it needs transaction-level dates, so it is not applied
  here — for such taxpayers this module OVERSTATES s.234C interest. A note says so on
  every result rather than only in this docstring.
- s.234A (late filing) needs the actual filing date and is exposed separately rather
  than being folded in with an assumed date.
"""

import math
from dataclasses import dataclass, field

#: Cumulative advance-tax requirement at 15 Jun / 15 Sep / 15 Dec / 15 Mar.
_REQUIRED_PCT = (0.15, 0.45, 0.75, 1.00)
#: Safe-harbour percentages: meeting these means no s.234C interest for that instalment.
_TOLERANCE_PCT = (0.12, 0.36, 0.75, 1.00)
#: Months of interest charged when an instalment falls short.
_MONTHS_IF_SHORT = (3, 3, 3, 1)
_CHECKPOINT_NAMES = ("15 Jun", "15 Sep", "15 Dec", "15 Mar")


@dataclass(frozen=True)
class InterestResult:
    section_234b: int
    section_234c: int
    total: int
    notes: list[str] = field(default_factory=list)


def _round_down_119a(amount: int) -> int:
    """Rule 119A: round the base for interest down to the nearest 100 rupees."""
    return max(0, (amount // 100) * 100)


def _simple_interest(principal: int, months: int, rate_pct: float = 1.0) -> int:
    base = _round_down_119a(principal)
    if base <= 0 or months <= 0:
        return 0
    return round(base * (rate_pct / 100) * months)


def section_234b_interest(assessed_tax: int, advance_tax_paid: int, months_elapsed: int) -> int:
    if assessed_tax <= 0 or advance_tax_paid >= 0.90 * assessed_tax:
        return 0
    return _simple_interest(assessed_tax - advance_tax_paid, months_elapsed)


def section_234c_interest(
    assessed_tax: int, cumulative_paid_by_checkpoint: list[int]
) -> tuple[int, list[str]]:
    """`cumulative_paid_by_checkpoint`: cumulative advance tax as of each of the four dates."""
    if len(cumulative_paid_by_checkpoint) != 4:
        raise ValueError(
            "expected exactly 4 cumulative advance-tax figures (15 Jun / 15 Sep / 15 Dec / 15 Mar)"
        )
    if assessed_tax <= 0:
        return 0, []

    notes: list[str] = []
    total = 0
    for i, (required_pct, tolerance_pct, months) in enumerate(
        zip(_REQUIRED_PCT, _TOLERANCE_PCT, _MONTHS_IF_SHORT, strict=True)
    ):
        paid = cumulative_paid_by_checkpoint[i]
        if paid >= math.floor(assessed_tax * tolerance_pct):
            continue
        shortfall = math.ceil(assessed_tax * required_pct) - paid
        if shortfall <= 0:
            continue
        interest = _simple_interest(shortfall, months)
        total += interest
        notes.append(
            f"s.234C {_CHECKPOINT_NAMES[i]}: shortfall {shortfall:,}, interest {interest:,}"
        )
    return total, notes


def compute_advance_tax_interest(
    assessed_tax: int,
    advance_tax_paid_total: int,
    cumulative_paid_by_checkpoint: list[int],
    months_elapsed_234b: int,
) -> InterestResult:
    b = section_234b_interest(assessed_tax, advance_tax_paid_total, months_elapsed_234b)
    c, notes = section_234c_interest(assessed_tax, cumulative_paid_by_checkpoint)
    if c > 0:
        notes.append(
            "s.234C does not apply to a shortfall caused by capital gains or other income "
            "arising after an instalment due date; that carve-out is not modelled, so this "
            "figure may be overstated for such taxpayers."
        )
    return InterestResult(section_234b=b, section_234c=c, total=b + c, notes=notes)


def section_234a_interest(
    tax_payable_on_filing: int, months_late: int, rate_pct: float = 1.0
) -> int:
    """s.234A: interest on tax still unpaid when a return is filed after the due date."""
    return _simple_interest(tax_payable_on_filing, months_late, rate_pct)
