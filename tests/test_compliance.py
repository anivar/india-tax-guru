"""Regime-choice compliance guidance.

The first test here guards against actively harmful advice: telling a salaried
taxpayer to file Form 10-IEA makes them file a form the law does not require of them.
That obligation attaches to income under the head Profits and Gains of Business or
Profession, not to a taxpayer's decision to use the old regime.
"""

from conftest import make_profile

from india_tax_guru.advisory import analyse_salary_structure
from india_tax_guru.compliance import DUE_DATES, due_dates_for, regime_choice_guidance
from india_tax_guru.models import (
    Deductions,
    RentPeriod,
    SalaryComponent,
    SalaryIncome,
    TaxpayerProfile,
)


def test_salaried_taxpayer_is_never_told_to_file_form_10iea():
    guidance = regime_choice_guidance("2026-27", "old", has_business_or_professional_income=False)
    assert guidance is not None
    assert guidance.requires_form_10iea is False
    assert "No Form 10-IEA is required" in guidance.detail


def test_business_income_taxpayer_is_told_to_file_form_10iea():
    guidance = regime_choice_guidance("2026-27", "old", has_business_or_professional_income=True)
    assert guidance is not None
    assert guidance.requires_form_10iea is True
    assert "Form 10-IEA must be filed" in guidance.detail
    assert "acknowledgement number" in guidance.detail


def test_salaried_guidance_warns_that_a_belated_return_forfeits_the_old_regime():
    """s.115BAC(6)(ii) ties the option to a s.139(1) return; s.139(4) cannot carry it."""
    guidance = regime_choice_guidance("2026-27", "old")
    assert "139(4)" in guidance.detail
    assert "forfeits" in guidance.detail or "cannot claim" in guidance.detail


def test_no_guidance_when_the_new_regime_is_recommended():
    """The new regime is the default, so nothing need be done and nothing can go wrong."""
    assert regime_choice_guidance("2026-27", "new") is None
    assert (
        regime_choice_guidance("2026-27", "new", has_business_or_professional_income=True)
        is None
    )


def test_due_date_is_quoted_from_the_table_not_hardcoded():
    guidance = regime_choice_guidance("2026-27", "old")
    assert "31 July 2026" in guidance.headline

    audit = regime_choice_guidance("2026-27", "old", is_audit_case=True)
    assert "31 October 2026" in audit.headline


def test_extended_due_dates_are_reflected():
    """AY 2025-26's non-audit date was moved to 16 September 2025 by circular."""
    dates = due_dates_for("2025-26")
    assert (dates.non_audit.day, dates.non_audit.month) == (16, 9)
    assert "16 September 2025" in regime_choice_guidance("2025-26", "old").headline


def test_provisional_dates_are_hedged_in_the_wording():
    assert DUE_DATES["2026-27"].provisional is True
    assert "confirm no CBDT extension" in regime_choice_guidance("2026-27", "old").headline
    assert DUE_DATES["2025-26"].provisional is False


def test_unknown_assessment_year_falls_back_to_a_generic_phrase():
    guidance = regime_choice_guidance("2099-2100", "old")
    assert "applicable s.139(1) due date" in guidance.headline


def test_advisory_does_not_mention_form_10iea_for_a_salaried_profile(rules):
    """End-to-end: the advisory path must not surface the false positive either."""
    profile = TaxpayerProfile(
        assessment_year="2026-27",
        salaries=[
            SalaryIncome(
                employer_name="x",
                basic_plus_da_annual=1_500_000,
                components=[
                    SalaryComponent(name="Basic", annual_amount=1_500_000),
                    SalaryComponent(name="HRA", annual_amount=750_000, is_hra=True),
                    SalaryComponent(name="Special Allowance", annual_amount=750_000),
                ],
                rent_periods=[RentPeriod(months=12, monthly_rent=90_000, is_metro=True)],
            )
        ],
        deductions=Deductions(section_80c=150_000, section_80ccd_1b=50_000),
    )
    advice = analyse_salary_structure(profile, rules)
    if advice.recommended_regime == "old":
        compliance = [r for r in advice.recommendations if r.category == "compliance"]
        assert compliance, "an old-regime recommendation must carry a deadline warning"
        assert "No Form 10-IEA is required" in compliance[0].rationale


def test_advisory_surfaces_form_10iea_when_business_income_is_declared(rules):
    profile = make_profile(3_000_000, deductions=Deductions(section_80c=150_000))
    advice = analyse_salary_structure(
        profile, rules, has_business_or_professional_income=True
    )
    if advice.recommended_regime == "old":
        compliance = [r for r in advice.recommendations if r.category == "compliance"]
        assert "Form 10-IEA must be filed" in compliance[0].rationale
