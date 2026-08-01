"""CTC / salary-structure optimization: given a fixed annual CTC, search the component
split that maximizes take-home pay, subject to realistic employer-policy constraints.

Edge cases handled:
- Basic salary is bounded to a realistic policy range (30%-50% of CTC by default). An
  unbounded search would drive basic toward zero, which minimizes tax but breaks PF and
  gratuity and is not something an employer will implement. The bound is a parameter so
  a caller with a different policy can widen it.
- Employer NPS is a genuine trade-off, not free money: it is part of CTC, so every rupee
  routed there is a rupee that does not reach the employee's bank account. It is
  therefore modelled as diverting money FROM special allowance, and take-home is
  computed net of it. Contribution beyond the 80CCD(2) cap remains taxable, which the
  salary module handles, so over-allocating is correctly punished rather than rewarded.
- The 80CCD(2) cap differs by regime (10% of basic+DA old, 14% new). The cap is applied
  per regime downstream, so the raw contribution is passed through unclamped — clamping
  it here to the more generous of the two would hand old-regime candidates a deduction
  they are not entitled to.
- HRA is allocated to exactly the amount that is fully exempt given the rent actually
  paid — min(50%/40% of basic, rent less 10% of basic). Allocating more is not harmful
  (the excess is taxable exactly as special allowance would be) but it is misleading in
  the output, since it implies an exemption the taxpayer cannot claim.
- If no rent is paid, HRA is forced to zero rather than searched: HRA with no rent is
  fully taxable, so the allocation would be pure noise.
- Because the new regime disallows HRA and Chapter VI-A entirely, a split that is optimal
  under the old regime can be actively bad under the new one. Every candidate split is
  therefore evaluated under BOTH regimes and the best (split, regime) pair is returned,
  rather than optimizing a split for a regime chosen in advance.
"""

from dataclasses import dataclass

from .models import (
    AgeBand,
    Deductions,
    Regime,
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
    fixed_meal_voucher_exempt: int = 26_400  # common employer policy, 2,200/month
    fixed_lta_exempt: int = 0  # exempt only if actually claimed with travel proof
    basic_pct_range: tuple[float, float] = (0.30, 0.50)
    basic_pct_step: float = 0.05
    employer_nps_pct_range: tuple[float, float] = (0.0, 0.14)
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
    take_home_annual: int  # CTC less employer NPS (never reaches the employee) less tax


def _build_profile(
    inp: CTCOptimizationInput, basic_pct: float, nps_pct: float, rules: AssessmentYearRules
) -> tuple[TaxpayerProfile, int, int, int, int]:
    basic = round(inp.annual_ctc * basic_pct)
    employer_nps = round(basic * nps_pct)

    if inp.annual_rent > 0:
        pct = 0.50 if inp.is_metro else 0.40
        hra = max(0, min(round(pct * basic), inp.annual_rent - round(0.10 * basic)))
    else:
        hra = 0

    reserved = basic + employer_nps + hra + inp.fixed_meal_voucher_exempt + inp.fixed_lta_exempt
    special_allowance = max(0, inp.annual_ctc - reserved)

    components = [
        SalaryComponent(name="Basic", annual_amount=basic),
        SalaryComponent(name="HRA", annual_amount=hra, is_hra=True),
        SalaryComponent(
            name="Meal Vouchers",
            annual_amount=inp.fixed_meal_voucher_exempt,
            section_10_14_exempt_amount=inp.fixed_meal_voucher_exempt,
        ),
        SalaryComponent(name="Special Allowance", annual_amount=special_allowance),
    ]
    if inp.fixed_lta_exempt:
        components.append(
            SalaryComponent(
                name="LTA",
                annual_amount=inp.fixed_lta_exempt,
                section_10_14_exempt_amount=inp.fixed_lta_exempt,
            )
        )

    salary = SalaryIncome(
        employer_name="candidate",
        components=components,
        basic_plus_da_annual=basic,
        rent_periods=(
            [RentPeriod(months=12, monthly_rent=inp.annual_rent // 12, is_metro=inp.is_metro)]
            if inp.annual_rent > 0
            else []
        ),
        employer_nps_contribution=employer_nps,
    )

    profile = TaxpayerProfile(
        assessment_year=rules.assessment_year,
        age_band=inp.age_band,
        salaries=[salary],
        deductions=inp.other_deductions,
    )
    return profile, basic, hra, employer_nps, special_allowance


def _frange(lo: float, hi: float, step: float) -> list[float]:
    values = []
    current = lo
    while current <= hi + 1e-9:
        values.append(round(current, 4))
        current += step
    return values


def optimize_ctc_split(
    inp: CTCOptimizationInput, rules: AssessmentYearRules
) -> list[CTCCandidate]:
    candidates: list[CTCCandidate] = []
    for basic_pct in _frange(*inp.basic_pct_range, inp.basic_pct_step):
        for nps_pct in _frange(*inp.employer_nps_pct_range, inp.employer_nps_pct_step):
            profile, basic, hra, employer_nps, special = _build_profile(
                inp, basic_pct, nps_pct, rules
            )
            for regime in (Regime.OLD, Regime.NEW):
                result = compute_regime(profile, rules, regime)
                candidates.append(
                    CTCCandidate(
                        basic_pct=basic_pct,
                        employer_nps_pct=nps_pct,
                        basic_annual=basic,
                        hra_annual=hra,
                        employer_nps_annual=employer_nps,
                        special_allowance_annual=special,
                        regime=str(regime),
                        total_tax=result.total_tax_liability,
                        take_home_annual=inp.annual_ctc
                        - employer_nps
                        - result.total_tax_liability,
                    )
                )
    candidates.sort(key=lambda c: -c.take_home_annual)
    return candidates


def best_ctc_split(inp: CTCOptimizationInput, rules: AssessmentYearRules) -> CTCCandidate:
    return optimize_ctc_split(inp, rules)[0]
