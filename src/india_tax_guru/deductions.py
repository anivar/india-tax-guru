"""Chapter VI-A deductions: statutory caps, regime gating, and qualifying limits.

Edge cases handled:
- The new regime allows nothing from Chapter VI-A except 80CCD(2) employer NPS (handled
  in salary.py, since its cap is a percentage of salary rather than a flat amount).
  Everything else is zeroed HERE rather than merely ignored by the caller, so a claimed
  deduction cannot survive into the new regime by accident, and every zeroed head is
  reported back so the user can see what the regime cost them.
- 80D caps depend on whether the taxpayer and the parents are senior citizens, which are
  two independent tests — a 40-year-old supporting senior parents gets 25,000 + 50,000.
- 80TTA (below 60, savings interest only, 10,000) and 80TTB (senior, all interest
  including fixed deposits, 50,000) are mutually exclusive by age; the caller supplies
  whichever figure applies and this module applies the right cap.
- 80DDB is capped at 40,000, or 1,00,000 where the patient is a senior citizen.
- 80G donations must already be reduced to their deductible amount (the 50%/100% rate
  applied) by the caller, because the rate depends on the specific donee. What is applied
  here is the 10%-of-gross-total-income qualifying limit, which depends on income the
  caller may not have computed yet.
- 80E (education loan interest) has no monetary cap — deliberately uncapped.
- `other_chapter_via` is an uncapped escape hatch for heads this tool does not model.
  Because it bypasses every statutory limit, using it emits a warning rather than
  silently inflating the deduction.
"""

from dataclasses import dataclass, field

from .models import AgeBand, Deductions
from .rules.base import AssessmentYearRules


@dataclass(frozen=True)
class DeductionResult:
    total: int
    breakdown: dict[str, int]
    zeroed_by_regime: list[str]
    notes: list[str] = field(default_factory=list)


def compute_deductions(
    deductions: Deductions,
    age_band: AgeBand,
    rules: AssessmentYearRules,
    regime: str,
    gross_total_income: int,
) -> DeductionResult:
    regime_rules = rules.old_regime if regime == "old" else rules.new_regime
    allowed = regime_rules.allowed_deductions
    notes: list[str] = []

    is_senior = age_band != AgeBand.BELOW_60
    interest_cap = rules.section_80ttb_cap if is_senior else rules.section_80tta_cap

    section_80g = deductions.section_80g_deductible
    if section_80g and deductions.section_80g_subject_to_qualifying_limit:
        qualifying_cap = round(gross_total_income * rules.section_80g_qualifying_pct_of_gti)
        if section_80g > qualifying_cap:
            notes.append(
                f"80G restricted to the qualifying limit of "
                f"{rules.section_80g_qualifying_pct_of_gti:.0%} of gross total income "
                f"({qualifying_cap:,}); {section_80g - qualifying_cap:,} disallowed."
            )
            section_80g = qualifying_cap

    if deductions.other_chapter_via > 0:
        notes.append(
            f"`other_chapter_via` of {deductions.other_chapter_via:,} was applied with NO "
            "statutory cap — this field bypasses all limit checking and is the caller's "
            "responsibility to verify."
        )

    raw = {
        "section_80c": min(deductions.section_80c, rules.section_80c_cap),
        "section_80ccd_1b": min(deductions.section_80ccd_1b, rules.section_80ccd_1b_cap),
        "section_80d_self_family": min(
            deductions.section_80d_self_family,
            rules.section_80d_self_family_cap_senior
            if is_senior
            else rules.section_80d_self_family_cap,
        ),
        "section_80d_parents": min(
            deductions.section_80d_parents,
            rules.section_80d_parents_cap_senior
            if deductions.parents_are_senior_citizens
            else rules.section_80d_parents_cap,
        ),
        "section_80tta_or_ttb": min(deductions.section_80tta_or_ttb, interest_cap),
        "section_80e_education_loan_interest": deductions.section_80e_education_loan_interest,
        "section_80ddb": min(
            deductions.section_80ddb,
            rules.section_80ddb_cap_senior if is_senior else rules.section_80ddb_cap,
        ),
        "section_80g": section_80g,
        "other_chapter_via": deductions.other_chapter_via,
    }

    breakdown: dict[str, int] = {}
    zeroed: list[str] = []
    for key, value in raw.items():
        if key in allowed:
            breakdown[key] = value
        else:
            breakdown[key] = 0
            if value > 0:
                zeroed.append(key)

    # Chapter VI-A deductions cannot exceed gross total income.
    total = sum(breakdown.values())
    if total > max(0, gross_total_income):
        notes.append(
            f"Chapter VI-A deductions ({total:,}) restricted to gross total income "
            f"({max(0, gross_total_income):,}); they cannot create or increase a loss."
        )
        total = max(0, gross_total_income)

    return DeductionResult(
        total=total, breakdown=breakdown, zeroed_by_regime=zeroed, notes=notes
    )
