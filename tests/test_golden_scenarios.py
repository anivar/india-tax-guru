"""Golden reference figures for AY 2026-27.

Each expected number was derived INDEPENDENTLY of this codebase: eight canonical
scenarios were each computed from the statute three times over, by three separate
passes working from a verified rules digest and using different approaches
(bottom-up from the statute, ITR-schedule order, and error-hunting). A figure is
recorded here only where at least two of the three agreed; all eight reached
agreement, seven of them unanimously.

These are the suite's oracle. Unlike the tests elsewhere in this directory, which
verify that a rule behaves as the author believes it should, these verify that the
engine as a whole lands on a number arrived at without reference to the engine. If
one of these fails, the engine is wrong until proven otherwise — do not adjust the
expected figure to make it pass without re-deriving it from the statute first.
"""

import pytest

from india_tax_guru.models import (
    AssetClass,
    CapitalGainLot,
    Deductions,
    HouseProperty,
    RentPeriod,
    SalaryComponent,
    SalaryIncome,
    TaxpayerProfile,
)
from india_tax_guru.regime import compute_regime


def _profile(
    basic: int,
    special: int = 0,
    hra: int = 0,
    monthly_rent: int = 0,
    is_metro: bool = True,
    professional_tax: int = 0,
    deductions: Deductions | None = None,
    **kwargs,
) -> TaxpayerProfile:
    components = [SalaryComponent(name="Basic", annual_amount=basic)]
    if special:
        components.append(SalaryComponent(name="Special Allowance", annual_amount=special))
    if hra:
        components.append(SalaryComponent(name="HRA", annual_amount=hra, is_hra=True))
    salary = SalaryIncome(
        employer_name="Test Employer",
        basic_plus_da_annual=basic,
        components=components,
        professional_tax_paid=professional_tax,
        rent_periods=(
            [RentPeriod(months=12, monthly_rent=monthly_rent, is_metro=is_metro)]
            if monthly_rent
            else []
        ),
    )
    return TaxpayerProfile(
        assessment_year="2026-27",
        salaries=[salary],
        deductions=deductions or Deductions(),
        **kwargs,
    )


def _equity(gain: int, long_term: bool) -> CapitalGainLot:
    return CapitalGainLot(
        asset_class=AssetClass.EQUITY_MF if long_term else AssetClass.EQUITY_LISTED,
        is_long_term=long_term,
        gain=gain,
    )


#: (id, description, profile factory, expected old-regime tax, expected new-regime tax)
SCENARIOS = [
    (
        "S1_self_occupied_loan",
        "Salary 20,00,000; self-occupied house with 2,00,000 home-loan interest",
        lambda: _profile(
            1_000_000,
            1_000_000,
            house_properties=[
                HouseProperty(is_self_occupied=True, home_loan_interest=200_000)
            ],
        ),
        351_000,
        192_400,
    ),
    (
        "S2_surcharge_threshold",
        "Salary 52,00,000 — just past the 50,00,000 surcharge threshold",
        lambda: _profile(2_600_000, 2_600_000),
        1_521_000,
        1_253_200,
    ),
    (
        "S3_87a_marginal_relief",
        "Salary 12,85,000 — total income 12,10,000, just past the new-regime rebate limit",
        lambda: _profile(642_500, 642_500),
        190_320,
        10_400,
    ),
    (
        "S4_hra_deductions_prof_tax",
        "Salary 15,00,000 with HRA, metro rent 25,000/month, professional tax, 80C and 80D",
        lambda: _profile(
            600_000,
            600_000,
            hra=300_000,
            monthly_rent=25_000,
            professional_tax=2_500,
            deductions=Deductions(section_80c=150_000, section_80d_self_family=25_000),
        ),
        127_140,
        97_500,
    ),
    (
        "S5_equity_gains",
        "Salary 10,00,000 + 3,00,000 s.112A LTCG + 1,00,000 s.111A STCG",
        lambda: _profile(
            500_000,
            500_000,
            capital_gains=[_equity(300_000, True), _equity(100_000, False)],
        ),
        150_150,
        77_350,
    ),
    (
        "S6_gains_with_surcharge",
        "Salary 60,00,000 + 20,00,000 s.112A LTCG — surcharge applies at 10%",
        lambda: _profile(3_000_000, 3_000_000, capital_gains=[_equity(2_000_000, True)]),
        2_095_670,
        1_821_110,
    ),
    (
        "S7_basic_exemption_setoff",
        "Salary 2,00,000 + 5,00,000 s.112A LTCG — unused basic exemption offsets the gains",
        lambda: _profile(200_000, capital_gains=[_equity(500_000, True)]),
        35_750,
        13_000,
    ),
    (
        "S8_let_out_loss",
        "Salary 18,00,000; let-out property with a loss from 6,00,000 of interest",
        lambda: _profile(
            900_000,
            900_000,
            house_properties=[
                HouseProperty(
                    is_self_occupied=False,
                    annual_rent_received=300_000,
                    municipal_taxes_paid=20_000,
                    home_loan_interest=600_000,
                )
            ],
        ),
        288_600,
        150_800,
    ),
]


@pytest.mark.parametrize(
    "scenario_id,description,factory,expected_old,expected_new",
    SCENARIOS,
    ids=[s[0] for s in SCENARIOS],
)
def test_golden_scenario(scenario_id, description, factory, expected_old, expected_new, rules):
    profile = factory()
    got_old = compute_regime(profile, rules, "old").total_tax_liability
    got_new = compute_regime(profile, rules, "new").total_tax_liability
    assert got_old == expected_old, f"{description} (old regime)"
    assert got_new == expected_new, f"{description} (new regime)"
