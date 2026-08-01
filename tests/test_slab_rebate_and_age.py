"""Slab tax, age-based basic exemption, and the s.87A rebate.

Every expected figure here is hand-derived in the test's own comment, so a failure
identifies which statutory step drifted rather than merely that "a number changed".
"""

from conftest import make_profile

from india_tax_guru.compute import round_288b, slab_tax, slabs_for_age
from india_tax_guru.models import AgeBand
from india_tax_guru.regime import compute_regime


def test_old_regime_basic_exemption_rises_with_age(rules):
    """Gross 6,00,000; standard deduction 50,000 -> total income 5,50,000.

    below 60:      (5,00,000-2,50,000)@5% = 12,500 ; (5,50,000-5,00,000)@20% = 10,000
                   -> 22,500 + 4% cess = 23,400
    senior 60-80:  (5,00,000-3,00,000)@5% = 10,000 ; 10,000 -> 20,000 + cess = 20,800
    super-senior:  no 5% bracket at all; (5,50,000-5,00,000)@20% = 10,000 + cess = 10,400
    """
    expected = {
        AgeBand.BELOW_60: 23_400,
        AgeBand.SENIOR_60_80: 20_800,
        AgeBand.SUPER_SENIOR_80_PLUS: 10_400,
    }
    for age_band, want in expected.items():
        profile = make_profile(600_000, age_band=age_band)
        got = compute_regime(profile, rules, "old").total_tax_liability
        assert got == want, f"{age_band}: expected {want}, got {got}"


def test_new_regime_has_no_age_concession(rules):
    taxes = {
        age: compute_regime(make_profile(1_500_000, age_band=age), rules, "new").total_tax_liability
        for age in AgeBand
    }
    assert len(set(taxes.values())) == 1, f"new regime should be age-independent, got {taxes}"


def test_new_regime_87a_makes_12l_tax_free(rules):
    """Gross 12,75,000 less 75,000 standard deduction = 12,00,000, exactly at the limit."""
    profile = make_profile(1_275_000)
    assert compute_regime(profile, rules, "new").total_tax_liability == 0


def test_new_regime_87a_marginal_relief(rules):
    """Gross 12,85,000 -> total income 12,10,000, i.e. 10,000 over the rebate limit.

    Slab tax would be 61,500, but marginal relief caps tax at the 10,000 of excess
    income. Plus 4% cess = 10,400.
    """
    profile = make_profile(1_285_000)
    assert compute_regime(profile, rules, "new").total_tax_liability == 10_400


def test_old_regime_has_no_87a_marginal_relief(rules):
    """Gross 5,60,000 -> total income 5,10,000, just over the old-regime 5,00,000 limit.

    (5,00,000-2,50,000)@5% = 12,500 ; (5,10,000-5,00,000)@20% = 2,000 -> 14,500.
    No rebate (income exceeds the limit) and NO marginal relief in the old regime,
    so the full 14,500 stands: 14,500 + 4% cess = 15,080.
    """
    profile = make_profile(560_000)
    assert compute_regime(profile, rules, "old").total_tax_liability == 15_080


def test_old_regime_87a_full_rebate_at_limit(rules):
    """Gross 5,50,000 -> total income 5,00,000, exactly at the limit; tax fully rebated."""
    profile = make_profile(550_000)
    assert compute_regime(profile, rules, "old").total_tax_liability == 0


def test_slab_tax_is_marginal_not_cliffed(rules):
    slabs = slabs_for_age(rules.new_regime, AgeBand.BELOW_60)
    # One rupee more income can never cost more than one rupee of slab tax.
    for income in (399_999, 400_001, 799_999, 800_001, 2_399_999, 2_400_001):
        assert slab_tax(income + 1, slabs) - slab_tax(income, slabs) <= 1


def test_round_288b_rounds_halves_up_not_to_even():
    # Python's round() is banker's rounding and would give 1000 here.
    assert round_288b(1005, 10) == 1010
    assert round_288b(1015, 10) == 1020
    assert round_288b(1004, 10) == 1000
    assert round_288b(0, 10) == 0
