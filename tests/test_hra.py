from india_tax_guru.models import RentPeriod, SalaryComponent, SalaryIncome
from india_tax_guru.salary import hra_exemption


def make_salary(basic, hra_annual, rent_periods):
    return SalaryIncome(
        employer_name="x",
        components=[
            SalaryComponent(name="Basic", annual_amount=basic),
            SalaryComponent(name="HRA", annual_amount=hra_annual, is_hra=True),
        ],
        basic_plus_da_annual=basic,
        rent_periods=rent_periods,
    )


def test_hra_no_rent_no_exemption():
    salary = make_salary(600_000, 300_000, [])
    assert hra_exemption(salary) == 0


def test_hra_single_period_metro():
    # Basic 6,00,000/yr = 50,000/mo. HRA 3,00,000/yr = 25,000/mo. Rent 25,000/mo, metro.
    salary = make_salary(
        600_000, 300_000, [RentPeriod(months=12, monthly_rent=25_000, is_metro=True)]
    )
    # least of: HRA received 300000; rent-10%basic = 300000-60000=240000; 50%*basic=300000
    assert hra_exemption(salary) == 240_000


def test_hra_mid_year_rent_increase_period_wise():
    # Rent increases mid-year; period-wise calc should differ from a flat annual shortcut.
    salary = make_salary(
        600_000,
        300_000,
        [
            RentPeriod(months=6, monthly_rent=20_000, is_metro=True),
            RentPeriod(months=6, monthly_rent=30_000, is_metro=True),
        ],
    )
    result = hra_exemption(salary)
    assert 0 < result <= 300_000


def test_hra_capped_at_actual_received():
    # Even if rent is very high, exemption can't exceed HRA actually received.
    salary = make_salary(
        1_200_000, 100_000, [RentPeriod(months=12, monthly_rent=200_000, is_metro=True)]
    )
    assert hra_exemption(salary) <= 100_000


def test_hra_non_metro_uses_40_pct():
    salary_metro = make_salary(
        600_000, 300_000, [RentPeriod(months=12, monthly_rent=50_000, is_metro=True)]
    )
    salary_non_metro = make_salary(
        600_000, 300_000, [RentPeriod(months=12, monthly_rent=50_000, is_metro=False)]
    )
    assert hra_exemption(salary_metro) >= hra_exemption(salary_non_metro)
