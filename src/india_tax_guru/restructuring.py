"""CTC / salary-structure optimization: given a fixed annual CTC, search for the
component split (Basic/HRA/Special Allowance/employer NPS/tax-free perks) that
minimizes total tax, subject to realistic employer-policy constraints.

Edge cases handled:
- Basic salary is bounded to a realistic policy range (default 30%-50% of CTC) —
  the optimizer will NOT recommend basic=0 just because it minimizes tax, since
  that breaks PF/gratuity computations and is not something an employer would
  implement; the bound is a constructor parameter so callers can widen/narrow it.
- Employer NPS (80CCD(2)) is a genuine CTC trade-off, not free money: increasing
  it reduces take-home cash (it's deducted from the CTC pool, unlike a pure tax
  slab change) but is deductible in BOTH regimes up to the regime's cap % of
  basic+DA — so the optimizer treats it as diverting rupees FROM special
  allowance, not as an addition to CTC.
- Tax-free perquisites (meal vouchers, LTA) have small statutory caps — the
  optimizer treats them as constants the user supplies (policy-dependent), not
  as a free variable to maximize, since most employers cap these regardless of
  what would be tax-optimal.
- Because switching to the new regime disallows HRA/80C/80D/etc. entirely, a
  CTC split that's optimal under the old regime can be actively suboptimal
  under the new regime (where only 80CCD(2) and standard deduction matter) —
  the optimizer runs BOTH regimes for every candidate split and reports the
  best (split, regime) pair, not just the best split for a regime chosen in
  advance.
- If rent_annual is 0 (no HRA claim possible, e.g. owns home), HRA allocation
  is forced to a minimal/zero value rather than searched, since maximizing HRA
  with no rent produces a fully taxable, pointless allocation.
"""

from dataclasses import dataclass

from .models import (
    AgeBand,
    Deductions,
    RentPeriod,
    SalaryComponent,
    SalaryIncome,
    TaxpayerProfile,
)
from .regime import compute_regime
from .rules.base import AssessmentYearRules


@dataclass(frozen=True)
class CTCOptimizationInput:
    annual_ctc: int
    annual_rent: int
    is_metro: bool
    age_band: AgeBand
    other_deductions: Deductions
    fixed_meal_voucher_exempt: int = 26_400  # common employer policy, 2200/month
    fixed_lta_exempt: int = 0  # only exempt if actually claimed with travel proof
    basic_pct_range: tuple[float, float] = (0.30, 0.50)
    basic_pct_step: float = 0.05
    employer_nps_pct_range: tuple[float, float] = (0.0, 0.10)
    employer_nps_pct_step: float = 0.02


@dataclass(frozen=True)
class CTCCandidate:
    basic_pct: float
    employer_nps_pct: float
    basic_annual: int
    hra_annual: int
    employer_nps_annual: int
    special_allowance_annual: int
    regime: str
    total_tax: int
    take_home_annual: (
        int  # CTC - employer_nps (which never reaches the employee's bank account) - tax
    )


def _build_profile(
    inp: CTCOptimizationInput, basic_pct: float, nps_pct: float, rules: AssessmentYearRules
) -> tuple[TaxpayerProfile, int, int, int, int]:
    basic = round(inp.annual_ctc * basic_pct)
    employer_nps_cap_old = round(rules.old_regime.max_80ccd2_pct_of_salary * basic)
    employer_nps_cap_new = round(rules.new_regime.max_80ccd2_pct_of_salary * basic)
    employer_nps = min(round(basic * nps_pct), max(employer_nps_cap_old, employer_nps_cap_new))

    hra_target = round(0.50 * basic) if inp.is_metro else round(0.40 * basic)
    hra = hra_target if inp.annual_rent > 0 else 0

    reserved = basic + employer_nps + hra + inp.fixed_meal_voucher_exempt + inp.fixed_lta_exempt
    special_allowance = max(0, inp.annual_ctc - reserved)

    components = [
        SalaryComponent(name="Basic", annual_amount=basic, taxable=True),
        SalaryComponent(name="HRA", annual_amount=hra, taxable=True, is_hra=True),
        SalaryComponent(
            name="Meal Vouchers",
            annual_amount=inp.fixed_meal_voucher_exempt,
            taxable=True,
            section_10_14_exempt_amount=inp.fixed_meal_voucher_exempt,
        ),
        SalaryComponent(name="Special Allowance", annual_amount=special_allowance, taxable=True),
    ]
    if inp.fixed_lta_exempt:
        components.append(
            SalaryComponent(
                name="LTA",
                annual_amount=inp.fixed_lta_exempt,
                taxable=True,
                section_10_14_exempt_amount=inp.fixed_lta_exempt,
            )
        )

    salary = SalaryIncome(
        employer_name="candidate",
        components=components,
        basic_plus_da_annual=basic,
        rent_periods=[
            RentPeriod(months=12, monthly_rent=inp.annual_rent // 12, is_metro=inp.is_metro)
        ]
        if inp.annual_rent > 0
        else [],
        employer_nps_contribution=employer_nps,
    )

    return (
        TaxpayerProfile(
            assessment_year=rules.assessment_year,
            age_band=inp.age_band,
            salaries=[salary],
            deductions=inp.other_deductions,
        ),
        basic,
        hra,
        employer_nps,
        special_allowance,
    )


def _frange(lo: float, hi: float, step: float):
    vals = []
    v = lo
    while v <= hi + 1e-9:
        vals.append(round(v, 4))
        v += step
    return vals


def optimize_ctc_split(inp: CTCOptimizationInput, rules: AssessmentYearRules) -> list[CTCCandidate]:
    candidates: list[CTCCandidate] = []
    basic_pcts = _frange(*inp.basic_pct_range, inp.basic_pct_step)
    nps_pcts = _frange(*inp.employer_nps_pct_range, inp.employer_nps_pct_step)

    for basic_pct in basic_pcts:
        for nps_pct in nps_pcts:
            profile, basic, hra, employer_nps, special = _build_profile(
                inp, basic_pct, nps_pct, rules
            )
            for regime in ("old", "new"):
                result = compute_regime(profile, rules, regime)
                take_home = inp.annual_ctc - employer_nps - result.total_tax_payable
                candidates.append(
                    CTCCandidate(
                        basic_pct=basic_pct,
                        employer_nps_pct=nps_pct,
                        basic_annual=basic,
                        hra_annual=hra,
                        employer_nps_annual=employer_nps,
                        special_allowance_annual=special,
                        regime=regime,
                        total_tax=result.total_tax_payable,
                        take_home_annual=take_home,
                    )
                )

    candidates.sort(key=lambda c: -c.take_home_annual)
    return candidates


def best_ctc_split(inp: CTCOptimizationInput, rules: AssessmentYearRules) -> CTCCandidate:
    return optimize_ctc_split(inp, rules)[0]
