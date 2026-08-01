"""Slab tax, s.87A rebate, surcharge (with marginal relief), cess, and statutory rounding.

Edge cases handled:
- Old-regime slabs vary by age: basic exemption 2,50,000 / 3,00,000 (senior 60-80) /
  5,00,000 (super-senior 80+). Super-seniors lose the 5% bracket outright rather than
  merely shifting it, so each age band carries its own explicit slab tuple. The new
  regime has no age concession.
- s.87A rebate nullifies tax entirely at/below the regime's threshold. Marginal relief
  for income just above the threshold exists ONLY in the new regime — applying it in
  the old regime understates tax, so it is gated on an explicit per-regime flag.
- Surcharge attributable to s.111A / s.112A / s.112 gains and dividend income is capped
  at 15% even when the taxpayer's general surcharge rate is higher (25%/37%). Surcharge
  is therefore computed on TWO bases at two rates, not on one blended total.
- Surcharge marginal relief: crossing a threshold cannot increase (tax + surcharge) by
  more than the income that crossed it. Computing this correctly requires tax recomputed
  at the threshold, which requires the income composition — so the caller injects a
  `tax_at_total_income` callable rather than this module guessing. The excess income is
  assumed to come off slab-rate income first (the common case: salary pushing a taxpayer
  over), leaving special-rate gains unchanged at the threshold.
- s.288A/288B rounding is half-UP to the nearest 10, not Python's default banker's
  rounding (which would turn 1005 into 1000 instead of 1010). Applied once at the end,
  never at intermediate steps.
"""

from collections.abc import Callable

from .models import AgeBand
from .rules.base import RegimeRules, SlabBracket


def slabs_for_age(
    regime_rules: RegimeRules, age_band: AgeBand, is_resident: bool = True
) -> tuple[SlabBracket, ...]:
    """Resolve the slab structure for a taxpayer's age band.

    The raised basic exemption at 60 and 80 is available only to a RESIDENT individual —
    a non-resident of any age is taxed from the ordinary threshold. Applying the age
    concession on age alone hands a 62-year-old non-resident an extra 50,000 of exempt
    income they are not entitled to.

    A regime with no age concession leaves `slabs_senior`/`slabs_super_senior` as None,
    which falls back to the standard slabs — expressed explicitly so that a future age
    concession cannot be half-applied by omission.
    """
    if not is_resident:
        return regime_rules.slabs
    is_senior = age_band in (AgeBand.SENIOR_60_80, AgeBand.SUPER_SENIOR_80_PLUS)
    if age_band == AgeBand.SUPER_SENIOR_80_PLUS and regime_rules.slabs_super_senior:
        return regime_rules.slabs_super_senior
    if is_senior and regime_rules.slabs_senior:
        return regime_rules.slabs_senior
    return regime_rules.slabs


def basic_exemption_limit(slabs: tuple[SlabBracket, ...]) -> int:
    """The income up to which the slab rate is nil — the first bracket's ceiling."""
    for bracket in slabs:
        if bracket.rate == 0.0 and bracket.upto is not None:
            return bracket.upto
    return 0


def slab_tax(taxable_income: int, slabs: tuple[SlabBracket, ...]) -> int:
    if taxable_income <= 0:
        return 0
    tax = 0.0
    lower = 0
    for bracket in slabs:
        if taxable_income <= lower:
            break
        upper = bracket.upto if bracket.upto is not None else taxable_income
        slice_amount = min(taxable_income, upper) - lower
        if slice_amount > 0:
            tax += slice_amount * bracket.rate
        lower = upper
        if bracket.upto is None:
            break
    return round(tax)


def apply_87a_rebate(
    tax_on_slab_income: int,
    total_income: int,
    regime_rules: RegimeRules,
    is_resident: bool = True,
    is_individual: bool = True,
) -> int:
    """Tax on slab income after s.87A rebate. Never negative.

    The rebate is confined to a RESIDENT INDIVIDUAL — both words carry weight. A
    non-resident pays the full slab tax however low their income, and so does an HUF:
    s.87A opens with "an assessee, being an individual resident in India". Granting it
    on income alone can wipe out a real liability entirely.

    The rebate is applied only to slab-rate tax — tax on s.111A/112A gains is not
    rebatable, so the caller must pass slab-rate tax alone and add special-rate tax
    afterwards.
    """
    if not is_resident or not is_individual:
        return tax_on_slab_income
    if total_income <= regime_rules.rebate_87a_income_limit:
        rebate = min(tax_on_slab_income, regime_rules.rebate_87a_max_amount)
        return max(0, tax_on_slab_income - rebate)

    if not regime_rules.rebate_87a_has_marginal_relief:
        return tax_on_slab_income

    # Marginal relief (new regime only): tax cannot exceed the income earned past the
    # rebate threshold, otherwise one extra rupee of income would cost far more than one
    # rupee of tax.
    excess_income = total_income - regime_rules.rebate_87a_income_limit
    return min(tax_on_slab_income, excess_income)


def surcharge_rate_for(
    total_income: int, special_rate_income: int, regime_rules: RegimeRules
) -> tuple[float, int | None]:
    """Applicable general surcharge rate, and the threshold that triggered it.

    The clauses are not a ladder on one quantity. Clauses flagged
    `basis_excludes_special_income` (the 25% and 37% ones) test income with dividend and
    s.111A/112/112A gains STRIPPED OUT; the rest test total income as it stands. So a
    taxpayer with 30,00,000 of salary and 2,50,00,000 of equity gains does NOT reach 25%
    — their non-special income is far below 2 crore — and the residual clause charges
    15% on everything instead. Testing the 25% clause against total income would
    over-tax exactly the taxpayer most likely to notice.
    """
    excluding = max(0, total_income - special_rate_income)

    exclusive = sorted(
        (c for c in regime_rules.surcharge if c.basis_excludes_special_income),
        key=lambda c: -c.above,
    )
    for clause in exclusive:
        if excluding > clause.above and (clause.upto is None or excluding <= clause.upto):
            return min(clause.rate, regime_rules.surcharge_cap_rate), clause.above
    # An open-ended exclusive clause still applies above its own ceiling-less range.
    for clause in exclusive:
        if clause.upto is None and excluding > clause.above:
            return min(clause.rate, regime_rules.surcharge_cap_rate), clause.above

    if total_income > regime_rules.surcharge_residual_above:
        return (
            min(regime_rules.surcharge_residual_rate, regime_rules.surcharge_cap_rate),
            regime_rules.surcharge_residual_above,
        )

    inclusive = sorted(
        (c for c in regime_rules.surcharge if not c.basis_excludes_special_income),
        key=lambda c: -c.above,
    )
    for clause in inclusive:
        if total_income > clause.above:
            return min(clause.rate, regime_rules.surcharge_cap_rate), clause.above
    return 0.0, None


def _previous_surcharge_rate(
    threshold: int, special_rate_income: int, regime_rules: RegimeRules
) -> float:
    """The surcharge rate applying at total income exactly equal to `threshold`."""
    rate, _ = surcharge_rate_for(threshold, special_rate_income, regime_rules)
    return rate


def compute_surcharge(
    tax_on_normal_income: int,
    tax_on_special_income: int,
    total_income: int,
    special_rate_income: int,
    regime_rules: RegimeRules,
    tax_at_total_income: Callable[[int], int],
) -> tuple[int, str | None]:
    """Surcharge with the 15% special-income cap and threshold marginal relief.

    `special_rate_income` is the INCOME taxed under s.111A/112/112A plus dividends —
    used both to pick the clause and to apply the 15% cap. `tax_at_total_income(x)`
    must return total tax (slab tax after rebate PLUS special-rate tax, before surcharge
    and cess) for a hypothetical total income of x.

    Returns (surcharge, marginal_relief_note).
    """
    rate, threshold = surcharge_rate_for(total_income, special_rate_income, regime_rules)
    if rate == 0.0 or threshold is None:
        return 0, None

    capped_rate = min(rate, regime_rules.surcharge_special_income_cap_rate)
    raw_surcharge = round(tax_on_normal_income * rate + tax_on_special_income * capped_rate)

    # Marginal relief: (tax + surcharge) at this income must not exceed
    # (tax + surcharge) at the threshold plus the income earned beyond it.
    prev_rate = _previous_surcharge_rate(threshold, special_rate_income, regime_rules)
    prev_capped_rate = min(prev_rate, regime_rules.surcharge_special_income_cap_rate)

    tax_at_threshold = tax_at_total_income(threshold)
    # The excess income is assumed to come off slab-rate income, so special-rate tax is
    # unchanged at the threshold; the remainder is the normal-income tax there.
    normal_tax_at_threshold = max(0, tax_at_threshold - tax_on_special_income)
    special_tax_at_threshold = min(tax_on_special_income, tax_at_threshold)
    surcharge_at_threshold = round(
        normal_tax_at_threshold * prev_rate + special_tax_at_threshold * prev_capped_rate
    )

    ceiling = tax_at_threshold + surcharge_at_threshold + (total_income - threshold)
    tax_here = tax_on_normal_income + tax_on_special_income

    if tax_here + raw_surcharge > ceiling:
        relieved = max(0, ceiling - tax_here)
        return relieved, (
            f"Surcharge marginal relief applied at the {threshold:,} threshold: "
            f"surcharge reduced from {raw_surcharge:,} to {relieved:,}."
        )
    return raw_surcharge, None


def add_cess(tax_plus_surcharge: int, cess_rate: float) -> int:
    return round(tax_plus_surcharge * cess_rate)


def round_half_up(amount: float) -> int:
    """Round to the nearest rupee, halves upward (not Python's banker's rounding)."""
    return int(amount + 0.5) if amount >= 0 else -int(-amount + 0.5)


def round_288b(amount: int, unit: int) -> int:
    """s.288B rounding: to the nearest `unit` rupees, with a half rounding UP.

    Python's built-in round() is banker's rounding and would send 1005 to 1000; the
    statute sends it to 1010.
    """
    if unit <= 1:
        return int(amount)
    if amount < 0:
        return -(((-amount) + unit // 2) // unit * unit)
    return (amount + unit // 2) // unit * unit
