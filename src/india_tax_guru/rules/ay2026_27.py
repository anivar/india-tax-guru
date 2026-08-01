"""AY 2026-27 (FY 2025-26) rules.

Source: Finance Act 2025 (Budget presented Feb 2025) — new regime slabs revised,
rebate raised so effective tax-free income is 12,00,000 (12,75,000 for salaried
after standard deduction). Old regime slabs unchanged from earlier years.

VERIFY against CBDT before relying on this for an actual filing — numbers here
reflect the drafting author's understanding at the time this module was written
and may miss a late amendment or clarification circular.
"""

from .base import AssessmentYearRules, RegimeRules, SlabBracket, SurchargeBracket

OLD_REGIME = RegimeRules(
    slabs=(
        SlabBracket(upto=250_000, rate=0.0),
        SlabBracket(upto=500_000, rate=0.05),
        SlabBracket(upto=1_000_000, rate=0.20),
        SlabBracket(upto=None, rate=0.30),
    ),
    standard_deduction=50_000,
    rebate_87a_income_limit=500_000,
    rebate_87a_max_amount=12_500,
    surcharge=(
        SurchargeBracket(income_above=5_000_000, rate=0.10),
        SurchargeBracket(income_above=10_000_000, rate=0.15),
        SurchargeBracket(income_above=20_000_000, rate=0.25),
        SurchargeBracket(income_above=50_000_000, rate=0.37),
    ),
    surcharge_cap_rate=0.37,
    max_80ccd2_pct_of_salary=0.10,
    allowed_deductions=frozenset(
        {
            "section_80c",
            "section_80ccd_1b",
            "section_80d_self_family",
            "section_80d_parents",
            "section_80tta_or_ttb",
            "section_80e_education_loan_interest",
            "section_80g",
            "section_80ddb",
            "other_chapter_via",
            "hra_exemption",
            "home_loan_interest_self_occupied",
        }
    ),
)

NEW_REGIME = RegimeRules(
    slabs=(
        SlabBracket(upto=400_000, rate=0.0),
        SlabBracket(upto=800_000, rate=0.05),
        SlabBracket(upto=1_200_000, rate=0.10),
        SlabBracket(upto=1_600_000, rate=0.15),
        SlabBracket(upto=2_000_000, rate=0.20),
        SlabBracket(upto=2_400_000, rate=0.25),
        SlabBracket(upto=None, rate=0.30),
    ),
    standard_deduction=75_000,
    rebate_87a_income_limit=1_200_000,
    rebate_87a_max_amount=60_000,
    surcharge=(
        SurchargeBracket(income_above=5_000_000, rate=0.10),
        SurchargeBracket(income_above=10_000_000, rate=0.15),
        SurchargeBracket(income_above=20_000_000, rate=0.25),
    ),
    surcharge_cap_rate=0.25,  # new regime caps surcharge at 25% even beyond 5Cr
    max_80ccd2_pct_of_salary=0.14,  # 14% for both govt and private employees under new regime
    allowed_deductions=frozenset(
        {
            "section_80ccd_2_employer_nps",  # tracked separately, not in Deductions model
        }
    ),
)

RULES = AssessmentYearRules(
    assessment_year="2026-27",
    old_regime=OLD_REGIME,
    new_regime=NEW_REGIME,
    ltcg_112a_exemption=1_250_000,
    ltcg_112a_rate=0.125,
    stcg_111a_rate=0.20,
    ltcg_other_rate=0.125,
    section_80c_cap=150_000,
    section_80ccd_1b_cap=50_000,
    section_80d_self_family_cap=25_000,
    section_80d_self_family_cap_senior=50_000,
    section_80d_parents_cap=25_000,
    section_80d_parents_cap_senior=50_000,
    section_80tta_cap=10_000,
    section_80ttb_cap=50_000,
    house_property_loss_setoff_cap=200_000,
    rounding_unit=10,
)
