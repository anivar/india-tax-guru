"""Income from salary: exemptions, period-wise HRA, and section 16 deductions.

Edge cases handled:
- HRA exemption (s.10(13A)) is the LEAST of: HRA actually received, rent paid minus 10%
  of basic, and 50% (metro) or 40% (non-metro) of basic — computed PERIOD BY PERIOD.
  A single annual calculation overstates the exemption whenever rent or city changes
  mid-year, which is exactly when taxpayers most want the number checked.
- Rent periods that do not add up to twelve months are legitimate (a taxpayer who rented
  for only part of the year) but are also a common data-entry error, so a warning is
  emitted rather than silently pro-rating.
- Regime gating: HRA and most s.10(14) allowance exemptions, and professional tax under
  s.16(iii), are available only in the old regime. The standard deduction is available
  in both, at different amounts.
- 80CCD(2) employer NPS is part of gross salary AND deductible in both regimes, at
  different caps — 10% of basic+DA in the old regime, 14% in the new. Contribution above
  the cap stays taxable, so it must enter gross salary rather than being netted off
  invisibly. Supply it via `employer_nps_contribution` only; do NOT also list it as a
  salary component or it will be counted twice.
- Multiple employers (a job change mid-year) are summed independently; each carries its
  own basic+DA figure, so percentage caps are applied per employer as the statute
  requires rather than against a blended annual basic.
"""

from dataclasses import dataclass, field

from .models import SalaryIncome
from .rules.base import RegimeRules


@dataclass(frozen=True)
class SalaryResult:
    gross_salary: int
    hra_exemption: int
    other_exemptions: int
    standard_deduction: int
    professional_tax: int
    net_salary: int
    employer_nps_deduction: int
    notes: list[str] = field(default_factory=list)


def hra_exemption(salary: SalaryIncome) -> tuple[int, list[str]]:
    notes: list[str] = []
    total_hra_received = sum(c.annual_amount for c in salary.components if c.is_hra)
    if total_hra_received == 0 or not salary.rent_periods:
        return 0, notes

    total_months = sum(p.months for p in salary.rent_periods)
    if total_months == 0:
        return 0, notes
    if total_months != 12:
        notes.append(
            f"Rent periods cover {total_months} month(s), not 12. HRA exemption was computed "
            "only for the months supplied — verify this is intentional."
        )

    monthly_basic = salary.basic_plus_da_annual / 12
    monthly_hra = total_hra_received / 12

    exemption = 0.0
    for period in salary.rent_periods:
        period_basic = monthly_basic * period.months
        period_hra = monthly_hra * period.months
        period_rent = period.monthly_rent * period.months
        pct = 0.50 if period.is_metro else 0.40
        exemption += min(
            period_hra,
            max(0, period_rent - 0.10 * period_basic),
            pct * period_basic,
        )

    return round(min(exemption, total_hra_received)), notes


def other_exempt_allowances(salary: SalaryIncome) -> int:
    """s.10(14) exemptions on non-HRA components (LTA, conveyance, meal vouchers)."""
    return sum(c.section_10_14_exempt_amount for c in salary.components if not c.is_hra)


def employer_nps_deduction(salary: SalaryIncome, cap_pct: float) -> int:
    """80CCD(2), capped at cap_pct of basic+DA for this employer."""
    return min(salary.employer_nps_contribution, round(cap_pct * salary.basic_plus_da_annual))


def compute_salary(salaries: list[SalaryIncome], regime_rules: RegimeRules) -> SalaryResult:
    gross = 0
    hra_total = 0
    other_total = 0
    prof_tax_total = 0
    nps_total = 0
    notes: list[str] = []

    for salary in salaries:
        gross += salary.gross_taxable + salary.employer_nps_contribution
        if regime_rules.allows_hra_and_10_14:
            exempt, hra_notes = hra_exemption(salary)
            hra_total += exempt
            other_total += other_exempt_allowances(salary)
            notes.extend(hra_notes)
        if regime_rules.allows_professional_tax:
            prof_tax_total += salary.professional_tax_paid
        nps_total += employer_nps_deduction(salary, regime_rules.max_80ccd2_pct_of_salary)

    if not regime_rules.allows_hra_and_10_14:
        claimed = sum(
            (hra_exemption(s)[0] + other_exempt_allowances(s)) for s in salaries
        )
        if claimed > 0:
            notes.append(
                f"HRA and s.10(14) allowance exemptions worth {claimed:,} are not available "
                "under the new regime (s.115BAC) and have been disallowed."
            )
    if not regime_rules.allows_professional_tax:
        claimed_pt = sum(s.professional_tax_paid for s in salaries)
        if claimed_pt > 0:
            notes.append(
                f"Professional tax of {claimed_pt:,} (s.16(iii)) is not deductible under the "
                "new regime and has been disallowed."
            )

    after_exemptions = max(0, gross - hra_total - other_total)
    # s.16 deductions cannot take salary income below zero.
    section_16 = min(after_exemptions, regime_rules.standard_deduction + prof_tax_total)
    standard = min(after_exemptions, regime_rules.standard_deduction)
    prof_tax_applied = section_16 - standard

    return SalaryResult(
        gross_salary=gross,
        hra_exemption=hra_total,
        other_exemptions=other_total,
        standard_deduction=standard,
        professional_tax=prof_tax_applied,
        net_salary=after_exemptions - section_16,
        employer_nps_deduction=nps_total,
        notes=notes,
    )
