"""HUF computation: the individual machinery MINUS the individual-only reliefs.

The dangerous failure mode is silence: an HUF run through the individual path would
collect the s.87A rebate, the age-based exemption and s.80CCD headroom without anything
in the output looking wrong. These tests pin both directions — the reliefs an HUF must
not get (87A, age slabs, salary heads, 80CCD(1B), 80E, s.44ADA) and the machinery it
must still get unchanged (slabs, cess, 80C/80TTA, s.44AD, Form 10-IEA).

Golden figures, AY 2026-27, hand-derived:
- 8,00,000 of interest income, new regime: slab tax (8L-4L) x 5% = 20,000. An
  individual is rebated to nil (limit 12,00,000); an HUF pays 20,000 + 4% cess = 20,800.
- Same income, old regime: 12,500 + 60,000 = 72,500; +cess = 75,400 for BOTH, since at
  8L the old-regime rebate (limit 5,00,000) reaches neither.
"""

import pytest

from india_tax_guru.advisory import analyse_salary_structure
from india_tax_guru.models import (
    AgeBand,
    AssesseeType,
    Deductions,
    HouseProperty,
    OtherIncome,
    SalaryComponent,
    SalaryIncome,
    TaxpayerProfile,
)
from india_tax_guru.presumptive import PresumptiveIneligible, compute_44ad, compute_44ada
from india_tax_guru.regime import compare_regimes, compute_regime


def make_huf(income: int = 800_000, **kwargs) -> TaxpayerProfile:
    """An HUF earning `income` as other-source income (an HUF cannot earn salary)."""
    return TaxpayerProfile(
        assessment_year="2026-27",
        assessee_type=AssesseeType.HUF,
        other_income=OtherIncome(other_sources=income),
        **kwargs,
    )


# ---------------------------------------------------------------- construction guards


def test_huf_with_salary_income_is_rejected():
    salary = SalaryIncome(
        employer_name="Emp",
        basic_plus_da_annual=600_000,
        components=[SalaryComponent(name="Basic", annual_amount=600_000)],
    )
    with pytest.raises(ValueError, match="salary"):
        TaxpayerProfile(
            assessment_year="2026-27",
            assessee_type=AssesseeType.HUF,
            salaries=[salary],
        )


@pytest.mark.parametrize("band", [AgeBand.SENIOR_60_80, AgeBand.SUPER_SENIOR_80_PLUS])
def test_huf_with_a_senior_age_band_is_rejected(band):
    """The karta's age must not smuggle in the individual's age concession."""
    with pytest.raises(ValueError, match="age"):
        TaxpayerProfile(
            assessment_year="2026-27", assessee_type=AssesseeType.HUF, age_band=band
        )


def test_huf_claiming_80ccd_1b_is_rejected():
    with pytest.raises(ValueError, match="80CCD"):
        make_huf(deductions=Deductions(section_80ccd_1b=50_000))


def test_huf_claiming_80e_is_rejected():
    with pytest.raises(ValueError, match="80E"):
        make_huf(deductions=Deductions(section_80e_education_loan_interest=40_000))


# ------------------------------------------------------------------------ s.87A rebate


def test_huf_gets_no_87a_rebate_where_an_individual_pays_nil(rules):
    """8,00,000 in the new regime: individual nil, HUF 20,800 — the headline difference."""
    huf = compute_regime(make_huf(800_000), rules, "new")
    individual = compute_regime(
        TaxpayerProfile(
            assessment_year="2026-27",
            other_income=OtherIncome(other_sources=800_000),
        ),
        rules,
        "new",
    )
    assert individual.total_tax_liability == 0
    assert huf.rebate_87a == 0
    assert huf.tax_on_slab_income == 20_000
    assert huf.total_tax_liability == 20_800


def test_huf_gets_no_87a_marginal_relief_either(rules):
    """Just past the 12,00,000 limit an individual pays only the excess; an HUF pays full."""
    huf = compute_regime(make_huf(1_210_000), rules, "new")
    individual = compute_regime(
        TaxpayerProfile(
            assessment_year="2026-27",
            other_income=OtherIncome(other_sources=1_210_000),
        ),
        rules,
        "new",
    )
    # Slab tax at 12,10,000 is 20,000 + 40,000 + 1,500 = 61,500.
    assert huf.tax_on_slab_income == 61_500
    assert huf.rebate_87a == 0
    # Individual: marginal relief caps tax at the 10,000 earned past the limit.
    assert individual.tax_on_slab_income - individual.rebate_87a == 10_000
    assert huf.total_tax_liability == round(61_500 * 1.04 / 10) * 10


def test_huf_old_regime_matches_individual_where_no_rebate_reaches_either(rules):
    """At 8,00,000 the old-regime slabs and cess are identical — 75,400 for both."""
    huf = compute_regime(make_huf(800_000), rules, "old")
    assert huf.tax_on_slab_income == 72_500
    assert huf.total_tax_liability == 75_400


# ------------------------------------------------------------------------- deductions


def test_huf_80c_and_80tta_apply_with_their_ordinary_caps(rules):
    """80C and 80TTA both extend to HUFs; 80TTA stays at 10,000 (never 80TTB's 50,000)."""
    profile = TaxpayerProfile(
        assessment_year="2026-27",
        assessee_type=AssesseeType.HUF,
        other_income=OtherIncome(savings_bank_interest=60_000, other_sources=740_000),
        deductions=Deductions(section_80c=200_000, section_80tta_or_ttb=60_000),
    )
    result = compute_regime(profile, rules, "old")
    # 80C capped at 1,50,000 + 80TTA capped at 10,000.
    assert result.deductions_claimed == 160_000
    assert result.slab_taxable_income == 640_000


# ------------------------------------------------------------------------ presumptive


def test_huf_remains_eligible_for_44ad(rules):
    result = compute_44ad(
        turnover=1_000_000,
        digital_receipts=1_000_000,
        cash_receipts=0,
        assessee_type=AssesseeType.HUF,
    )
    assert result.presumptive_income == 60_000


def test_huf_is_refused_44ada_since_finance_act_2021():
    """s.44ADA admits only an individual or a partnership firm; an HUF lost it in 2021."""
    with pytest.raises(PresumptiveIneligible, match="2021"):
        compute_44ada(
            gross_receipts=2_000_000,
            cash_receipts=0,
            profession="legal",
            assessee_type=AssesseeType.HUF,
        )


def test_individual_and_firm_still_pass_the_44ada_gate():
    for assessee in (AssesseeType.INDIVIDUAL, AssesseeType.FIRM):
        result = compute_44ada(
            gross_receipts=2_000_000,
            cash_receipts=0,
            profession="legal",
            assessee_type=assessee,
        )
        assert result.presumptive_income == 1_000_000


# ---------------------------------------------------------------- end-to-end advisory


def test_huf_with_business_income_gets_form_10iea_guidance_when_old_wins(rules):
    """Old regime wins on heavy deductions + house-property loss; 10-IEA must surface.

    Old: GTI 8,00,000 - 2,00,000 s.24(b) = 6,00,000; less 80C 1,50,000 and 80D 25,000
    -> 4,25,000 -> tax 8,750 (NO rebate for an HUF) -> 9,100 with cess.
    New: loss and deductions disallowed -> tax 20,000 -> 20,800 with cess.
    """
    profile = TaxpayerProfile(
        assessment_year="2026-27",
        assessee_type=AssesseeType.HUF,
        business_income=800_000,
        house_properties=[HouseProperty(is_self_occupied=True, home_loan_interest=200_000)],
        deductions=Deductions(section_80c=150_000, section_80d_self_family=25_000),
    )
    comparison = compare_regimes(profile, rules)
    assert comparison.recommended == "old"
    assert comparison.old.total_tax_liability == 9_100
    assert comparison.new.total_tax_liability == 20_800

    advice = analyse_salary_structure(profile, rules)
    compliance = [r for r in advice.recommendations if r.category == "compliance"]
    assert compliance and "Form 10-IEA" in compliance[0].action


def test_advisory_never_recommends_80ccd_1b_to_an_huf(rules):
    """The NPS lever is individual-only, and for an HUF it would even crash on replay."""
    advice = analyse_salary_structure(make_huf(2_000_000), rules)
    assert not any("80CCD(1B)" in r.action for r in advice.recommendations)
