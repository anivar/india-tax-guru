from india_tax_guru.capital_gains import compute_capital_gains
from india_tax_guru.models import CapitalGainLot
from india_tax_guru.rules import get_rules


def test_equity_ltcg_exempt_up_to_threshold():
    rules = get_rules("2026-27")
    lots = [CapitalGainLot(asset_class="equity_mf", is_long_term=True, gain=1_000_000)]
    result = compute_capital_gains(lots, rules)
    assert result.ltcg_112a_taxable == 0
    assert result.tax_on_capital_gains == 0


def test_equity_ltcg_taxed_above_threshold():
    rules = get_rules("2026-27")
    lots = [CapitalGainLot(asset_class="equity_mf", is_long_term=True, gain=1_500_000)]
    result = compute_capital_gains(lots, rules)
    assert result.ltcg_112a_taxable == 250_000
    assert result.tax_on_capital_gains == round(250_000 * rules.ltcg_112a_rate)


def test_short_term_loss_offsets_long_term_gain():
    rules = get_rules("2026-27")
    lots = [
        CapitalGainLot(asset_class="equity_mf", is_long_term=False, gain=-200_000),
        CapitalGainLot(asset_class="equity_mf", is_long_term=True, gain=1_500_000),
    ]
    result = compute_capital_gains(lots, rules)
    # ST loss should reduce the LT gain base before the exemption threshold applies
    assert result.ltcg_112a_taxable < 250_000
    assert result.unabsorbed_loss_note is None


def test_unabsorbed_loss_flagged_not_silently_dropped():
    rules = get_rules("2026-27")
    lots = [CapitalGainLot(asset_class="equity_mf", is_long_term=False, gain=-500_000)]
    result = compute_capital_gains(lots, rules)
    assert result.unabsorbed_loss_note is not None
    assert result.tax_on_capital_gains == 0
