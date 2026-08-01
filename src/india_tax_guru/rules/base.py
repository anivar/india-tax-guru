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


@dataclass(frozen=True)
class RegimeRules:
    """Rules for one regime (old or new) in one assessment year.

    Slabs vary by age ONLY in the old regime (raised basic exemption for senior and
    super-senior citizens). `slabs_senior`/`slabs_super_senior` are None in the new
    regime, which has a single age-independent structure — expressed as None rather
    than duplicated tuples so a future age concession can't be half-applied.
    """

    slabs: tuple[SlabBracket, ...]  # below 60
    standard_deduction: int
    rebate_87a_income_limit: int  # total income at/below which rebate applies
    rebate_87a_max_amount: int
    rebate_87a_has_marginal_relief: bool  # new regime only; no such relief in the old regime
    surcharge: tuple[SurchargeBracket, ...]
    surcharge_cap_rate: float  # max surcharge rate regardless of income
    # Surcharge on tax attributable to s.111A / s.112A / s.112 gains and dividend income
    # is capped at this rate even when the taxpayer's general surcharge rate is higher.
    surcharge_special_income_cap_rate: float
    allows_professional_tax: bool  # s.16(iii)
    allows_hra_and_10_14: bool  # s.10(13A) and most s.10(14) allowances
    allows_self_occupied_interest: bool  # s.24(b) on self-occupied property
    allows_house_property_loss_setoff: bool  # set-off of HP loss against other heads
    max_80ccd2_pct_of_salary: float  # employer NPS cap as % of (basic+DA)
    allowed_deductions: frozenset[str]  # which Deductions fields apply in this regime
    slabs_senior: tuple[SlabBracket, ...] | None = None  # age 60-80
    slabs_super_senior: tuple[SlabBracket, ...] | None = None  # age 80+
    cess_rate: float = 0.04


@dataclass(frozen=True)
class AssessmentYearRules:
    assessment_year: str
    old_regime: RegimeRules
    new_regime: RegimeRules
    ltcg_112a_exemption: int  # equity LTCG annual exemption threshold
    ltcg_112a_rate: float
    stcg_111a_rate: float
    ltcg_other_rate: float  # non-equity LTCG
    section_80c_cap: int
    section_80ccd_1b_cap: int
    section_80d_self_family_cap: int
    section_80d_self_family_cap_senior: int
    section_80d_parents_cap: int
    section_80d_parents_cap_senior: int
    section_80ddb_cap: int
    section_80ddb_cap_senior: int
    section_80tta_cap: int
    section_80ttb_cap: int
    section_80g_qualifying_pct_of_gti: float  # 10% qualifying-limit ceiling for capped donations
    self_occupied_interest_cap: int  # s.24(b), AGGREGATE across all self-occupied properties
    house_property_loss_setoff_cap: int  # s.71(3A), AGGREGATE across all properties
    rounding_unit: int = 10  # s.288A/288B: round to nearest 10
