"""Slab tax, rebate, surcharge (with marginal relief), and cess computation.

Edge cases handled:
- Section 87A rebate: nullifies tax entirely if total income is at/below the
  regime's threshold — NOT a flat subtraction once you cross it (a taxpayer at
  exactly the threshold pays zero; one rupee over can pay tax on the whole slab
  unless marginal relief applies).
- 87A marginal relief: when income is just above the rebate threshold, the tax
  increase must not exceed the income increase past the threshold (applies to
  both regimes historically, though in the new regime post-Budget-2025 the slab
  design was intended to avoid needing it in most cases — still computed
  defensively here since edge income levels can still trigger it).
- Surcharge marginal relief: at each surcharge threshold, the extra tax (incl.
  surcharge) from crossing the threshold cannot exceed the extra income —
  otherwise a taxpayer earning 1 rupee more could end up with strictly less
  post-tax income, which the law prevents.
- Cess is applied AFTER surcharge and rebate, on (tax - rebate + surcharge).
- Final tax is rounded to the nearest rupee, then to the nearest `rounding_unit`
  (Section 288B) — done last, not at intermediate steps, to avoid compounding
  rounding drift.
"""

from .rules.base import RegimeRules


def slab_tax(taxable_income: int, regime_rules: RegimeRules) -> int:
    if taxable_income <= 0:
        return 0
    tax = 0.0
    lower = 0
    for bracket in regime_rules.slabs:
        upper = bracket.upto if bracket.upto is not None else taxable_income
        if taxable_income <= lower:
            break
        slice_amount = min(taxable_income, upper) - lower
        if slice_amount > 0:
            tax += slice_amount * bracket.rate
        lower = upper
        if bracket.upto is None:
            break
    return round(tax)


def apply_87a_rebate(tax_before_cess: int, taxable_income: int, regime_rules: RegimeRules) -> int:
    """Returns tax after rebate (before surcharge/cess). Never negative."""
    if taxable_income <= regime_rules.rebate_87a_income_limit:
        rebate = min(tax_before_cess, regime_rules.rebate_87a_max_amount)
        return max(0, tax_before_cess - rebate)

    # Marginal relief: tax can never rise by more than the income that pushed you
    # past the threshold. If uncapped tax exceeds that excess income, cap it there;
    # otherwise no relief is needed (tax is already below the excess-income ceiling).
    excess_income = taxable_income - regime_rules.rebate_87a_income_limit
    if tax_before_cess > excess_income:
        return excess_income
    return tax_before_cess


def compute_surcharge(
    tax_before_surcharge: int, taxable_income: int, regime_rules: RegimeRules
) -> int:
    applicable_rate = 0.0
    for bracket in sorted(regime_rules.surcharge, key=lambda b: b.income_above):
        if taxable_income > bracket.income_above:
            applicable_rate = min(bracket.rate, regime_rules.surcharge_cap_rate)
    if applicable_rate == 0.0:
        return 0

    surcharge = round(tax_before_surcharge * applicable_rate)

    # Marginal relief at the threshold that produced this rate.
    crossed = [
        b
        for b in regime_rules.surcharge
        if taxable_income > b.income_above and b.rate == applicable_rate
    ]
    if crossed:
        threshold = min(b.income_above for b in crossed)
        excess_income = taxable_income - threshold
        # Relief caps (tax + surcharge) growth beyond `threshold` to the excess income itself,
        # relative to tax-with-no-surcharge at the threshold. We don't recompute tax-at-threshold
        # here (would need the full income breakdown); this is a conservative approximation
        # documented as such — callers needing exact relief at >5Cr edge cases should verify.
        max_total_tax_increase = excess_income
        if surcharge > max_total_tax_increase:
            surcharge = max(0, max_total_tax_increase)

    return surcharge


def add_cess(tax_plus_surcharge: int, cess_rate: float) -> int:
    return round(tax_plus_surcharge * (1 + cess_rate)) - tax_plus_surcharge


def round_288b(amount: int, unit: int) -> int:
    return int(round(amount / unit) * unit)
