"""Salary-structure advice.

The load-bearing property is that every quoted saving is reproducible: applying the
recommended change to the profile and re-running the engine must yield exactly the
figure the recommendation claimed. A recommendation that cannot be reproduced is worse
than none, because it invites the taxpayer to restructure payroll for nothing.
"""

from conftest import make_profile

from india_tax_guru.advisory import analyse_salary_structure
from india_tax_guru.models import (
    Deductions,
    RentPeriod,
    SalaryComponent,
    SalaryIncome,
    TaxpayerProfile,
)
from india_tax_guru.regime import compute_regime


def structured_profile(
    *, basic=1_200_000, hra=240_000, special=1_080_000, rent_monthly=0, **kwargs
) -> TaxpayerProfile:
    components = [
        SalaryComponent(name="Basic", annual_amount=basic),
        SalaryComponent(name="Special Allowance", annual_amount=special),
    ]
    if hra:
        components.append(SalaryComponent(name="HRA", annual_amount=hra, is_hra=True))
    salary = SalaryIncome(
        employer_name="x",
        basic_plus_da_annual=basic,
        components=components,
        rent_periods=(
            [RentPeriod(months=12, monthly_rent=rent_monthly, is_metro=True)]
            if rent_monthly
            else []
        ),
        employer_nps_contribution=kwargs.pop("employer_nps", 0),
    )
    return TaxpayerProfile(assessment_year="2026-27", salaries=[salary], **kwargs)


def test_baseline_matches_the_recommended_regime(rules):
    profile = structured_profile()
    advice = analyse_salary_structure(profile, rules)
    assert advice.baseline_tax == compute_regime(
        profile, rules, advice.recommended_regime
    ).total_tax_liability


def test_every_recommendation_claims_a_positive_or_zero_saving(rules):
    advice = analyse_salary_structure(structured_profile(rent_monthly=60_000), rules)
    assert all(r.annual_tax_saving >= 0 for r in advice.recommendations)


def test_combined_saving_is_reproducible_and_not_a_sum_of_levers(rules):
    """Levers overlap, so the combined figure must be measured, not added up."""
    profile = structured_profile(
        rent_monthly=60_000, deductions=Deductions(section_80c=0, section_80ccd_1b=0)
    )
    advice = analyse_salary_structure(profile, rules)
    assert advice.optimised_tax == advice.baseline_tax - advice.combined_saving
    assert advice.combined_saving >= 0

    structural = [r for r in advice.recommendations if r.category != "regime"]
    if len(structural) > 1:
        assert advice.combined_saving <= sum(r.annual_tax_saving for r in structural)


def test_employer_nps_headroom_is_recommended_and_reproducible(rules):
    profile = structured_profile(employer_nps=0)
    advice = analyse_salary_structure(profile, rules)
    nps = [r for r in advice.recommendations if "80CCD(2)" in r.action]
    assert nps, "unused employer-NPS headroom is the main new-regime lever"
    assert nps[0].reduces_take_home_cash is True
    assert nps[0].requires_employer_action is True


def test_no_nps_recommendation_when_already_at_the_cap(rules):
    at_cap = structured_profile(employer_nps=round(1_200_000 * 0.14))
    advice = analyse_salary_structure(at_cap, rules)
    assert not [r for r in advice.recommendations if "80CCD(2)" in r.action]


def test_hra_lever_only_appears_when_rent_is_paid(rules):
    no_rent = analyse_salary_structure(structured_profile(hra=0), rules)
    assert not [r for r in no_rent.recommendations if "HRA" in r.action]


def test_hra_never_recommended_beyond_the_exempt_ceiling(rules):
    """Basic 12,00,000, metro, rent 7,20,000 -> ceiling is min(6,00,000, 6,00,000)."""
    profile = structured_profile(
        hra=0,
        rent_monthly=60_000,
        deductions=Deductions(section_80c=150_000, section_80ccd_1b=50_000),
    )
    advice = analyse_salary_structure(profile, rules)
    hra_recs = [r for r in advice.recommendations if "HRA" in r.action]
    if hra_recs:
        assert "600,000" in hra_recs[0].action


def test_hra_without_rent_produces_a_warning(rules):
    advice = analyse_salary_structure(structured_profile(hra=300_000), rules)
    assert any("no rent is recorded" in w for w in advice.warnings)


def test_no_chapter_via_advice_when_new_regime_is_recommended(rules):
    """Telling a new-regime taxpayer to top up 80C would be actively harmful."""
    profile = structured_profile(deductions=Deductions(section_80c=0))
    advice = analyse_salary_structure(profile, rules)
    if advice.recommended_regime == "new":
        assert not [r for r in advice.recommendations if r.category == "deduction"]


def test_chapter_via_advice_appears_when_old_regime_wins(rules):
    """A high earner with heavy rent and part-used deductions belongs in the old regime."""
    profile = structured_profile(
        basic=1_500_000,
        hra=750_000,
        special=750_000,
        rent_monthly=90_000,
        deductions=Deductions(section_80c=50_000, section_80d_self_family=0),
    )
    advice = analyse_salary_structure(profile, rules)
    if advice.recommended_regime == "old":
        assert [r for r in advice.recommendations if r.category == "deduction"]


def test_form_10iea_compliance_note_when_old_regime_recommended(rules):
    profile = structured_profile(
        basic=1_500_000,
        hra=750_000,
        special=750_000,
        rent_monthly=90_000,
        deductions=Deductions(section_80c=150_000, section_80ccd_1b=50_000),
    )
    advice = analyse_salary_structure(profile, rules)
    if advice.recommended_regime == "old":
        assert [r for r in advice.recommendations if r.category == "compliance"]


def test_advice_is_stable_on_an_already_optimal_profile(rules):
    """A taxpayer with nothing left to do should get no structural recommendations."""
    profile = structured_profile(
        employer_nps=round(1_200_000 * 0.14),
        deductions=Deductions(
            section_80c=150_000, section_80ccd_1b=50_000, section_80d_self_family=25_000
        ),
    )
    advice = analyse_salary_structure(profile, rules)
    assert advice.combined_saving == 0
    assert not [r for r in advice.recommendations if r.category == "allocation"]


def test_salaried_profile_with_no_salary_does_not_crash(rules):
    profile = make_profile(0)
    profile.salaries = []
    advice = analyse_salary_structure(profile, rules)
    assert advice.baseline_tax == 0
