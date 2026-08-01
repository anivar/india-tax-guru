"""AY 2025-26 (FY 2024-25) rules.

Source: Finance Act 2024 (July 2024 Budget) — new regime slabs revised mid-year
scheme, LTCG/STCG rates changed from 23 July 2024 (LTCG 10%->12.5%, STCG 15%->20%,
equity LTCG exemption 1,00,000->1,25,000). This module uses the post-23-July rates
for the full year as a simplification; a split-period computation for FY2024-25
transactions before/after 23 July is NOT implemented — treat this AY as approximate.

VERIFY against CBDT before relying on this for an actual filing.
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
        SlabBracket(upto=300_000, rate=0.0),
        SlabBracket(upto=700_000, rate=0.05),
        SlabBracket(upto=1_000_000, rate=0.10),
        SlabBracket(upto=1_200_000, rate=0.15),
        SlabBracket(upto=1_500_000, rate=0.20),
        SlabBracket(upto=None, rate=0.30),
    ),
    standard_deduction=75_000,
    rebate_87a_income_limit=700_000,
    rebate_87a_max_amount=25_000,
    surcharge=(
        SurchargeBracket(income_above=5_000_000, rate=0.10),
        SurchargeBracket(income_above=10_000_000, rate=0.15),
        SurchargeBracket(income_above=20_000_000, rate=0.25),
    ),
    surcharge_cap_rate=0.25,
    max_80ccd2_pct_of_salary=0.14,
    allowed_deductions=frozenset({"section_80ccd_2_employer_nps"}),
)

RULES = AssessmentYearRules(
    assessment_year="2025-26",
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
