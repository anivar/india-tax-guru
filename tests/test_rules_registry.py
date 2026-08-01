"""Every registered assessment year must be internally complete and self-consistent.

These are structural invariants rather than rate assertions: a new AY module added by a
contributor should fail here loudly if a field was left at a placeholder or a slab tuple
is malformed, rather than silently producing a plausible-looking wrong number.
"""

import pytest
from conftest import make_profile

from india_tax_guru.compute import basic_exemption_limit, slabs_for_age
from india_tax_guru.models import AgeBand
from india_tax_guru.regime import compare_regimes, compute_regime
from india_tax_guru.rules import available_years, get_rules

ALL_YEARS = available_years()


def test_at_least_two_years_registered():
    assert len(ALL_YEARS) >= 2


def test_unknown_year_raises_with_actionable_message():
    with pytest.raises(ValueError) as exc:
        get_rules("1999-2000")
    message = str(exc.value)
    assert "1999-2000" in message
    for year in ALL_YEARS:
        assert year in message


@pytest.mark.parametrize("year", ALL_YEARS)
def test_assessment_year_field_matches_registry_key(year):
    assert get_rules(year).assessment_year == year


@pytest.mark.parametrize("year", ALL_YEARS)
def test_slabs_are_ascending_and_open_ended(year):
    rules = get_rules(year)
    for regime_rules in (rules.old_regime, rules.new_regime):
        for slabs in (
            regime_rules.slabs,
            regime_rules.slabs_senior,
            regime_rules.slabs_super_senior,
        ):
            if slabs is None:
                continue
            bounds = [b.upto for b in slabs]
            assert bounds[-1] is None, "the final bracket must be open-ended"
            finite = [b for b in bounds[:-1]]
            assert all(b is not None for b in finite), "only the last bracket may be open"
            assert finite == sorted(finite), "slab ceilings must ascend"
            assert slabs[0].rate == 0.0, "the first bracket must be the exemption"


@pytest.mark.parametrize("year", ALL_YEARS)
def test_old_regime_basic_exemption_rises_with_age(year):
    old = get_rules(year).old_regime
    below = basic_exemption_limit(slabs_for_age(old, AgeBand.BELOW_60))
    senior = basic_exemption_limit(slabs_for_age(old, AgeBand.SENIOR_60_80))
    super_senior = basic_exemption_limit(slabs_for_age(old, AgeBand.SUPER_SENIOR_80_PLUS))
    assert below < senior < super_senior


@pytest.mark.parametrize("year", ALL_YEARS)
def test_new_regime_has_no_age_concession(year):
    new = get_rules(year).new_regime
    assert new.slabs_senior is None
    assert new.slabs_super_senior is None


@pytest.mark.parametrize("year", ALL_YEARS)
def test_new_regime_disallows_what_it_should(year):
    new = get_rules(year).new_regime
    assert new.allows_hra_and_10_14 is False
    assert new.allows_professional_tax is False
    assert new.allows_self_occupied_interest is False
    assert new.allows_house_property_loss_setoff is False
    assert new.allowed_deductions == frozenset()
    assert new.rebate_87a_has_marginal_relief is True


@pytest.mark.parametrize("year", ALL_YEARS)
def test_old_regime_allows_what_it_should(year):
    old = get_rules(year).old_regime
    assert old.allows_hra_and_10_14 is True
    assert old.allows_professional_tax is True
    assert old.allows_self_occupied_interest is True
    assert old.rebate_87a_has_marginal_relief is False, "relief is new-regime only"
    assert "section_80c" in old.allowed_deductions


@pytest.mark.parametrize("year", ALL_YEARS)
def test_surcharge_brackets_ascend_in_both_rate_and_threshold(year):
    rules = get_rules(year)
    for regime_rules in (rules.old_regime, rules.new_regime):
        brackets = sorted(regime_rules.surcharge, key=lambda b: b.income_above)
        rates = [b.rate for b in brackets]
        assert rates == sorted(rates), "a higher threshold must not carry a lower rate"
        assert max(rates) <= regime_rules.surcharge_cap_rate
        assert regime_rules.surcharge_special_income_cap_rate <= regime_rules.surcharge_cap_rate


@pytest.mark.parametrize("year", ALL_YEARS)
def test_new_regime_surcharge_ceiling_below_old(year):
    rules = get_rules(year)
    assert rules.new_regime.surcharge_cap_rate < rules.old_regime.surcharge_cap_rate


@pytest.mark.parametrize("year", ALL_YEARS)
def test_caps_are_positive_and_senior_caps_are_not_lower(year):
    rules = get_rules(year)
    assert rules.section_80c_cap > 0
    assert rules.ltcg_112a_exemption > 0
    assert rules.section_80d_self_family_cap_senior >= rules.section_80d_self_family_cap
    assert rules.section_80d_parents_cap_senior >= rules.section_80d_parents_cap
    assert rules.section_80ddb_cap_senior >= rules.section_80ddb_cap
    assert rules.section_80ttb_cap >= rules.section_80tta_cap


@pytest.mark.parametrize("year", ALL_YEARS)
def test_112a_exemption_is_in_a_plausible_range(year):
    """Guards the 10x class of typo that made a 10,00,000 gain look exempt."""
    assert 50_000 <= get_rules(year).ltcg_112a_exemption <= 500_000


@pytest.mark.parametrize("year", ALL_YEARS)
def test_tax_rises_monotonically_with_income(year):
    """Across a wide sweep, more income must never mean less tax."""
    rules = get_rules(year)
    for regime in ("old", "new"):
        previous = -1
        for gross in range(300_000, 15_000_000, 250_000):
            profile = make_profile(gross, assessment_year=year)
            tax = compute_regime(profile, rules, regime).total_tax_liability
            assert tax >= previous, f"{year}/{regime}: tax fell at gross {gross:,}"
            previous = tax


@pytest.mark.parametrize("year", ALL_YEARS)
def test_zero_income_is_zero_tax(year):
    rules = get_rules(year)
    for regime in ("old", "new"):
        profile = make_profile(0, assessment_year=year)
        assert compute_regime(profile, rules, regime).total_tax_liability == 0


@pytest.mark.parametrize("year", ALL_YEARS)
def test_comparison_recommends_the_cheaper_regime(year):
    """On an exact tie the new regime wins — it is the statutory default and needs
    no Form 10-IEA opt-out, so recommending the old regime would cost the taxpayer
    paperwork for no benefit."""
    rules = get_rules(year)
    for gross in (500_000, 1_200_000, 3_000_000):
        comparison = compare_regimes(make_profile(gross, assessment_year=year), rules)
        old_tax = comparison.old.total_tax_liability
        new_tax = comparison.new.total_tax_liability
        expected = "old" if old_tax < new_tax else "new"
        assert comparison.recommended == expected
        assert comparison.savings == abs(old_tax - new_tax)
