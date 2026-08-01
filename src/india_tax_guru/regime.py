"""End-to-end computation for one regime, and side-by-side comparison.

Edge cases handled:
- Total income assembly order matters for loss set-off: house property loss
  offsets other heads BEFORE the slab tax is computed on the net figure.
- Capital gains are taxed separately (flat rates) and added to the slab tax on
  the remaining "normal" income — they must NOT be included in the amount that
  87A rebate/marginal-relief math uses for slab computation but ARE included in
  the total-income figure used to test the 87A eligibility threshold and surcharge
  brackets (per current law: 87A rebate does not apply to LTCG/STCG taxed under
  111A/112, only to the slab-rate tax component and other special-rate incomes
  narrowly listed — this tool applies rebate ONLY to the slab-tax portion, which
  is the conservative/correct reading for 111A/112A gains).
- Both regimes are always computed and compared, even if the taxpayer has already
  filed one way — the point is decision support, not just validation.
"""

from dataclasses import dataclass

from . import capital_gains as cg
from . import deductions as ded
from . import house_property as hp
from . import salary as sal
from .compute import add_cess, apply_87a_rebate, compute_surcharge, round_288b, slab_tax
from .models import TaxpayerProfile
from .rules.base import AssessmentYearRules, RegimeRules


@dataclass(frozen=True)
class RegimeResult:
    regime: str
    taxable_salary: int
    house_property_net: int
    other_income: int
    gross_total_income: int
    deductions_claimed: int
    total_income: int  # after deductions, before capital-gains-only additions folded back
    slab_taxable_income: int  # total_income minus special-rate capital gains
    tax_on_slab_income: int
    tax_on_capital_gains: int
    rebate_87a_applied: int
    surcharge: int
    cess: int
    total_tax_payable: int
    deduction_notes: list[str]
    other_notes: list[str]


def compute_regime(
    profile: TaxpayerProfile, rules: AssessmentYearRules, regime: str
) -> RegimeResult:
    regime_rules: RegimeRules = rules.old_regime if regime == "old" else rules.new_regime

    taxable_sal = (
        sal.total_taxable_salary(profile.salaries, regime) - regime_rules.standard_deduction
    )
    taxable_sal = max(0, taxable_sal)

    hp_results = [
        hp.compute_house_property(p, rules.house_property_loss_setoff_cap)
        for p in profile.house_properties
    ]
    hp_net = sum(
        r.set_off_this_year if r.income_or_loss < 0 else r.income_or_loss for r in hp_results
    )
    notes = [r.note for r in hp_results if r.note]

    cg_result = cg.compute_capital_gains(profile.capital_gains, rules)
    if cg_result.unabsorbed_loss_note:
        notes.append(cg_result.unabsorbed_loss_note)

    other_st_cg_income = cg_result.stcg_other_net  # taxed at slab rate, so folds into normal income

    oi = profile.other_income
    other_income_total = (
        oi.savings_bank_interest + oi.fd_interest + oi.dividend_income + oi.other_sources
    )

    employer_nps_deduction = sum(
        sal.max_80ccd2_deduction(s, regime_rules.max_80ccd2_pct_of_salary) for s in profile.salaries
    )

    ded_result = ded.compute_deductions(profile.deductions, profile.age_band, rules, regime)
    if ded_result.zeroed_by_regime:
        zeroed = ", ".join(sorted(ded_result.zeroed_by_regime))
        notes.append(f"{regime} regime disallows: {zeroed} (claimed but zeroed).")

    gross_total_income = taxable_sal + hp_net + other_income_total + other_st_cg_income

    total_deductions = ded_result.total + employer_nps_deduction
    slab_taxable_income = max(0, gross_total_income - total_deductions)

    tax_on_slab = slab_tax(slab_taxable_income, regime_rules)

    total_income_for_rebate_test = (
        slab_taxable_income + cg_result.ltcg_112a_taxable + cg_result.stcg_111a_net
    )
    tax_after_rebate = apply_87a_rebate(tax_on_slab, total_income_for_rebate_test, regime_rules)
    rebate_applied = tax_on_slab - tax_after_rebate

    tax_before_surcharge = tax_after_rebate + cg_result.tax_on_capital_gains
    surcharge = compute_surcharge(tax_before_surcharge, total_income_for_rebate_test, regime_rules)

    tax_plus_surcharge = tax_before_surcharge + surcharge
    cess = add_cess(tax_plus_surcharge, regime_rules.cess_rate)

    total_tax = round_288b(tax_plus_surcharge + cess, rules.rounding_unit)

    return RegimeResult(
        regime=regime,
        taxable_salary=taxable_sal,
        house_property_net=hp_net,
        other_income=other_income_total,
        gross_total_income=gross_total_income,
        deductions_claimed=total_deductions,
        total_income=slab_taxable_income,
        slab_taxable_income=slab_taxable_income,
        tax_on_slab_income=tax_on_slab,
        tax_on_capital_gains=cg_result.tax_on_capital_gains,
        rebate_87a_applied=rebate_applied,
        surcharge=surcharge,
        cess=cess,
        total_tax_payable=total_tax,
        deduction_notes=notes,
        other_notes=[],
    )


@dataclass(frozen=True)
class RegimeComparison:
    old: RegimeResult
    new: RegimeResult
    recommended: str
    savings: int


def compare_regimes(profile: TaxpayerProfile, rules: AssessmentYearRules) -> RegimeComparison:
    old_result = compute_regime(profile, rules, "old")
    new_result = compute_regime(profile, rules, "new")
    if old_result.total_tax_payable <= new_result.total_tax_payable:
        recommended, savings = "old", new_result.total_tax_payable - old_result.total_tax_payable
    else:
        recommended, savings = "new", old_result.total_tax_payable - new_result.total_tax_payable
    return RegimeComparison(
        old=old_result, new=new_result, recommended=recommended, savings=savings
    )
