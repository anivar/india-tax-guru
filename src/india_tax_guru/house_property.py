"""Income/loss from house property.

Edge cases handled:
- Self-occupied property: no rent income, but home loan interest is deductible
  up to 2,00,000 (old regime only; new regime disallows it — enforced by the
  caller via `allowed_deductions`, this module just returns the raw figure).
- Let-out property: standard 30% deduction on Net Annual Value (rent minus
  municipal taxes), no cap on interest deduction, and a resulting loss is capped
  at 2,00,000 for set-off against other heads in the same year
  (rules.house_property_loss_setoff_cap); any excess loss carries forward — NOT
  modelled here (single-year tool), returned as an explicit unabsorbed figure so
  it isn't silently dropped.
- Under-construction property: pre-construction interest (5 equal instalments from
  completion year) is NOT modelled in v1 — flagged via `is_under_construction`.
"""

from dataclasses import dataclass

from .models import HouseProperty


@dataclass(frozen=True)
class HousePropertyResult:
    income_or_loss: int  # for self-occupied: <= 0 (just the interest deduction, capped at 2L)
    set_off_this_year: int
    carried_forward_loss: int
    note: str | None


def compute_house_property(prop: HouseProperty, loss_setoff_cap: int) -> HousePropertyResult:
    if prop.is_self_occupied:
        interest_deduction = min(prop.home_loan_interest, 200_000)
        note = None
        if prop.is_under_construction:
            note = (
                "Pre-construction interest amortization (5 equal instalments from year of "
                "completion) is not modelled; only current-year interest was applied."
            )
        result = -interest_deduction
        set_off = min(-result, loss_setoff_cap)
        return HousePropertyResult(
            income_or_loss=result,
            set_off_this_year=-set_off,
            carried_forward_loss=max(0, -result - set_off),
            note=note,
        )

    nav = max(0, prop.annual_rent_received - prop.municipal_taxes_paid)
    standard_deduction = round(nav * 0.30)
    net = nav - standard_deduction - prop.home_loan_interest
    if net >= 0:
        return HousePropertyResult(
            income_or_loss=net, set_off_this_year=net, carried_forward_loss=0, note=None
        )

    loss = -net
    set_off = min(loss, loss_setoff_cap)
    carried = loss - set_off
    note = None
    if carried > 0:
        note = (
            f"Loss of {carried} exceeds the {loss_setoff_cap} set-off cap; "
            "carry-forward is not modelled."
        )
    return HousePropertyResult(
        income_or_loss=net, set_off_this_year=-set_off, carried_forward_loss=carried, note=note
    )
