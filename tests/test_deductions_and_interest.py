"""Chapter VI-A caps and advance-tax interest (s.234B / s.234C)."""

from india_tax_guru.deductions import compute_deductions
from india_tax_guru.interest import (
    compute_advance_tax_interest,
    section_234b_interest,
    section_234c_interest,
)
from india_tax_guru.models import AgeBand, Deductions

GTI = 2_000_000


def _old(deductions, age_band=AgeBand.BELOW_60, rules=None, gti=GTI):
    return compute_deductions(deductions, age_band, rules, "old", gti)


def test_80c_capped(rules):
    result = _old(Deductions(section_80c=500_000), rules=rules)
    assert result.breakdown["section_80c"] == 150_000


def test_80ddb_capped_and_higher_for_seniors(rules):
    assert _old(Deductions(section_80ddb=500_000), rules=rules).breakdown["section_80ddb"] == 40_000
    senior = _old(
        Deductions(section_80ddb=500_000), age_band=AgeBand.SENIOR_60_80, rules=rules
    )
    assert senior.breakdown["section_80ddb"] == 100_000


def test_80d_self_and_parents_are_independent_tests(rules):
    """A below-60 taxpayer supporting senior parents gets 25,000 + 50,000."""
    result = _old(
        Deductions(
            section_80d_self_family=100_000,
            section_80d_parents=100_000,
            parents_are_senior_citizens=True,
        ),
        rules=rules,
    )
    assert result.breakdown["section_80d_self_family"] == 25_000
    assert result.breakdown["section_80d_parents"] == 50_000


def test_80tta_vs_80ttb_by_age(rules):
    below = _old(Deductions(section_80tta_or_ttb=100_000), rules=rules)
    senior = _old(
        Deductions(section_80tta_or_ttb=100_000), age_band=AgeBand.SENIOR_60_80, rules=rules
    )
    assert below.breakdown["section_80tta_or_ttb"] == 10_000
    assert senior.breakdown["section_80tta_or_ttb"] == 50_000


def test_80g_restricted_to_qualifying_limit(rules):
    """10% of gross total income; 2,00,000 on a GTI of 20,00,000."""
    result = _old(Deductions(section_80g_deductible=1_000_000), rules=rules)
    assert result.breakdown["section_80g"] == 200_000
    assert any("qualifying limit" in note for note in result.notes)


def test_80g_without_qualifying_limit_is_not_restricted(rules):
    result = _old(
        Deductions(
            section_80g_deductible=1_000_000, section_80g_subject_to_qualifying_limit=False
        ),
        rules=rules,
    )
    assert result.breakdown["section_80g"] == 1_000_000


def test_80e_is_uncapped(rules):
    result = _old(Deductions(section_80e_education_loan_interest=800_000), rules=rules)
    assert result.breakdown["section_80e_education_loan_interest"] == 800_000


def test_other_chapter_via_warns_that_it_bypasses_caps(rules):
    result = _old(Deductions(other_chapter_via=9_999_999), rules=rules)
    assert any("NO" in note and "cap" in note for note in result.notes)


def test_deductions_cannot_exceed_gross_total_income(rules):
    result = _old(
        Deductions(section_80c=150_000, other_chapter_via=500_000), rules=rules, gti=100_000
    )
    assert result.total == 100_000
    assert any("cannot create" in note for note in result.notes)


# --- advance-tax interest -------------------------------------------------------


def test_234c_tolerance_means_no_interest_at_12_and_36_pct():
    """The nominal requirements are 15%/45%, but the statutory safe harbour is 12%/36%."""
    assessed = 1_000_000
    interest, notes = section_234c_interest(assessed, [120_000, 360_000, 750_000, 1_000_000])
    assert interest == 0
    assert notes == []


def test_234c_charges_below_the_tolerance():
    assessed = 1_000_000
    interest, notes = section_234c_interest(assessed, [0, 360_000, 750_000, 1_000_000])
    assert interest > 0
    assert len(notes) == 1


def test_234c_rounds_shortfall_down_per_rule_119a():
    """Rule 119A: 1% x 3 months on a shortfall rounded down to the nearest 100."""
    interest, _ = section_234c_interest(1_000_000, [149_999, 450_000, 750_000, 1_000_000])
    # Shortfall 150,000 - 149,999 = 1; rounded down to 0, so no interest.
    assert interest == 0


def test_234b_not_charged_when_90_pct_paid():
    assert section_234b_interest(1_000_000, 900_000, 6) == 0


def test_234b_charged_below_90_pct():
    # Shortfall 500,000 at 1% for 4 months.
    assert section_234b_interest(1_000_000, 500_000, 4) == 20_000


def test_234c_rejects_wrong_checkpoint_count():
    import pytest

    with pytest.raises(ValueError):
        section_234c_interest(1_000_000, [0, 0, 0])


def test_advance_tax_interest_notes_the_unmodelled_carve_out():
    result = compute_advance_tax_interest(1_000_000, 0, [0, 0, 0, 0], 4)
    assert result.total > 0
    assert any("not modelled" in note for note in result.notes)
