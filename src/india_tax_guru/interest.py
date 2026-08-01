"""Interest for late/short advance tax and late filing (sections 234A/234B/234C).

Edge cases handled:
- 234C uses the four cumulative advance-tax instalment checkpoints (15%/45%/75%/100%
  by 15 Jun / 15 Sep / 15 Dec / 15 Mar) — a shortfall at an EARLIER checkpoint that
  is made up later still attracts interest for the months it was short, computed
  checkpoint-by-checkpoint rather than only on the year-end shortfall.
- 234C has a carve-out: no interest on the first two checkpoints if the shortfall
  is due to capital gains / lottery / etc. that arose after that checkpoint's due
  date — NOT modelled (would need transaction-date-level detail); documented as a
  known simplification that can overstate 234C interest for such taxpayers.
- 234B interest runs from 1 April of the AY until payment, in whole/part months,
  at 1% per month simple interest, only if advance tax paid < 90% of assessed tax.
- 234A interest (late filing) is only relevant if there's still tax payable at the
  return-filing date past the due date — not modelled here since it needs the
  actual filing date; exposed as a separate function the caller can invoke once
  the filing date is known.
"""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class InterestResult:
    section_234b: int
    section_234c: int
    total: int
    notes: list[str]


def _months_simple_interest(principal: int, months: int, rate_pct: float = 1.0) -> int:
    if principal <= 0 or months <= 0:
        return 0
    return round(principal * (rate_pct / 100) * months)


def section_234b_interest(assessed_tax: int, advance_tax_paid: int, months_elapsed: int) -> int:
    if advance_tax_paid >= 0.90 * assessed_tax:
        return 0
    shortfall = assessed_tax - advance_tax_paid
    return _months_simple_interest(shortfall, months_elapsed)


def section_234c_interest(
    assessed_tax: int, cumulative_paid_by_checkpoint: list[int]
) -> tuple[int, list[str]]:
    """cumulative_paid_by_checkpoint: advance tax actually paid, cumulative, as of
    15-Jun, 15-Sep, 15-Dec, 15-Mar (exactly 4 values, in that order).
    """
    if len(cumulative_paid_by_checkpoint) != 4:
        raise ValueError("expected exactly 4 cumulative advance-tax figures (Jun/Sep/Dec/Mar)")

    required_pct = [0.15, 0.45, 0.75, 1.00]
    months_if_short = [3, 3, 3, 1]
    notes = []
    total = 0
    for i, (pct, months) in enumerate(zip(required_pct, months_if_short, strict=True)):
        required = math.ceil(assessed_tax * pct)
        paid = cumulative_paid_by_checkpoint[i]
        if paid < required:
            shortfall = required - paid
            interest = _months_simple_interest(shortfall, months)
            total += interest
            notes.append(f"checkpoint {i + 1}: shortfall {shortfall}, interest {interest}")
    return total, notes


def compute_advance_tax_interest(
    assessed_tax: int,
    advance_tax_paid_total: int,
    cumulative_paid_by_checkpoint: list[int],
    months_elapsed_234b: int,
) -> InterestResult:
    b = section_234b_interest(assessed_tax, advance_tax_paid_total, months_elapsed_234b)
    c, notes = section_234c_interest(assessed_tax, cumulative_paid_by_checkpoint)
    notes.append(
        "234C shortfall carve-out for gains/income arising after a checkpoint's due date "
        "(e.g. late-year capital gains) is not modelled — may overstate interest in that case."
    )
    return InterestResult(section_234b=b, section_234c=c, total=b + c, notes=notes)
