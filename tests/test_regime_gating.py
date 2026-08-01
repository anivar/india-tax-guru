"""Everything the new regime disallows.

This file exists because the same bug — an exemption or deduction leaking into the new
regime — was found three separate times in three different modules (HRA, self-occupied
interest, house-property loss set-off). Each is pinned here with a numeric assertion
that the new-regime figure is UNCHANGED by the claim.
"""

from conftest import make_profile

from india_tax_guru.models import (
    Deductions,
    HouseProperty,
    RentPeriod,
    SalaryComponent,
    SalaryIncome,
    TaxpayerProfile,
)
from india_tax_guru.regime import compute_regime


def _with_hra(gross: int, rent_monthly: int) -> TaxpayerProfile:
    basic = gross // 2
    hra = gross // 4
    return TaxpayerProfile(
        assessment_year="2026-27",
        salaries=[
            SalaryIncome(
                employer_name="x",
                basic_plus_da_annual=basic,
                components=[
                    SalaryComponent(name="Basic", annual_amount=basic),
                    SalaryComponent(name="HRA", annual_amount=hra, is_hra=True),
                    SalaryComponent(name="Special", annual_amount=gross - basic - hra),
                ],
                rent_periods=[
                    RentPeriod(months=12, monthly_rent=rent_monthly, is_metro=True)
                ],
            )
        ],
    )


def test_hra_exemption_disallowed_in_new_regime(rules):
    no_rent = _with_hra(2_000_000, 0)
    with_rent = _with_hra(2_000_000, 50_000)

    old_no = compute_regime(no_rent, rules, "old").total_tax_liability
    old_yes = compute_regime(with_rent, rules, "old").total_tax_liability
    assert old_yes < old_no, "old regime must give an HRA exemption"

    new_no = compute_regime(no_rent, rules, "new").total_tax_liability
    new_yes = compute_regime(with_rent, rules, "new").total_tax_liability
    assert new_yes == new_no, "new regime must ignore rent entirely"


def test_self_occupied_interest_disallowed_in_new_regime(rules):
    """s.24(b) interest of 2,00,000 at the 30% marginal rate saves 62,400 with cess."""
    base = make_profile(2_000_000)
    with_loan = make_profile(
        2_000_000,
        house_properties=[HouseProperty(is_self_occupied=True, home_loan_interest=200_000)],
    )

    old_base = compute_regime(base, rules, "old").total_tax_liability
    old_loan = compute_regime(with_loan, rules, "old").total_tax_liability
    assert old_base - old_loan == 62_400

    new_base = compute_regime(base, rules, "new").total_tax_liability
    new_loan = compute_regime(with_loan, rules, "new").total_tax_liability
    assert new_loan == new_base, "new regime must disallow self-occupied interest"


def test_house_property_loss_setoff_disallowed_in_new_regime(rules):
    """Let-out property running a loss: old regime sets it off, new regime cannot."""
    let_out = HouseProperty(
        is_self_occupied=False,
        annual_rent_received=300_000,
        municipal_taxes_paid=20_000,
        home_loan_interest=600_000,
    )
    base = make_profile(1_800_000)
    with_prop = make_profile(1_800_000, house_properties=[let_out])

    assert (
        compute_regime(with_prop, rules, "old").total_tax_liability
        < compute_regime(base, rules, "old").total_tax_liability
    )

    new_base = compute_regime(base, rules, "new")
    new_prop = compute_regime(with_prop, rules, "new")
    assert new_prop.total_tax_liability == new_base.total_tax_liability
    assert new_prop.house_property == 0
    assert new_prop.notes, "the disallowance must be reported, not silent"


def test_professional_tax_only_deductible_in_old_regime(rules):
    """s.16(iii): 2,500 at the 30% marginal rate saves 780 with cess."""
    without = make_profile(1_500_000)
    with_pt = make_profile(1_500_000, professional_tax=2_500)

    old_delta = (
        compute_regime(without, rules, "old").total_tax_liability
        - compute_regime(with_pt, rules, "old").total_tax_liability
    )
    assert old_delta == 780

    assert (
        compute_regime(with_pt, rules, "new").total_tax_liability
        == compute_regime(without, rules, "new").total_tax_liability
    )


def test_chapter_via_disallowed_in_new_regime_and_reported(rules):
    deductions = Deductions(
        section_80c=150_000, section_80ccd_1b=50_000, section_80d_self_family=25_000
    )
    profile = make_profile(1_500_000, deductions=deductions)

    old = compute_regime(profile, rules, "old")
    assert old.deductions_claimed == 225_000

    new = compute_regime(profile, rules, "new")
    assert new.deductions_claimed == 0
    assert any("section_80c" in note for note in new.notes)


def test_employer_nps_allowed_in_both_regimes_at_different_caps(rules):
    """80CCD(2): capped at 10% of basic in the old regime, 14% in the new."""
    basic = 1_000_000
    profile = TaxpayerProfile(
        assessment_year="2026-27",
        salaries=[
            SalaryIncome(
                employer_name="x",
                basic_plus_da_annual=basic,
                components=[SalaryComponent(name="Basic", annual_amount=basic)],
                employer_nps_contribution=200_000,  # 20% — above both caps
            )
        ],
    )
    assert compute_regime(profile, rules, "old").deductions_claimed == 100_000
    assert compute_regime(profile, rules, "new").deductions_claimed == 140_000


def test_employer_nps_above_cap_stays_taxable(rules):
    """Contribution beyond the cap is part of salary and must not vanish.

    Basic is set high enough that both variants sit above the s.87A rebate band,
    otherwise both would be nil-tax and the comparison would prove nothing.
    """
    basic = 2_000_000
    at_cap = TaxpayerProfile(
        assessment_year="2026-27",
        salaries=[
            SalaryIncome(
                employer_name="x",
                basic_plus_da_annual=basic,
                components=[SalaryComponent(name="Basic", annual_amount=basic)],
                employer_nps_contribution=280_000,
            )
        ],
    )
    over_cap = TaxpayerProfile(
        assessment_year="2026-27",
        salaries=[
            SalaryIncome(
                employer_name="x",
                basic_plus_da_annual=basic,
                components=[SalaryComponent(name="Basic", annual_amount=basic)],
                employer_nps_contribution=400_000,
            )
        ],
    )
    assert (
        compute_regime(over_cap, rules, "new").total_tax_liability
        > compute_regime(at_cap, rules, "new").total_tax_liability
    )
