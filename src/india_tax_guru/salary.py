"""Salary income computation, including period-wise HRA exemption.

Edge cases handled:
- Multiple rent periods in a year (rent increase, city change mid-year).
- Metro (50% of basic) vs non-metro (40% of basic) split per period.
- Multiple employers (job change mid-year) — each SalaryIncome is summed independently;
  the caller is responsible for annualizing DA correctly per employer.
- HRA exemption is the LEAST of: actual HRA received, rent paid minus 10% of basic
  for that period, and the metro/non-metro % of basic for that period — computed
  period-by-period, not as a single annual shortcut (which overstates exemption when
  rent or city changes mid-year).
- Regime-gating: HRA exemption (s.10(13A)) and most Section 10(14) allowance
  exemptions (LTA, conveyance, etc.) apply ONLY in the old regime — the new regime
  disallows nearly all of them (a few narrow exceptions like transport allowance
  for specially-abled employees exist but are not modelled here). `taxable_salary`
  therefore takes an explicit `regime` argument rather than defaulting to "always
  exempt", so a caller can't accidentally overstate new-regime take-home.
"""

from .models import SalaryIncome


def hra_exemption(salary: SalaryIncome) -> int:
    hra_components = [c for c in salary.components if c.is_hra]
    total_hra_received = sum(c.annual_amount for c in hra_components)
    if total_hra_received == 0 or not salary.rent_periods:
        return 0

    total_rent_months = sum(p.months for p in salary.rent_periods)
    if total_rent_months == 0:
        return 0

    monthly_basic = salary.basic_plus_da_annual / 12
    monthly_hra_received = total_hra_received / 12

    exemption = 0
    for period in salary.rent_periods:
        period_basic = monthly_basic * period.months
        period_hra_received = monthly_hra_received * period.months
        period_rent = period.monthly_rent * period.months
        pct = 0.50 if period.is_metro else 0.40

        least_of = min(
            period_hra_received,
            max(0, period_rent - 0.10 * period_basic),
            pct * period_basic,
        )
        exemption += least_of

    return round(min(exemption, total_hra_received))


def other_exempt_allowances(salary: SalaryIncome) -> int:
    """Section 10(14) exemptions on non-HRA components (LTA, meal vouchers, conveyance)."""
    return sum(c.section_10_14_exempt_amount for c in salary.components if not c.is_hra)


def taxable_salary(salary: SalaryIncome, regime: str) -> int:
    gross = salary.gross_taxable
    exempt = (hra_exemption(salary) + other_exempt_allowances(salary)) if regime == "old" else 0
    return max(0, round(gross - exempt))


def total_taxable_salary(salaries: list[SalaryIncome], regime: str) -> int:
    return sum(taxable_salary(s, regime) for s in salaries)


def max_80ccd2_deduction(salary: SalaryIncome, cap_pct: float) -> int:
    """Employer NPS contribution eligible for 80CCD(2), capped at cap_pct of basic+DA.

    Not subject to the overall Chapter VI-A umbrella cap, and available in BOTH
    regimes (with a different cap_pct per regime — old regime caps at 10%,
    new regime at 14%, per Finance Act 2024).
    """
    cap = round(cap_pct * salary.basic_plus_da_annual)
    return min(salary.employer_nps_contribution, cap)
