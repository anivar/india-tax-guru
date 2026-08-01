"""Worked examples from published professional-body study material for AY 2026-27.

These differ from `test_golden_scenarios.py` in an important way. Those figures were
derived for this project; these come from an external body's published answer keys,
computed with no knowledge of this codebase. That makes them the stronger oracle, and
they immediately earned their place by exposing two live bugs — the s.87A rebate and the
age-enhanced basic exemption were both being granted to non-residents, who are entitled
to neither.

Only the numeric fact patterns and published answers are used here; the scenario
descriptions are written fresh.

If one of these fails, assume the engine is wrong until the figure has been re-derived
from the statute. Do not adjust an expected value to make a test pass.
"""

from india_tax_guru.models import (
    AgeBand,
    AssetClass,
    CapitalGainLot,
    Deductions,
    HouseProperty,
    OtherIncome,
    RentPeriod,
    SalaryComponent,
    SalaryIncome,
    TaxpayerProfile,
)
from india_tax_guru.regime import compute_regime
from india_tax_guru.rules import get_rules

RULES = get_rules("2026-27")


def salaried(components, basic, **kwargs):
    rent = kwargs.pop("monthly_rent", 0)
    metro = kwargs.pop("is_metro", True)
    salary = SalaryIncome(
        employer_name="Employer",
        basic_plus_da_annual=basic,
        components=components,
        rent_periods=(
            [RentPeriod(months=12, monthly_rent=rent, is_metro=metro)] if rent else []
        ),
    )
    return TaxpayerProfile(assessment_year="2026-27", salaries=[salary], **kwargs)


def test_salary_hra_self_occupied_interest_and_chapter_via():
    """Basic 9,60,000, transport allowance 1,80,000, HRA 2,40,000; Delhi rent 25,000/month;
    2,10,000 of interest on a self-occupied house; PPF 1,50,000, NPS 50,000, mediclaim for
    self 32,000 and for a 65-year-old parent 55,000.

    Old regime: HRA exempt is the least of 2,40,000 received, 3,00,000 rent less 10% of
    basic (2,04,000), and 50% of basic (4,80,000) — so 2,04,000. Interest is capped at
    2,00,000. 80D is 25,000 + 50,000. Total income 6,51,000.

    New regime denies the HRA exemption, the s.24(b) interest and all of Chapter VI-A,
    leaving total income 13,05,000 — a case where the old regime wins decisively.
    """
    profile = salaried(
        [
            SalaryComponent(name="Basic", annual_amount=960_000),
            SalaryComponent(name="Transport Allowance", annual_amount=180_000),
            SalaryComponent(name="HRA", annual_amount=240_000, is_hra=True),
        ],
        basic=960_000,
        monthly_rent=25_000,
        house_properties=[HouseProperty(is_self_occupied=True, home_loan_interest=210_000)],
        deductions=Deductions(
            section_80c=150_000,
            section_80ccd_1b=50_000,
            section_80d_self_family=32_000,
            section_80d_parents=55_000,
            parents_are_senior_citizens=True,
        ),
    )
    old = compute_regime(profile, RULES, "old")
    new = compute_regime(profile, RULES, "new")
    assert old.total_income == 651_000
    assert old.total_tax_liability == 44_410
    assert new.total_income == 1_305_000
    assert new.total_tax_liability == 78_780


def test_modest_salary_with_hra_old_regime():
    """Basic 4,92,000 and HRA 84,000 against Delhi rent of 6,000/month.

    Exempt HRA is the least of 84,000, 72,000 less 49,200 (22,800), and 2,46,000 — so
    22,800. Total income 5,03,200, just above the old-regime rebate ceiling, so no s.87A.
    Tax 13,140 plus cess is 13,666, which s.288B rounds up to 13,670.
    """
    profile = salaried(
        [
            SalaryComponent(name="Basic", annual_amount=492_000),
            SalaryComponent(name="HRA", annual_amount=84_000, is_hra=True),
        ],
        basic=492_000,
        monthly_rent=6_000,
    )
    result = compute_regime(profile, RULES, "old")
    assert result.total_income == 503_200
    assert result.total_tax_liability == 13_670


def test_surcharge_marginal_relief_at_the_one_crore_threshold():
    """Total income 1,01,50,000 under the default regime.

    Surcharge steps from 10% to 15% at one crore. Unrelieved tax would be 30,18,750
    against 28,38,000 at exactly one crore, so relief caps tax plus surcharge at
    28,38,000 plus the 1,50,000 of excess income. Relief is 30,750; cess then applies.

    This is the harder relief branch: the rate at the threshold is 10%, not zero.
    """
    gross = 10_150_000 + 75_000  # add back the standard deduction
    profile = salaried([SalaryComponent(name="Basic", annual_amount=gross)], basic=gross)
    result = compute_regime(profile, RULES, "new")
    assert result.total_income == 10_150_000
    assert result.tax_on_slab_income == 2_625_000
    assert result.surcharge == 363_000
    assert result.total_tax_liability == 3_107_520


# --- residency-conditioned reliefs ------------------------------------------------


def only_other_income(amount, age_band, is_resident, **kwargs):
    return TaxpayerProfile(
        assessment_year="2026-27",
        age_band=age_band,
        is_resident=is_resident,
        other_income=OtherIncome(other_sources=amount),
        **kwargs,
    )


def test_non_resident_gets_no_basic_exemption_set_off_against_gains():
    """A 45-year-old non-resident with 2,40,000 of other income and an 85,000 long-term
    gain on a vacant site.

    The other income sits below the exemption limit under both regimes, but a
    non-resident cannot set an unused limit against capital gains, so the whole gain
    bears 12.5% and the tax is identical in both regimes.
    """
    profile = only_other_income(
        240_000,
        AgeBand.BELOW_60,
        False,
        capital_gains=[
            CapitalGainLot(asset_class=AssetClass.PROPERTY, is_long_term=True, gain=85_000)
        ],
    )
    for regime in ("old", "new"):
        assert compute_regime(profile, RULES, regime).total_tax_liability == 11_050


def test_non_resident_senior_gets_neither_raised_exemption_nor_rebate():
    """A 62-year-old non-resident with 4,10,000 of other income.

    The old-regime exemption stays at 2,50,000 rather than the 3,00,000 a resident of
    that age would get, and s.87A is unavailable, so tax arises under both regimes.
    """
    profile = only_other_income(410_000, AgeBand.SENIOR_60_80, False)
    assert compute_regime(profile, RULES, "old").total_tax_liability == 8_320
    assert compute_regime(profile, RULES, "new").total_tax_liability == 520


def test_resident_super_senior_gets_both():
    """A resident aged 81 with 5,90,000 of other income.

    The old-regime exemption is 5,00,000, giving 18,720. Under the default regime the
    s.87A rebate removes the liability entirely.
    """
    profile = only_other_income(590_000, AgeBand.SUPER_SENIOR_80_PLUS, True)
    assert compute_regime(profile, RULES, "old").total_tax_liability == 18_720
    assert compute_regime(profile, RULES, "new").total_tax_liability == 0


def test_non_resident_super_senior_control_case():
    """An 82-year-old non-resident with 4,80,000 and no capital gain.

    Denied both the 5,00,000 exemption and the rebate purely on residence.
    """
    profile = only_other_income(480_000, AgeBand.SUPER_SENIOR_80_PLUS, False)
    assert compute_regime(profile, RULES, "old").total_tax_liability == 11_960
    assert compute_regime(profile, RULES, "new").total_tax_liability == 4_160


