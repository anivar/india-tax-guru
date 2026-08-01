from india_tax_guru.compute import apply_87a_rebate, slab_tax
from india_tax_guru.rules import get_rules


def test_slab_tax_new_regime_zero_below_exemption():
    rules = get_rules("2026-27")
    assert slab_tax(400_000, rules.new_regime) == 0


def test_slab_tax_new_regime_top_bracket():
    rules = get_rules("2026-27")
    # 24,00,000 -> 25,00,000 is entirely 30% bracket start; sanity check monotonic increase
    tax_at_2400k = slab_tax(2_400_000, rules.new_regime)
    tax_at_2500k = slab_tax(2_500_000, rules.new_regime)
    assert tax_at_2500k > tax_at_2400k


def test_87a_rebate_full_at_threshold():
    rules = get_rules("2026-27").new_regime
    tax = slab_tax(rules.rebate_87a_income_limit, rules)
    after = apply_87a_rebate(tax, rules.rebate_87a_income_limit, rules)
    assert after == 0


def test_87a_marginal_relief_just_above_threshold():
    rules = get_rules("2026-27").new_regime
    income = rules.rebate_87a_income_limit + 1000
    tax = slab_tax(income, rules)
    after = apply_87a_rebate(tax, income, rules)
    # tax increase over the threshold can never exceed the excess income
    assert after <= 1000


def test_87a_no_rebate_well_above_threshold():
    rules = get_rules("2026-27").new_regime
    income = rules.rebate_87a_income_limit * 3
    tax = slab_tax(income, rules)
    after = apply_87a_rebate(tax, income, rules)
    assert after == tax
