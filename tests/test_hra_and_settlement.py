"""Period-wise HRA exemption, and settlement against taxes already paid."""

from conftest import make_profile

from india_tax_guru.models import (
    RentPeriod,
    SalaryComponent,
    SalaryIncome,
    TaxesPaid,
)
from india_tax_guru.regime import compute_regime
from india_tax_guru.salary import hra_exemption


def salary_with_rent(basic, hra_annual, periods):
    return SalaryIncome(
        employer_name="x",
        basic_plus_da_annual=basic,
        components=[
            SalaryComponent(name="Basic", annual_amount=basic),
            SalaryComponent(name="HRA", annual_amount=hra_annual, is_hra=True),
        ],
        rent_periods=periods,
    )


def test_no_rent_means_no_exemption():
    assert hra_exemption(salary_with_rent(600_000, 300_000, []))[0] == 0


def test_single_period_metro():
    """Basic 6,00,000, HRA 3,00,000, rent 25,000/month, metro.

    Least of: HRA received 3,00,000 ; rent 3,00,000 less 10% of basic (60,000) =
    2,40,000 ; 50% of basic = 3,00,000.  -> 2,40,000
    """
    salary = salary_with_rent(
        600_000, 300_000, [RentPeriod(months=12, monthly_rent=25_000, is_metro=True)]
    )
    assert hra_exemption(salary)[0] == 240_000


def test_mid_year_rent_increase_is_computed_period_wise():
    """Basic 6,00,000 (50,000/month), HRA 3,00,000 (25,000/month), metro throughout.

    Apr-Sep at 20,000/month: least of HRA 1,50,000 ; rent 1,20,000 less 30,000 =
                             90,000 ; 50% of basic 1,50,000  ->  90,000
    Oct-Mar at 30,000/month: least of 1,50,000 ; 1,80,000 less 30,000 = 1,50,000 ;
                             1,50,000                              -> 1,50,000
    Total 2,40,000.

    A naive annual computation on average rent (25,000/month) also lands on 2,40,000
    only by coincidence at these figures; the asymmetric case below proves the split
    is real.
    """
    salary = salary_with_rent(
        600_000,
        300_000,
        [
            RentPeriod(months=6, monthly_rent=20_000, is_metro=True),
            RentPeriod(months=6, monthly_rent=30_000, is_metro=True),
        ],
    )
    assert hra_exemption(salary)[0] == 240_000


def test_period_wise_differs_from_annual_average_when_city_changes():
    """Six months metro (50%) then six months non-metro (40%) on identical rent.

    Metro half:     least of 1,50,000 ; 3,00,000-30,000 = 2,70,000 ; 1,50,000 -> 1,50,000
    Non-metro half: least of 1,50,000 ; 2,70,000 ; 40% of 3,00,000 = 1,20,000 -> 1,20,000
    Total 2,70,000 — strictly less than the 3,00,000 an all-metro year would give.
    """
    salary = salary_with_rent(
        600_000,
        300_000,
        [
            RentPeriod(months=6, monthly_rent=50_000, is_metro=True),
            RentPeriod(months=6, monthly_rent=50_000, is_metro=False),
        ],
    )
    assert hra_exemption(salary)[0] == 270_000


def test_non_metro_uses_40_pct_strictly_less_than_metro():
    periods_metro = [RentPeriod(months=12, monthly_rent=50_000, is_metro=True)]
    periods_non_metro = [RentPeriod(months=12, monthly_rent=50_000, is_metro=False)]
    metro = hra_exemption(salary_with_rent(600_000, 300_000, periods_metro))[0]
    non_metro = hra_exemption(salary_with_rent(600_000, 300_000, periods_non_metro))[0]
    assert metro == 300_000
    assert non_metro == 240_000
    assert non_metro < metro


def test_exemption_never_exceeds_hra_actually_received():
    salary = salary_with_rent(
        1_200_000, 100_000, [RentPeriod(months=12, monthly_rent=200_000, is_metro=True)]
    )
    assert hra_exemption(salary)[0] == 100_000


def test_partial_year_rent_warns():
    salary = salary_with_rent(
        600_000, 300_000, [RentPeriod(months=6, monthly_rent=25_000, is_metro=True)]
    )
    exemption, notes = hra_exemption(salary)
    assert exemption > 0
    assert any("not 12" in note for note in notes)


# --- settlement ------------------------------------------------------------------


def test_tds_produces_a_refund(rules):
    profile = make_profile(2_000_000, taxes_paid=TaxesPaid(tds_salary=500_000))
    result = compute_regime(profile, rules, "new")
    assert result.total_tax_liability == 192_400
    assert result.taxes_already_paid == 500_000
    assert result.refund_due == 307_600
    assert result.balance_payable == 0


def test_shortfall_produces_a_balance_payable(rules):
    profile = make_profile(2_000_000, taxes_paid=TaxesPaid(tds_salary=100_000))
    result = compute_regime(profile, rules, "new")
    assert result.balance_payable == 92_400
    assert result.refund_due == 0


def test_liability_is_gross_of_taxes_paid(rules):
    """`total_tax_liability` must not move when credits change — only settlement does."""
    without = compute_regime(make_profile(2_000_000), rules, "new")
    with_tds = compute_regime(
        make_profile(2_000_000, taxes_paid=TaxesPaid(tds_salary=500_000)), rules, "new"
    )
    assert without.total_tax_liability == with_tds.total_tax_liability


def test_234_interest_wired_in_when_checkpoints_supplied(rules):
    profile = make_profile(
        5_000_000,
        taxes_paid=TaxesPaid(
            advance_tax=0, advance_tax_by_checkpoint=[0, 0, 0, 0], months_elapsed_for_234b=4
        ),
    )
    result = compute_regime(profile, rules, "new")
    assert result.interest_234b > 0
    assert result.interest_234c > 0
    assert result.balance_payable > result.total_tax_liability


def test_no_interest_computed_when_checkpoints_absent(rules):
    result = compute_regime(make_profile(5_000_000), rules, "new")
    assert result.interest_234b == 0
    assert result.interest_234c == 0
