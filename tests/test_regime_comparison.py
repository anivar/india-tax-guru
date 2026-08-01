from india_tax_guru.models import (
    AgeBand,
    Deductions,
    RentPeriod,
    SalaryComponent,
    SalaryIncome,
    TaxpayerProfile,
)
from india_tax_guru.regime import compare_regimes
from india_tax_guru.rules import get_rules


def _salaried_profile(gross_salary: int, deductions: Deductions, rent: int = 0) -> TaxpayerProfile:
    basic = round(gross_salary * 0.4)
    hra = round(gross_salary * 0.2)
    special = gross_salary - basic - hra
    salary = SalaryIncome(
        employer_name="acme",
        components=[
            SalaryComponent(name="Basic", annual_amount=basic),
            SalaryComponent(name="HRA", annual_amount=hra, is_hra=True),
            SalaryComponent(name="Special Allowance", annual_amount=special),
        ],
        basic_plus_da_annual=basic,
        rent_periods=[RentPeriod(months=12, monthly_rent=rent // 12, is_metro=True)]
        if rent
        else [],
    )
    return TaxpayerProfile(
        assessment_year="2026-27",
        age_band=AgeBand.BELOW_60,
        salaries=[salary],
        deductions=deductions,
    )


def test_new_regime_disallows_80c_deduction():
    rules = get_rules("2026-27")
    profile = _salaried_profile(1_500_000, Deductions(section_80c=150_000))
    comparison = compare_regimes(profile, rules)
    assert comparison.new.deductions_claimed == 0
    assert any("section_80c" in n for n in comparison.new.deduction_notes)
    assert comparison.old.deductions_claimed >= 150_000


def test_heavy_deductions_and_high_rent_favor_old_regime():
    rules = get_rules("2026-27")
    profile = _salaried_profile(
        3_000_000,
        Deductions(
            section_80c=150_000,
            section_80ccd_1b=50_000,
            section_80d_self_family=25_000,
            section_80d_parents=50_000,
            parents_are_senior_citizens=True,
        ),
        rent=770_000,
    )
    comparison = compare_regimes(profile, rules)
    assert comparison.old.total_tax_payable < comparison.new.total_tax_payable
    assert comparison.recommended == "old"


def test_low_deductions_no_rent_favor_new_regime():
    rules = get_rules("2026-27")
    profile = _salaried_profile(1_200_000, Deductions())
    comparison = compare_regimes(profile, rules)
    assert comparison.recommended == "new"


def test_both_regimes_always_computed():
    rules = get_rules("2026-27")
    profile = _salaried_profile(800_000, Deductions())
    comparison = compare_regimes(profile, rules)
    assert comparison.old.total_tax_payable >= 0
    assert comparison.new.total_tax_payable >= 0
