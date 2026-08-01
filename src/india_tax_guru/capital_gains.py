"""Capital gains computation.

Edge cases handled:
- Equity STCG (111A) taxed flat, separate from slab income.
- Equity LTCG (112A) exempt up to a per-year threshold, remainder taxed flat.
- Non-equity LTCG (property, debt post-2023 reclassification, gold) taxed at the
  "other" LTCG rate — indexation benefit is NOT modelled (Finance Act 2024 removed
  indexation for most assets acquired before 23 July 2024 with an optional
  pre-2024 12.5%-no-indexation-vs-20%-with-indexation choice for resident
  individuals on immovable property — that choice is out of scope for v1 and must
  be computed manually).
- Losses within a lot list net against gains of the SAME class/term first (intra-head
  set-off); cross-class netting (e.g. STCG loss vs LTCG gain) follows section 70/74
  rules loosely: short-term loss can offset both STCG and LTCG, long-term loss can
  offset only LTCG. Carry-forward of unabsorbed losses is NOT modelled (out of scope
  for a single-year calculator) — a negative net is reported, not silently zeroed.
"""

from dataclasses import dataclass

from .models import CapitalGainLot
from .rules.base import AssessmentYearRules


@dataclass(frozen=True)
class CapitalGainsResult:
    stcg_111a_net: int  # equity STCG, after intra-class loss set-off
    stcg_other_net: int  # non-equity STCG, taxed at slab rate (added to normal income)
    ltcg_112a_taxable: int  # equity LTCG above exemption threshold
    ltcg_other_net: int  # non-equity LTCG
    tax_on_capital_gains: int
    unabsorbed_loss_note: str | None  # non-None if a negative net couldn't be fully set off


_EQUITY_CLASSES = {"equity_listed", "equity_mf"}


def compute_capital_gains(
    lots: list[CapitalGainLot], rules: AssessmentYearRules
) -> CapitalGainsResult:
    equity_st = sum(
        lot.gain for lot in lots if lot.asset_class in _EQUITY_CLASSES and not lot.is_long_term
    )
    equity_lt = sum(
        lot.gain for lot in lots if lot.asset_class in _EQUITY_CLASSES and lot.is_long_term
    )
    other_st = sum(
        lot.gain for lot in lots if lot.asset_class not in _EQUITY_CLASSES and not lot.is_long_term
    )
    other_lt = sum(
        lot.gain for lot in lots if lot.asset_class not in _EQUITY_CLASSES and lot.is_long_term
    )

    note = None

    # Short-term losses (either bucket) can offset long-term gains within their own head;
    # long-term losses can only offset long-term gains. Keep it simple and conservative:
    # net each head internally, then let a residual short-term loss offset long-term gain.
    st_total = equity_st + other_st
    lt_total = equity_lt + other_lt

    if st_total < 0 and lt_total > 0:
        offset = min(-st_total, lt_total)
        lt_total -= offset
        st_total += offset

    if st_total < 0 or lt_total < 0:
        note = (
            "Net capital loss of "
            f"{min(st_total, 0) + min(lt_total, 0)} could not be set off against gains this year; "
            "carry-forward to future years (section 74) is not modelled by this tool."
        )

    stcg_111a_net = (
        max(0, equity_st) if equity_st > 0 else max(0, st_total if equity_lt <= 0 else 0)
    )
    # Simplify: apply flat rate only to the portion attributable to equity STCG, floored at 0.
    stcg_111a_net = max(0, min(equity_st, st_total)) if equity_st > 0 else 0
    stcg_other_net = max(0, st_total - stcg_111a_net)

    ltcg_112a_gross = max(0, min(equity_lt, lt_total)) if equity_lt > 0 else 0
    ltcg_112a_taxable = max(0, ltcg_112a_gross - rules.ltcg_112a_exemption)
    ltcg_other_net = max(0, lt_total - ltcg_112a_gross)

    tax = (
        round(stcg_111a_net * rules.stcg_111a_rate)
        + round(ltcg_112a_taxable * rules.ltcg_112a_rate)
        + round(ltcg_other_net * rules.ltcg_other_rate)
    )

    return CapitalGainsResult(
        stcg_111a_net=stcg_111a_net,
        stcg_other_net=stcg_other_net,
        ltcg_112a_taxable=ltcg_112a_taxable,
        ltcg_other_net=ltcg_other_net,
        tax_on_capital_gains=tax,
        unabsorbed_loss_note=note,
    )
