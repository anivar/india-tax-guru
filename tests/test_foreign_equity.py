"""Foreign-listed equity — the RSU case.

An Indian employee holding vested US-listed stock is the most common way to end up with
a capital gain that LOOKS like listed equity and is taxed nothing like it. No STT is
paid and a foreign exchange is not a recognised stock exchange in India, so s.111A and
s.112A simply do not reach it: no ₹1,25,000 exemption, no concessional equity rate, and
a 24-month long-term threshold instead of 12.

Picking `equity_listed` for such a holding would silently apply all three concessions,
which is why `foreign_equity` exists as a separate class.
"""

from datetime import date

from conftest import make_profile

from india_tax_guru.capital_gains import bucket_capital_gains, tax_on_special_rate_gains
from india_tax_guru.models import AssetClass, CapitalGainLot
from india_tax_guru.regime import compute_regime


def lot(asset_class, long_term=True, gain=1_000_000, acquired=None, transferred=None):
    return CapitalGainLot(
        asset_class=asset_class,
        is_long_term=long_term,
        gain=gain,
        acquired_on=acquired,
        transferred_on=transferred,
    )


def test_foreign_equity_is_not_a_112a_asset():
    assert lot(AssetClass.FOREIGN_EQUITY).is_equity is False
    assert lot(AssetClass.EQUITY_LISTED).is_equity is True


def test_foreign_equity_gets_no_112a_exemption(rules):
    """The same ₹1,00,000 gain is fully exempt as Indian equity, fully taxed as foreign."""
    indian = tax_on_special_rate_gains(
        bucket_capital_gains([lot(AssetClass.EQUITY_MF, gain=100_000)]), rules
    )
    foreign = tax_on_special_rate_gains(
        bucket_capital_gains([lot(AssetClass.FOREIGN_EQUITY, gain=100_000)]), rules
    )
    assert indian.tax == 0
    assert foreign.tax == round(100_000 * rules.ltcg_other_rate)


def test_foreign_equity_long_term_taxed_under_s112(rules):
    buckets = bucket_capital_gains([lot(AssetClass.FOREIGN_EQUITY, gain=2_000_000)])
    assert buckets.other_ltcg == 2_000_000
    assert buckets.equity_ltcg == 0
    result = tax_on_special_rate_gains(buckets, rules)
    assert result.tax == round(2_000_000 * rules.ltcg_other_rate)


def test_foreign_equity_short_term_falls_to_slab_rate(rules):
    """No s.111A 20% flat rate either — a short-term foreign gain is ordinary income."""
    profile = make_profile(
        2_000_000,
        capital_gains=[lot(AssetClass.FOREIGN_EQUITY, long_term=False, gain=1_000_000)],
    )
    result = compute_regime(profile, rules, "new")
    assert result.slab_rate_capital_gains == 1_000_000
    assert result.tax_on_special_rate_income == 0


def test_holding_period_derived_from_dates_when_both_given():
    """18 months is long-term for Indian listed equity and short-term for foreign."""
    acquired, transferred = date(2024, 1, 15), date(2025, 7, 15)
    indian = lot(
        AssetClass.EQUITY_LISTED, long_term=False, acquired=acquired, transferred=transferred
    )
    foreign = lot(
        AssetClass.FOREIGN_EQUITY, long_term=True, acquired=acquired, transferred=transferred
    )
    assert indian.held_for_months() == 18
    assert indian.is_long_term is True, "12-month threshold for Indian listed equity"
    assert foreign.is_long_term is False, "24-month threshold for foreign shares"


def test_caller_flag_is_overridden_not_trusted_when_dates_are_present():
    """A caller who wrongly ticks long-term on a 13-month foreign holding is corrected."""
    thirteen_months = lot(
        AssetClass.FOREIGN_EQUITY,
        long_term=True,
        acquired=date(2024, 4, 1),
        transferred=date(2025, 5, 1),
    )
    assert thirteen_months.is_long_term is False


def test_caller_flag_is_respected_when_dates_are_absent():
    assert lot(AssetClass.FOREIGN_EQUITY, long_term=True).is_long_term is True
    assert lot(AssetClass.FOREIGN_EQUITY, long_term=False).is_long_term is False


def test_specified_mf_stays_short_term_even_with_dates():
    """s.50AA is absolute — it outranks any holding-period derivation."""
    ten_years = lot(
        AssetClass.SPECIFIED_MF,
        long_term=True,
        acquired=date(2015, 1, 1),
        transferred=date(2025, 1, 1),
    )
    assert ten_years.is_long_term is False


def test_foreign_equity_costs_more_than_indian_equity_end_to_end(rules):
    gain = 2_000_000
    indian = make_profile(1_500_000, capital_gains=[lot(AssetClass.EQUITY_MF, gain=gain)])
    foreign = make_profile(1_500_000, capital_gains=[lot(AssetClass.FOREIGN_EQUITY, gain=gain)])
    indian_tax = compute_regime(indian, rules, "new").total_tax_liability
    foreign_tax = compute_regime(foreign, rules, "new").total_tax_liability
    # Same 12.5% rate, but the foreign holding loses the 1,25,000 exemption.
    assert foreign_tax > indian_tax
    assert foreign_tax - indian_tax == round(
        rules.ltcg_112a_exemption * rules.ltcg_112a_rate * 1.04
    )
