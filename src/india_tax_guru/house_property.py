"""Income and loss from house property, computed across ALL properties together.

Edge cases handled:
- The s.24(b) self-occupied interest cap of 2,00,000 and the s.71(3A) cap of 2,00,000
  on setting off house-property loss against other heads are AGGREGATE limits, not
  per-property. Computing them property-by-property lets a taxpayer with two
  self-occupied houses claim 4,00,000 — hence this module takes the whole list rather
  than one property at a time.
- Under the new regime (s.115BAC) interest on a SELF-OCCUPIED property is not
  deductible at all, and a house-property loss cannot be set off against any other
  head. Both are driven off explicit per-regime flags rather than left to the caller.
- Let-out property: Net Annual Value = rent received less municipal taxes actually
  paid; a flat 30% standard deduction on NAV; interest deductible without cap.
- Loss that exceeds the set-off cap is carried forward for up to 8 assessment years.
  Carry-forward is out of scope for a single-year calculator, so the unabsorbed amount
  is reported explicitly rather than dropped.
- Pre-construction interest (deductible in five equal instalments from the year of
  completion) is NOT modelled; a property flagged under construction produces a note.
"""

from dataclasses import dataclass, field

from .models import HouseProperty
from .rules.base import AssessmentYearRules, RegimeRules


@dataclass(frozen=True)
class HousePropertyResult:
    net_income_or_loss: int  # positive = income; negative = loss before the set-off cap
    set_off_against_other_heads: int  # <= 0; the loss actually reducing other income
    contribution_to_total_income: int  # what the caller adds to gross total income
    carried_forward_loss: int
    notes: list[str] = field(default_factory=list)


def compute_house_properties(
    properties: list[HouseProperty],
    rules: AssessmentYearRules,
    regime_rules: RegimeRules,
) -> HousePropertyResult:
    if not properties:
        return HousePropertyResult(0, 0, 0, 0, [])

    notes: list[str] = []
    total = 0

    self_occupied_interest = sum(
        p.home_loan_interest for p in properties if p.is_self_occupied
    )
    if self_occupied_interest > 0:
        if not regime_rules.allows_self_occupied_interest:
            notes.append(
                f"Self-occupied home-loan interest of {self_occupied_interest:,} is not "
                "deductible under the new regime (s.115BAC) and has been disallowed."
            )
        else:
            allowed = min(self_occupied_interest, rules.self_occupied_interest_cap)
            if allowed < self_occupied_interest:
                notes.append(
                    f"Self-occupied interest capped at {rules.self_occupied_interest_cap:,} "
                    f"in aggregate (s.24(b)); {self_occupied_interest - allowed:,} disallowed."
                )
            total -= allowed

    for prop in properties:
        if prop.is_self_occupied:
            if prop.is_under_construction:
                notes.append(
                    "Pre-construction interest (five equal instalments from the year of "
                    "completion) is not modelled; only current-year interest was applied."
                )
            continue
        nav = max(0, prop.annual_rent_received - prop.municipal_taxes_paid)
        total += nav - round(nav * 0.30) - prop.home_loan_interest

    if total >= 0:
        return HousePropertyResult(total, 0, total, 0, notes)

    loss = -total
    if not regime_rules.allows_house_property_loss_setoff:
        notes.append(
            f"House-property loss of {loss:,} cannot be set off against other heads under "
            "the new regime (s.115BAC(2)); it is carried forward against future house-"
            "property income only. Carry-forward is not modelled by this tool."
        )
        return HousePropertyResult(total, 0, 0, loss, notes)

    set_off = min(loss, rules.house_property_loss_setoff_cap)
    carried = loss - set_off
    if carried > 0:
        notes.append(
            f"House-property loss of {loss:,} exceeds the {rules.house_property_loss_setoff_cap:,} "
            f"set-off cap (s.71(3A)); {carried:,} is carried forward. Carry-forward is not "
            "modelled by this tool."
        )
    return HousePropertyResult(total, -set_off, -set_off, carried, notes)
