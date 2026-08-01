"""AY 2026-27 (FY 2025-26) rules.

Source: Finance Act 2025 — new regime slabs revised and the s.87A rebate raised so
that a resident's effective tax-free total income under the new regime is 12,00,000
(12,75,000 for a salaried taxpayer after the 75,000 standard deduction). Old regime
slabs, standard deduction and Chapter VI-A caps unchanged from prior years.

Capital gains reflect the post-23-July-2024 Finance Act 2024 regime, which applies to
the whole of FY 2025-26: s.112A at 12.5% with a 1,25,000 exemption, s.111A at 20%,
other long-term gains at 12.5% without indexation.

VERIFY against CBDT before relying on this for an actual filing.
"""

from .base import AssessmentYearRules, RegimeRules, SlabBracket, SurchargeClause

# Old regime: basic exemption rises with age (2.5L / 3L / 5L). Super-seniors lose the
# 5% bracket entirely rather than merely shifting it, so all three are written out.
_OLD_SLABS_BELOW_60 = (
    SlabBracket(upto=250_000, rate=0.0),
    SlabBracket(upto=500_000, rate=0.05),
    SlabBracket(upto=1_000_000, rate=0.20),
    SlabBracket(upto=None, rate=0.30),
)
_OLD_SLABS_SENIOR = (
    SlabBracket(upto=300_000, rate=0.0),
    SlabBracket(upto=500_000, rate=0.05),
    SlabBracket(upto=1_000_000, rate=0.20),
    SlabBracket(upto=None, rate=0.30),
)
_OLD_SLABS_SUPER_SENIOR = (
    SlabBracket(upto=500_000, rate=0.0),
    SlabBracket(upto=1_000_000, rate=0.20),
    SlabBracket(upto=None, rate=0.30),
)

OLD_REGIME = RegimeRules(
    slabs=_OLD_SLABS_BELOW_60,
    slabs_senior=_OLD_SLABS_SENIOR,
    slabs_super_senior=_OLD_SLABS_SUPER_SENIOR,
    standard_deduction=50_000,
    rebate_87a_income_limit=500_000,
    rebate_87a_max_amount=12_500,
    rebate_87a_has_marginal_relief=False,  # marginal relief u/s 87A exists only in the new regime
    surcharge=(
        SurchargeClause(rate=0.10, above=5_000_000, upto=10_000_000),
        SurchargeClause(rate=0.15, above=10_000_000, upto=20_000_000),
        SurchargeClause(
            rate=0.25, above=20_000_000, upto=50_000_000,
            basis_excludes_special_income=True,
        ),
        SurchargeClause(
            rate=0.37, above=50_000_000, basis_excludes_special_income=True
        ),
    ),
    surcharge_cap_rate=0.37,
    surcharge_residual_rate=0.15,
    surcharge_residual_above=20_000_000,
    surcharge_special_income_cap_rate=0.15,
    allows_professional_tax=True,
    allows_hra_and_10_14=True,
    allows_self_occupied_interest=True,
    allows_house_property_loss_setoff=True,
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
    slabs_senior=None,  # no age concession under s.115BAC
    slabs_super_senior=None,
    standard_deduction=75_000,
    rebate_87a_income_limit=1_200_000,
    rebate_87a_max_amount=60_000,
    rebate_87a_has_marginal_relief=True,
    surcharge=(
        SurchargeClause(rate=0.10, above=5_000_000, upto=10_000_000),
        SurchargeClause(rate=0.15, above=10_000_000, upto=20_000_000),
        # Open-ended: the new regime has no 5-crore/37% clause at all, which is why
        # 25% is its ceiling. This is structural, not a separate capping rule.
        SurchargeClause(
            rate=0.25, above=20_000_000, basis_excludes_special_income=True
        ),
    ),
    surcharge_cap_rate=0.25,
    surcharge_residual_rate=0.15,
    surcharge_residual_above=20_000_000,
    surcharge_special_income_cap_rate=0.15,
    allows_professional_tax=False,
    allows_hra_and_10_14=False,
    allows_self_occupied_interest=False,
    allows_house_property_loss_setoff=False,  # HP loss cannot be set off against other heads
    max_80ccd2_pct_of_salary=0.14,
    allowed_deductions=frozenset(),  # only 80CCD(2), handled separately from Chapter VI-A totals
)

RULES = AssessmentYearRules(
    assessment_year="2026-27",
    old_regime=OLD_REGIME,
    new_regime=NEW_REGIME,
    ltcg_112a_exemption=125_000,
    ltcg_112a_rate=0.125,
    stcg_111a_rate=0.20,
    ltcg_other_rate=0.125,
    section_80c_cap=150_000,
    section_80ccd_1b_cap=50_000,
    section_80d_self_family_cap=25_000,
    section_80d_self_family_cap_senior=50_000,
    section_80d_parents_cap=25_000,
    section_80d_parents_cap_senior=50_000,
    section_80ddb_cap=40_000,
    section_80ddb_cap_senior=100_000,
    section_80tta_cap=10_000,
    section_80ttb_cap=50_000,
    section_80g_qualifying_pct_of_gti=0.10,
    self_occupied_interest_cap=200_000,
    house_property_loss_setoff_cap=200_000,
    rounding_unit=10,
)
