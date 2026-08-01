"""Shape of a per-assessment-year rule set. Every AY module fills this in explicitly —
no rule is ever inherited silently from a prior year, so a missed Budget change can't
leak forward unnoticed.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SlabBracket:
    upto: int | None  # None = no upper bound
    rate: float  # e.g. 0.05 for 5%


@dataclass(frozen=True)
class SurchargeBracket:
    income_above: int
    rate: float
    capped_regime: str | None = (
        None  # "old" caps surcharge at 25% even above 5Cr for AMT-like heads
    )


@dataclass(frozen=True)
class RegimeRules:
    slabs: tuple[SlabBracket, ...]
    standard_deduction: int
    rebate_87a_income_limit: int  # total income at/below which rebate nullifies tax
    rebate_87a_max_amount: int
    surcharge: tuple[SurchargeBracket, ...]
    surcharge_cap_rate: float  # max surcharge rate regardless of income (post-2023: 25% new regime)
    cess_rate: float = 0.04
    max_80ccd2_pct_of_salary: float = (
        0.10  # employer NPS cap as % of (basic+DA); new regime raises this
    )
    allowed_deductions: frozenset[str] = frozenset()  # which Deductions fields apply in this regime


@dataclass(frozen=True)
class AssessmentYearRules:
    assessment_year: str
    old_regime: RegimeRules
    new_regime: RegimeRules
    ltcg_112a_exemption: int  # equity LTCG exemption threshold
    ltcg_112a_rate: float
    stcg_111a_rate: float
    ltcg_other_rate: float  # non-equity LTCG (post July 2024: 12.5% no indexation for most assets)
    section_80c_cap: int
    section_80ccd_1b_cap: int
    section_80d_self_family_cap: int
    section_80d_self_family_cap_senior: int
    section_80d_parents_cap: int
    section_80d_parents_cap_senior: int
    section_80tta_cap: int
    section_80ttb_cap: int
    house_property_loss_setoff_cap: int  # 2,00,000 against other heads, rest carried forward
    rounding_unit: int = 10  # Section 288A/288B: round to nearest 10
