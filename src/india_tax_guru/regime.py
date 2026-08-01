"""End-to-end computation for one regime, and side-by-side comparison.

Edge cases handled:
- Order of assembly matters. House-property loss reduces other heads (subject to its own
  cap and regime gating) BEFORE Chapter VI-A deductions, which in turn apply BEFORE the
  slab computation. Capital gains taxed at special rates never enter the slab base.
- Non-equity SHORT-term gains are taxed at slab rates and so DO fold into normal income;
  equity short-term (s.111A) and all long-term gains do not.
- The s.87A rebate is applied only to slab-rate tax. Tax on s.111A/112A gains is not
  rebatable, so it is added after the rebate rather than before.
- A resident whose normal income falls short of the basic exemption limit sets the
  shortfall off against capital gains. The headroom is computed from income AFTER
  Chapter VI-A deductions, which is the figure the slab actually charges.
- Surcharge is computed on two bases: tax on normal income at the general rate, and tax
  on s.111A/112A/112 gains plus dividend income at a rate capped at 15%. Dividend tax is
  attributed at the MARGINAL rate (tax with dividends less tax without), not by
  proportional averaging, since dividends sit at the top of the slab stack.
- Surcharge marginal relief needs tax recomputed at the threshold, so this module injects
  a closure that has the full income composition in scope.
- Taxes already paid (TDS, advance tax, self-assessment) are netted off to produce a
  refund or balance-payable figure. `total_tax_liability` is gross of these; the field
  that nets them is named separately so neither can be mistaken for the other.
"""

from dataclasses import dataclass, field

from . import capital_gains as cg
from . import deductions as ded
from . import house_property as hp
from . import salary as sal
from .compute import (
    add_cess,
    apply_87a_rebate,
    basic_exemption_limit,
    compute_surcharge,
    round_288b,
    slab_tax,
    slabs_for_age,
)
from .interest import compute_advance_tax_interest
from .models import Regime, TaxpayerProfile
from .rules.base import AssessmentYearRules, RegimeRules


@dataclass(frozen=True)
class RegimeResult:
    regime: str
    # Heads of income
    gross_salary: int
    net_salary: int
    house_property: int
    other_income: int
    slab_rate_capital_gains: int  # non-equity short-term, taxed at slab rates
    special_rate_capital_gains: int  # s.111A/112A/112, taxed at flat rates
    gross_total_income: int  # excludes special-rate gains; those are added into total_income
    deductions_claimed: int
    total_income: int  # statutory total income, incl. special-rate gains, s.288A rounded
    slab_taxable_income: int  # the base the slab actually charges
    # Tax
    tax_on_slab_income: int
    rebate_87a: int
    tax_on_special_rate_income: int
    surcharge: int
    cess: int
    total_tax_liability: int  # gross — BEFORE any credit for taxes already paid
    # Credits and settlement
    taxes_already_paid: int
    interest_234b: int
    interest_234c: int
    refund_due: int  # positive if the taxpayer gets money back
    balance_payable: int  # positive if the taxpayer still owes
    notes: list[str] = field(default_factory=list)


def compute_regime(
    profile: TaxpayerProfile, rules: AssessmentYearRules, regime: str | Regime
) -> RegimeResult:
    regime = Regime(regime)
    regime_rules: RegimeRules = (
        rules.old_regime if regime is Regime.OLD else rules.new_regime
    )
    notes: list[str] = []

    salary = sal.compute_salary(profile.salaries, regime_rules)
    notes.extend(salary.notes)

    house = hp.compute_house_properties(profile.house_properties, rules, regime_rules)
    notes.extend(house.notes)

    buckets = cg.bucket_capital_gains(profile.capital_gains)
    notes.extend(buckets.notes)

    oi = profile.other_income
    other_income_total = (
        oi.savings_bank_interest + oi.fd_interest + oi.dividend_income + oi.other_sources
    )

    gross_total_income = (
        salary.net_salary
        + house.contribution_to_total_income
        + other_income_total
        + buckets.other_stcg
    )

    ded_result = ded.compute_deductions(
        profile.deductions, profile.age_band, rules, str(regime), gross_total_income
    )
    notes.extend(ded_result.notes)
    if ded_result.zeroed_by_regime:
        zeroed = ", ".join(sorted(ded_result.zeroed_by_regime))
        notes.append(f"{regime} regime disallows: {zeroed} (claimed but zeroed).")

    total_deductions = ded_result.total + salary.employer_nps_deduction
    slab_taxable_income = max(0, gross_total_income - total_deductions)

    slabs = slabs_for_age(regime_rules, profile.age_band)
    exemption_limit = basic_exemption_limit(slabs)
    headroom = (
        max(0, exemption_limit - slab_taxable_income) if profile.is_resident else 0
    )

    cg_tax = cg.tax_on_special_rate_gains(buckets, rules, headroom)
    notes.extend(cg_tax.notes)

    special_rate_gains = buckets.equity_stcg + buckets.equity_ltcg + buckets.other_ltcg
    total_income = round_288b(slab_taxable_income + special_rate_gains, rules.rounding_unit)

    tax_on_slab = slab_tax(slab_taxable_income, slabs)
    tax_after_rebate = apply_87a_rebate(tax_on_slab, total_income, regime_rules)
    rebate = tax_on_slab - tax_after_rebate

    # Dividend tax attributed at the marginal rate — dividends sit atop the slab stack.
    dividend_marginal_tax = 0
    if oi.dividend_income > 0 and slab_taxable_income > 0:
        without_dividend = max(0, slab_taxable_income - oi.dividend_income)
        dividend_marginal_tax = min(
            tax_after_rebate, tax_on_slab - slab_tax(without_dividend, slabs)
        )
        dividend_marginal_tax = max(0, dividend_marginal_tax)

    tax_on_special_income = cg_tax.tax + dividend_marginal_tax
    tax_on_normal_income = tax_after_rebate - dividend_marginal_tax

    def tax_at_total_income(hypothetical_total: int) -> int:
        """Total tax (slab after rebate + special-rate) at a lower hypothetical income.

        The reduction is taken off slab-rate income, since that is what the marginal
        rupees crossing a surcharge threshold almost always are.
        """
        reduction = total_income - hypothetical_total
        hypo_slab_base = max(0, slab_taxable_income - reduction)
        hypo_slab_tax = slab_tax(hypo_slab_base, slabs)
        hypo_slab_tax = apply_87a_rebate(hypo_slab_tax, hypothetical_total, regime_rules)
        return hypo_slab_tax + cg_tax.tax

    # Income (not tax) that the surcharge clauses strip out when testing the 25%/37%
    # thresholds, and that the 15% cap attaches to: s.111A/112/112A gains and dividends.
    special_rate_income = special_rate_gains + oi.dividend_income

    surcharge, relief_note = compute_surcharge(
        tax_on_normal_income,
        tax_on_special_income,
        total_income,
        special_rate_income,
        regime_rules,
        tax_at_total_income,
    )
    if relief_note:
        notes.append(relief_note)

    tax_plus_surcharge = tax_after_rebate + cg_tax.tax + surcharge
    cess = add_cess(tax_plus_surcharge, regime_rules.cess_rate)
    total_tax_liability = round_288b(tax_plus_surcharge + cess, rules.rounding_unit)

    paid = profile.taxes_paid.total
    interest_234b = 0
    interest_234c = 0
    checkpoints = profile.taxes_paid.advance_tax_by_checkpoint
    if checkpoints is not None:
        interest = compute_advance_tax_interest(
            assessed_tax=total_tax_liability,
            advance_tax_paid_total=profile.taxes_paid.advance_tax,
            cumulative_paid_by_checkpoint=checkpoints,
            months_elapsed_234b=profile.taxes_paid.months_elapsed_for_234b,
        )
        interest_234b = interest.section_234b
        interest_234c = interest.section_234c
        notes.extend(interest.notes)

    settlement = total_tax_liability + interest_234b + interest_234c - paid

    return RegimeResult(
        regime=str(regime),
        gross_salary=salary.gross_salary,
        net_salary=salary.net_salary,
        house_property=house.contribution_to_total_income,
        other_income=other_income_total,
        slab_rate_capital_gains=buckets.other_stcg,
        special_rate_capital_gains=special_rate_gains,
        gross_total_income=gross_total_income,
        deductions_claimed=total_deductions,
        total_income=total_income,
        slab_taxable_income=slab_taxable_income,
        tax_on_slab_income=tax_on_slab,
        rebate_87a=rebate,
        tax_on_special_rate_income=cg_tax.tax,
        surcharge=surcharge,
        cess=cess,
        total_tax_liability=total_tax_liability,
        taxes_already_paid=paid,
        interest_234b=interest_234b,
        interest_234c=interest_234c,
        refund_due=max(0, -settlement),
        balance_payable=max(0, settlement),
        notes=notes,
    )


@dataclass(frozen=True)
class RegimeComparison:
    old: RegimeResult
    new: RegimeResult
    recommended: str
    savings: int


def compare_regimes(profile: TaxpayerProfile, rules: AssessmentYearRules) -> RegimeComparison:
    old_result = compute_regime(profile, rules, Regime.OLD)
    new_result = compute_regime(profile, rules, Regime.NEW)
    # Ties go to the NEW regime: it is the statutory default under s.115BAC, so choosing
    # it costs the taxpayer nothing and avoids a Form 10-IEA opt-out filing.
    if new_result.total_tax_liability <= old_result.total_tax_liability:
        recommended = str(Regime.NEW)
        savings = old_result.total_tax_liability - new_result.total_tax_liability
    else:
        recommended = str(Regime.OLD)
        savings = new_result.total_tax_liability - old_result.total_tax_liability
    return RegimeComparison(
        old=old_result, new=new_result, recommended=recommended, savings=savings
    )


__all__ = ["RegimeResult", "RegimeComparison", "compute_regime", "compare_regimes"]
