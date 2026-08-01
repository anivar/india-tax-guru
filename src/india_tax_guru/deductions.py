"""Chapter VI-A deduction totalling, regime-aware.

Edge cases handled:
- New regime allows almost nothing from Chapter VI-A except 80CCD(2) (employer NPS,
  handled separately in salary.py) — everything else is zeroed out here, not just
  "ignored by the caller", so a caller can't accidentally double count it.
- 80D caps depend on whether self/family and parents are senior citizens.
- 80TTA (non-senior, savings interest only, cap 10k) vs 80TTB (senior, ALL interest
  incl. FD, cap 50k) are mutually exclusive by age — the caller supplies whichever
  figure applies to `section_80tta_or_ttb`; this module just applies the right cap.
"""

from dataclasses import dataclass

from .models import AgeBand, Deductions
from .rules.base import AssessmentYearRules


@dataclass(frozen=True)
class DeductionResult:
    total: int
    breakdown: dict[str, int]
    zeroed_by_regime: list[str]


def compute_deductions(
    deductions: Deductions,
    age_band: AgeBand,
    rules: AssessmentYearRules,
    regime: str,  # "old" or "new"
) -> DeductionResult:
    regime_rules = rules.old_regime if regime == "old" else rules.new_regime
    allowed = regime_rules.allowed_deductions

    is_senior = age_band != AgeBand.BELOW_60
    interest_cap = rules.section_80ttb_cap if is_senior else rules.section_80tta_cap

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
        "section_80g": deductions.section_80g,
        "section_80ddb": deductions.section_80ddb,
        "other_chapter_via": deductions.other_chapter_via,
    }

    breakdown = {}
    zeroed = []
    for key, value in raw.items():
        if key in allowed:
            breakdown[key] = value
        else:
            breakdown[key] = 0
            if value > 0:
                zeroed.append(key)

    return DeductionResult(
        total=sum(breakdown.values()), breakdown=breakdown, zeroed_by_regime=zeroed
    )
