"""Presumptive taxation under s.44AD and s.44ADA."""

import pytest

from india_tax_guru.models import AssesseeType
from india_tax_guru.presumptive import (
    PresumptiveIneligible,
    compute_44ad,
    compute_44ada,
    presumptive_234c_interest,
)

# --- s.44AD rate is a split, not an alternative ----------------------------------


def test_all_digital_receipts_are_taxed_at_6_pct():
    result = compute_44ad(turnover=10_000_000, digital_receipts=10_000_000, cash_receipts=0)
    assert result.presumptive_income == 600_000


def test_all_cash_receipts_are_taxed_at_8_pct():
    result = compute_44ad(turnover=1_000_000, digital_receipts=0, cash_receipts=1_000_000)
    assert result.presumptive_income == 80_000


def test_mixed_receipts_are_split_not_rated_as_a_whole():
    """60,00,000 digital at 6% plus 40,00,000 otherwise at 8% = 6,80,000.

    Applying 6% to the whole turnover would give 6,00,000, and 8% to the whole would give
    8,00,000. Neither is the answer; the proviso substitutes the rate only for the amount
    actually received through qualifying modes.
    """
    result = compute_44ad(
        turnover=10_000_000, digital_receipts=6_000_000, cash_receipts=4_000_000
    )
    assert result.presumptive_income == 680_000
    assert result.presumptive_income != round(10_000_000 * 0.06)
    assert result.presumptive_income != round(10_000_000 * 0.08)
    assert any("Split rate" in note for note in result.notes)


def test_unreceived_turnover_falls_back_to_8_pct():
    """Turnover still unreceived by the s.139(1) due date does not earn the 6% rate."""
    result = compute_44ad(turnover=10_000_000, digital_receipts=5_000_000, cash_receipts=0)
    assert result.presumptive_income == round(5_000_000 * 0.06 + 5_000_000 * 0.08)


# --- thresholds ------------------------------------------------------------------


def test_enhanced_cap_applies_when_cash_is_within_5_pct():
    result = compute_44ad(
        turnover=25_000_000, digital_receipts=24_000_000, cash_receipts=1_000_000
    )
    assert result.turnover_cap_applied == 30_000_000
    assert any("Enhanced turnover cap" in note for note in result.notes)


def test_base_cap_applies_when_cash_exceeds_5_pct():
    with pytest.raises(PresumptiveIneligible) as exc:
        compute_44ad(turnover=25_000_000, digital_receipts=20_000_000, cash_receipts=5_000_000)
    assert "2" in str(exc.value)


def test_breaching_the_cap_removes_the_section_rather_than_capping_relief():
    """The cap sits inside the definition of 'eligible business', so it is not a ceiling."""
    with pytest.raises(PresumptiveIneligible) as exc:
        compute_44ad(turnover=40_000_000, digital_receipts=40_000_000, cash_receipts=0)
    assert "removes the section entirely" in str(exc.value)


# --- eligibility -----------------------------------------------------------------


def test_llp_is_excluded_by_name():
    with pytest.raises(PresumptiveIneligible) as exc:
        compute_44ad(
            turnover=1_000_000,
            digital_receipts=1_000_000,
            cash_receipts=0,
            assessee_type=AssesseeType.LLP,
        )
    assert "LLP" in str(exc.value)


def test_non_resident_is_excluded():
    with pytest.raises(PresumptiveIneligible):
        compute_44ad(
            turnover=1_000_000, digital_receipts=1_000_000, cash_receipts=0, is_resident=False
        )


@pytest.mark.parametrize(
    "business_kind",
    ["commission_or_brokerage", "agency_business", "goods_carriage", "profession_44aa_1"],
)
def test_excluded_business_kinds(business_kind):
    with pytest.raises(PresumptiveIneligible):
        compute_44ad(
            turnover=1_000_000,
            digital_receipts=1_000_000,
            cash_receipts=0,
            business_kind=business_kind,
        )


def test_company_cannot_use_44ad():
    with pytest.raises(PresumptiveIneligible):
        compute_44ad(
            turnover=1_000_000,
            digital_receipts=1_000_000,
            cash_receipts=0,
            assessee_type=AssesseeType.COMPANY,
        )


# --- the s.44AD(4) lock-in needs a prior-year declaration ------------------------


def test_declaring_lower_without_a_prior_opt_in_does_not_engage_44ad4():
    """Someone who never used s.44AD is governed by s.44AA(2)/44AB(a), not s.44AD(4)."""
    result = compute_44ad(
        turnover=10_000_000,
        digital_receipts=10_000_000,
        cash_receipts=0,
        declared_income=200_000,
        opted_in_an_earlier_year=False,
    )
    assert result.books_required is False
    assert result.audit_required is False
    assert any("does not engage s.44AD(4)" in note for note in result.notes)


def test_declaring_lower_after_opting_in_engages_the_lock_in():
    result = compute_44ad(
        turnover=10_000_000,
        digital_receipts=10_000_000,
        cash_receipts=0,
        declared_income=500_000,
        opted_in_an_earlier_year=True,
        basic_exemption_limit=400_000,
    )
    assert result.books_required is True
    assert result.audit_required is True
    assert any("five subsequent assessment years" in note for note in result.notes)


def test_no_audit_where_income_is_below_the_exemption_limit():
    result = compute_44ad(
        turnover=10_000_000,
        digital_receipts=10_000_000,
        cash_receipts=0,
        declared_income=300_000,
        opted_in_an_earlier_year=True,
        basic_exemption_limit=400_000,
    )
    assert result.books_required is False


def test_declaring_higher_than_presumptive_is_allowed():
    result = compute_44ad(
        turnover=10_000_000,
        digital_receipts=10_000_000,
        cash_receipts=0,
        declared_income=2_000_000,
    )
    assert result.declared_income == 2_000_000
    assert result.books_required is False


# --- s.44ADA ---------------------------------------------------------------------


def test_44ada_is_a_flat_50_pct():
    result = compute_44ada(gross_receipts=4_000_000, cash_receipts=0, profession="legal")
    assert result.presumptive_income == 2_000_000


def test_44ada_enhanced_cap_with_low_cash():
    result = compute_44ada(
        gross_receipts=7_000_000, cash_receipts=100_000, profession="engineering"
    )
    assert result.turnover_cap_applied == 7_500_000


def test_44ada_rejects_receipts_above_the_cap():
    with pytest.raises(PresumptiveIneligible):
        compute_44ada(gross_receipts=8_000_000, cash_receipts=0, profession="accountancy")


def test_44ada_rejects_a_profession_outside_44aa_1():
    with pytest.raises(PresumptiveIneligible) as exc:
        compute_44ada(gross_receipts=1_000_000, cash_receipts=0, profession="plumbing")
    assert "44AA(1)" in str(exc.value)


def test_44ada_has_no_split_rate():
    """Unlike s.44AD, the mode of receipt does not change the s.44ADA rate."""
    digital = compute_44ada(gross_receipts=4_000_000, cash_receipts=0, profession="medical")
    cash = compute_44ada(
        gross_receipts=4_000_000, cash_receipts=4_000_000, profession="medical"
    )
    assert digital.presumptive_income == cash.presumptive_income


# --- advance tax -----------------------------------------------------------------


def test_presumptive_assessee_has_a_single_advance_tax_instalment():
    result = compute_44ad(turnover=1_000_000, digital_receipts=1_000_000, cash_receipts=0)
    assert result.single_advance_tax_instalment is True
    assert any("15 March" in note for note in result.notes)


def test_presumptive_234c_is_one_time_1_pct_not_per_month():
    interest, note = presumptive_234c_interest(assessed_tax=500_000, paid_by_15_march=0)
    assert interest == 5_000
    assert "one-time 1%" in note


def test_no_234c_where_advance_tax_was_met():
    interest, note = presumptive_234c_interest(assessed_tax=500_000, paid_by_15_march=500_000)
    assert interest == 0
    assert "no s.234C" in note


def test_presumptive_234c_rounds_down_per_rule_119a():
    interest, _ = presumptive_234c_interest(assessed_tax=1_099, paid_by_15_march=1_000)
    assert interest == 0
