"""Capital gains: rates, the s.112A exemption, s.50AA, and set-off ordering."""

import pytest
from conftest import make_profile

from india_tax_guru.capital_gains import bucket_capital_gains, tax_on_special_rate_gains
from india_tax_guru.models import AssetClass, CapitalGainLot
from india_tax_guru.regime import compute_regime


def lot(asset_class, long_term, gain):
    return CapitalGainLot(asset_class=asset_class, is_long_term=long_term, gain=gain)


def test_112a_exemption_is_1_25_lakh_not_12_5_lakh(rules):
    """A 10x error here would make a 10,00,000 gain look entirely exempt."""
    assert rules.ltcg_112a_exemption == 125_000
    buckets = bucket_capital_gains([lot(AssetClass.EQUITY_MF, True, 1_000_000)])
    result = tax_on_special_rate_gains(buckets, rules)
    assert result.taxable_equity_ltcg == 875_000
    assert result.tax == round(875_000 * 0.125)


def test_equity_ltcg_fully_exempt_below_threshold(rules):
    buckets = bucket_capital_gains([lot(AssetClass.EQUITY_MF, True, 100_000)])
    assert tax_on_special_rate_gains(buckets, rules).tax == 0


def test_equity_stcg_taxed_at_20_pct(rules):
    buckets = bucket_capital_gains([lot(AssetClass.EQUITY_LISTED, False, 500_000)])
    assert tax_on_special_rate_gains(buckets, rules).tax == 100_000


def test_s50aa_forces_specified_mf_to_short_term(rules):
    """A specified mutual fund cannot be long-term however the caller labels it."""
    single = lot(AssetClass.SPECIFIED_MF, True, 1_000_000)
    assert single.is_long_term is False

    buckets = bucket_capital_gains([single])
    assert buckets.other_stcg == 1_000_000, "must be slab-rate, not 12.5%"
    assert tax_on_special_rate_gains(buckets, rules).tax == 0


def test_specified_mf_taxed_at_slab_rate_end_to_end(rules):
    """Slab-rate treatment costs a 30%-bracket taxpayer far more than 12.5% would."""
    profile = make_profile(
        2_000_000, capital_gains=[lot(AssetClass.SPECIFIED_MF, True, 1_000_000)]
    )
    result = compute_regime(profile, rules, "new")
    assert result.slab_rate_capital_gains == 1_000_000
    assert result.tax_on_special_rate_income == 0

    baseline = compute_regime(make_profile(2_000_000), rules, "new").total_tax_liability
    assert result.total_tax_liability - baseline > round(1_000_000 * 0.125)


def test_short_term_loss_may_offset_long_term_gain(rules):
    buckets = bucket_capital_gains(
        [
            lot(AssetClass.EQUITY_MF, False, -200_000),
            lot(AssetClass.EQUITY_MF, True, 1_000_000),
        ]
    )
    assert buckets.equity_ltcg == 800_000
    assert buckets.unabsorbed_short_term_loss == 0


def test_long_term_loss_may_not_offset_short_term_gain(rules):
    """s.74: a long-term loss is only ever set off against long-term gains."""
    buckets = bucket_capital_gains(
        [
            lot(AssetClass.EQUITY_MF, True, -300_000),
            lot(AssetClass.EQUITY_LISTED, False, 500_000),
        ]
    )
    assert buckets.equity_stcg == 500_000, "short-term gain must be untouched"
    assert buckets.unabsorbed_long_term_loss == 300_000


def test_short_term_loss_consumes_short_term_gain_first(rules):
    """Preserving the more flexible relief for later is the taxpayer-favourable order."""
    buckets = bucket_capital_gains(
        [
            lot(AssetClass.EQUITY_LISTED, False, 100_000),
            lot(AssetClass.EQUITY_LISTED, False, -100_000),
            lot(AssetClass.EQUITY_MF, True, 1_000_000),
        ]
    )
    assert buckets.equity_stcg == 0
    assert buckets.equity_ltcg == 1_000_000


def test_unabsorbed_loss_is_reported_not_silently_dropped(rules):
    buckets = bucket_capital_gains([lot(AssetClass.EQUITY_MF, False, -500_000)])
    assert buckets.unabsorbed_short_term_loss == 500_000
    assert buckets.notes


def test_basic_exemption_headroom_set_off_against_gains(rules):
    """Salary 2,00,000 leaves headroom under the 4,00,000 new-regime exemption."""
    buckets = bucket_capital_gains([lot(AssetClass.EQUITY_MF, True, 500_000)])
    without = tax_on_special_rate_gains(buckets, rules, basic_exemption_headroom=0)
    with_headroom = tax_on_special_rate_gains(buckets, rules, basic_exemption_headroom=200_000)
    assert with_headroom.basic_exemption_used == 200_000
    assert with_headroom.tax < without.tax
    assert with_headroom.notes


def test_headroom_applied_to_highest_taxed_gain_first(rules):
    """STCG at 20% should absorb headroom before LTCG at 12.5%."""
    buckets = bucket_capital_gains(
        [
            lot(AssetClass.EQUITY_LISTED, False, 300_000),
            lot(AssetClass.EQUITY_MF, True, 500_000),
        ]
    )
    result = tax_on_special_rate_gains(buckets, rules, basic_exemption_headroom=300_000)
    assert result.taxable_equity_stcg == 0
    assert result.taxable_equity_ltcg == 500_000 - rules.ltcg_112a_exemption


def test_non_resident_gets_no_headroom(rules):
    profile = make_profile(
        200_000,
        is_resident=False,
        capital_gains=[lot(AssetClass.EQUITY_MF, True, 500_000)],
    )
    resident = make_profile(
        200_000, capital_gains=[lot(AssetClass.EQUITY_MF, True, 500_000)]
    )
    assert (
        compute_regime(profile, rules, "new").total_tax_liability
        > compute_regime(resident, rules, "new").total_tax_liability
    )


@pytest.mark.parametrize("asset_class", list(AssetClass))
def test_every_asset_class_is_handled(asset_class, rules):
    """No asset class may fall through the bucketing and vanish."""
    buckets = bucket_capital_gains([lot(asset_class, True, 1_000_000)])
    total = buckets.equity_stcg + buckets.equity_ltcg + buckets.other_stcg + buckets.other_ltcg
    assert total == 1_000_000
