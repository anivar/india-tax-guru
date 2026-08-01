"""Surcharge: thresholds, the 15% special-income cap, and marginal relief."""

from conftest import make_profile

from india_tax_guru.compute import slab_tax, slabs_for_age
from india_tax_guru.models import (
    AgeBand,
    AssetClass,
    CapitalGainLot,
    SalaryComponent,
    SalaryIncome,
    TaxpayerProfile,
)
from india_tax_guru.regime import compute_regime


def test_no_surcharge_below_threshold(rules):
    assert compute_regime(make_profile(4_000_000), rules, "new").surcharge == 0


def test_surcharge_marginal_relief_at_50l(rules):
    """Gross 51,00,000 -> total income 50,25,000, i.e. 25,000 past the threshold.

    Slab tax 10,87,500; tax at exactly 50,00,000 is 10,80,000. Marginal relief caps
    (tax + surcharge) at 10,80,000 + 25,000 = 11,05,000, so surcharge is 17,500 —
    far below the unrelieved 10% of 10,87,500 = 1,08,750.
    """
    result = compute_regime(make_profile(5_100_000), rules, "new")
    assert result.surcharge == 17_500
    assert result.total_tax_liability == 1_149_200
    assert any("marginal relief" in note.lower() for note in result.notes)


def test_marginal_relief_never_lets_surcharge_exceed_excess_income(rules):
    """Across the whole relief band, tax+surcharge growth is bounded by income growth."""
    slabs = slabs_for_age(rules.new_regime, AgeBand.BELOW_60)
    tax_at_threshold = slab_tax(5_000_000, slabs)
    for total_income in range(5_010_000, 5_400_000, 10_000):
        gross = total_income + 75_000  # add back the standard deduction
        result = compute_regime(make_profile(gross), rules, "new")
        pre_cess = result.tax_on_slab_income - result.rebate_87a + result.surcharge
        ceiling = tax_at_threshold + (total_income - 5_000_000)
        assert pre_cess <= ceiling + 1, (
            f"at total income {total_income:,}: tax+surcharge {pre_cess:,} exceeds "
            f"the marginal-relief ceiling {ceiling:,}"
        )


def _salary_plus_ltcg(salary: int, ltcg: int) -> TaxpayerProfile:
    return TaxpayerProfile(
        assessment_year="2026-27",
        salaries=[
            SalaryIncome(
                employer_name="x",
                basic_plus_da_annual=salary // 2,
                components=[SalaryComponent(name="Basic", annual_amount=salary)],
            )
        ],
        capital_gains=[
            CapitalGainLot(asset_class=AssetClass.EQUITY_MF, is_long_term=True, gain=ltcg)
        ],
    )


def test_25_pct_clause_does_not_fire_on_capital_gains_alone(rules):
    """Salary 30,00,000 + equity LTCG 2,50,00,000 — total income is 2.79 crore.

    The 25% clause tests income EXCLUDING s.112A gains, which here is only 29,25,000.
    So 25% does not apply; the residual clause charges 15% on the whole tax. Testing
    the 25% clause against total income would over-tax this taxpayer substantially.
    """
    result = compute_regime(_salary_plus_ltcg(3_000_000, 25_000_000), rules, "new")

    slabs = slabs_for_age(rules.new_regime, AgeBand.BELOW_60)
    slab_component = slab_tax(3_000_000 - 75_000, slabs)
    cg_component = round((25_000_000 - rules.ltcg_112a_exemption) * rules.ltcg_112a_rate)

    assert result.surcharge == round((slab_component + cg_component) * 0.15)
    assert result.surcharge < round(slab_component * 0.25 + cg_component * 0.15)


def test_25_pct_clause_fires_when_non_special_income_alone_breaches_2cr(rules):
    """Salary 2,50,00,000 + equity LTCG 50,00,000.

    Income excluding the gains is 2.49 crore, above 2 crore, so the 25% clause does
    apply — to the salary tax. The s.112A portion is still capped at 15%.
    """
    result = compute_regime(_salary_plus_ltcg(25_000_000, 5_000_000), rules, "new")

    slabs = slabs_for_age(rules.new_regime, AgeBand.BELOW_60)
    slab_component = slab_tax(25_000_000 - 75_000, slabs)
    cg_component = round((5_000_000 - rules.ltcg_112a_exemption) * rules.ltcg_112a_rate)

    assert result.surcharge == round(slab_component * 0.25 + cg_component * 0.15)


def test_special_income_cap_is_a_ceiling_not_a_floor(rules):
    """At total income between 50L and 1cr the rate is 10%, so gains bear 10%, not 15%."""
    result = compute_regime(_salary_plus_ltcg(3_000_000, 3_000_000), rules, "new")
    slabs = slabs_for_age(rules.new_regime, AgeBand.BELOW_60)
    slab_component = slab_tax(3_000_000 - 75_000, slabs)
    cg_component = round((3_000_000 - rules.ltcg_112a_exemption) * rules.ltcg_112a_rate)
    assert result.surcharge == round((slab_component + cg_component) * 0.10)


def test_new_regime_surcharge_capped_at_25_pct(rules):
    """The old regime reaches 37% above 5 crore; the new regime has no such clause."""
    profile = make_profile(100_000_000)
    old = compute_regime(profile, rules, "old")
    new = compute_regime(profile, rules, "new")
    assert new.surcharge / new.tax_on_slab_income < 0.26
    assert old.surcharge / old.tax_on_slab_income > 0.30
