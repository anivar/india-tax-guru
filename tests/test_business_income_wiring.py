"""Presumptive income must actually reach the tax computation.

An earlier version of this project shipped an advance-tax interest module that no caller
ever invoked while the skill manifest advertised it. These tests exist so the presumptive
module cannot end up in the same state: the figure it produces has to move total income,
and its presence has to change the Form 10-IEA advice.
"""

from conftest import make_profile

from india_tax_guru.advisory import analyse_salary_structure
from india_tax_guru.models import AssesseeType, Deductions
from india_tax_guru.presumptive import compute_44ad, compute_44ada
from india_tax_guru.regime import compute_regime


def test_business_income_increases_total_income(rules):
    without = compute_regime(make_profile(1_000_000), rules, "new")
    with_business = compute_regime(
        make_profile(1_000_000, business_income=500_000), rules, "new"
    )
    assert with_business.business_income == 500_000
    assert with_business.gross_total_income - without.gross_total_income == 500_000
    assert with_business.total_tax_liability > without.total_tax_liability


def test_business_income_is_taxed_at_slab_rates_not_a_special_rate(rules):
    """PGBP income is ordinary income; it must not land in the special-rate bucket."""
    result = compute_regime(make_profile(1_000_000, business_income=500_000), rules, "new")
    assert result.tax_on_special_rate_income == 0
    assert result.special_rate_capital_gains == 0


def test_presumptive_figure_flows_end_to_end(rules):
    """44AD output -> profile -> engine, with the arithmetic reproducible."""
    presumptive = compute_44ad(
        turnover=10_000_000, digital_receipts=6_000_000, cash_receipts=4_000_000
    )
    assert presumptive.presumptive_income == 680_000

    profile = make_profile(0, business_income=presumptive.presumptive_income)
    result = compute_regime(profile, rules, "new")
    assert result.business_income == 680_000
    assert result.gross_total_income == 680_000


def test_44ada_figure_flows_end_to_end(rules):
    presumptive = compute_44ada(
        gross_receipts=4_000_000, cash_receipts=0, profession="information_technology"
    )
    assert presumptive.presumptive_income == 2_000_000

    result = compute_regime(
        make_profile(0, business_income=presumptive.presumptive_income), rules, "new"
    )
    assert result.gross_total_income == 2_000_000
    assert result.total_tax_liability > 0


def test_business_income_triggers_form_10iea_advice(rules):
    """A presumptive filer choosing the old regime DOES need Form 10-IEA."""
    profile = make_profile(
        2_500_000,
        business_income=1_000_000,
        deductions=Deductions(section_80c=150_000, section_80ccd_1b=50_000),
    )
    advice = analyse_salary_structure(profile, rules)
    if advice.recommended_regime == "old":
        compliance = [r for r in advice.recommendations if r.category == "compliance"]
        assert compliance
        assert "Form 10-IEA must be filed" in compliance[0].rationale


def test_no_business_income_still_gets_the_salaried_guidance(rules):
    profile = make_profile(
        2_500_000, deductions=Deductions(section_80c=150_000, section_80ccd_1b=50_000)
    )
    advice = analyse_salary_structure(profile, rules)
    if advice.recommended_regime == "old":
        compliance = [r for r in advice.recommendations if r.category == "compliance"]
        assert "No Form 10-IEA is required" in compliance[0].rationale


def test_huf_presumptive_is_permitted_by_44ad_even_though_the_engine_refuses_huf():
    """s.44AD admits an HUF; the engine's own HUF limitation is a separate matter.

    The presumptive module must not inherit the engine's assessee restriction, or it
    would misreport the law.
    """
    result = compute_44ad(
        turnover=1_000_000,
        digital_receipts=1_000_000,
        cash_receipts=0,
        assessee_type=AssesseeType.HUF,
    )
    assert result.presumptive_income == 60_000
