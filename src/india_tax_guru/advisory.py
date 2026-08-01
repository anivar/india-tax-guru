"""Expert salary-structure advice: what to change, and what each change is worth.

Every rupee figure here is produced by building the counterfactual profile and running
it through the SAME engine that produced the baseline, then taking the difference. No
saving is ever estimated by multiplying something by a marginal rate — that is how a
recommendation drifts out of agreement with the computation meant to justify it.

Each lever is measured INDIVIDUALLY against the baseline, so its figure answers "what is
this one change worth on its own". Those figures are NOT additive: filling 80C and
80CCD(1B) both reduce the same taxable income, and doing both saves less than the sum.
Levers are therefore also applied cumulatively to produce `combined_saving`, which is
the number to quote to a taxpayer.

Edge cases handled:
- Advice is generated against the regime the engine actually recommends, not whichever
  regime the taxpayer is currently in. Telling someone who belongs in the new regime to
  top up their 80C would be actively harmful.
- Employer NPS sits inside CTC, so routing salary into it converts spendable cash into a
  contribution locked until retirement. Flagged rather than presented as free money.
- Raising HRA helps only up to the amount fully exempt for the rent actually paid; past
  that it is taxed exactly like the special allowance it came from. The lever targets
  the exemption ceiling and never overshoots it.
- Levers needing payroll changes are marked `requires_employer_action`, because a
  taxpayer acting alone in March cannot use them.
- Levers compose: the NPS and HRA levers both draw from the same flexible component, so
  the cumulative pass re-derives each lever from the already-mutated profile instead of
  from the baseline.
"""

from collections.abc import Callable
from dataclasses import dataclass, field, replace

from .compliance import regime_choice_guidance
from .models import Regime, SalaryComponent, SalaryIncome, TaxpayerProfile
from .regime import compare_regimes, compute_regime
from .rules.base import AssessmentYearRules, RegimeRules


@dataclass(frozen=True)
class Recommendation:
    action: str
    rationale: str
    annual_tax_saving: int
    category: str  # regime | deduction | allocation | compliance
    requires_employer_action: bool = False
    reduces_take_home_cash: bool = False


@dataclass(frozen=True)
class SalaryAdvice:
    recommended_regime: str
    baseline_tax: int  # tax in the recommended regime, before any change
    combined_saving: int  # every recommended lever applied together
    optimised_tax: int
    recommendations: list[Recommendation] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


#: A lever maps a profile to (mutated profile, recommendation), or None if inapplicable.
Lever = Callable[
    [TaxpayerProfile, AssessmentYearRules, RegimeRules],
    tuple[TaxpayerProfile, Recommendation] | None,
]


def _tax(profile: TaxpayerProfile, rules: AssessmentYearRules, regime: str) -> int:
    return compute_regime(profile, rules, regime).total_tax_liability


def _with_salary(profile: TaxpayerProfile, salary: SalaryIncome) -> TaxpayerProfile:
    return replace(profile, salaries=[salary, *profile.salaries[1:]])


def _flexible_component(salary: SalaryIncome) -> SalaryComponent | None:
    """The component a restructuring can draw from: biggest taxable, non-basic, non-HRA."""
    candidates = [
        c
        for c in salary.components
        if c.taxable
        and not c.is_hra
        and c.section_10_14_exempt_amount == 0
        and "basic" not in c.name.lower()
    ]
    return max(candidates, key=lambda c: c.annual_amount, default=None)


def _annual_rent(salary: SalaryIncome) -> int:
    return sum(p.monthly_rent * p.months for p in salary.rent_periods)


def _lever_employer_nps(profile, rules, regime_rules):
    if not profile.salaries:
        return None
    salary = profile.salaries[0]
    cap = round(regime_rules.max_80ccd2_pct_of_salary * salary.basic_plus_da_annual)
    headroom = cap - salary.employer_nps_contribution
    if headroom <= 0:
        return None
    flexible = _flexible_component(salary)
    if flexible is None or flexible.annual_amount < headroom:
        return None

    components = [
        replace(c, annual_amount=c.annual_amount - headroom) if c is flexible else c
        for c in salary.components
    ]
    mutated = replace(salary, components=components, employer_nps_contribution=cap)
    return _with_salary(profile, mutated), Recommendation(
        action=(
            f"Route {headroom:,} of {flexible.name} into employer NPS under 80CCD(2), "
            f"taking the contribution to {cap:,}"
        ),
        rationale=(
            f"80CCD(2) is deductible up to {regime_rules.max_80ccd2_pct_of_salary:.0%} of "
            "basic+DA and, unlike 80C, it survives in the new regime — often the only "
            "structural lever left there. The money is locked until retirement."
        ),
        annual_tax_saving=0,
        category="allocation",
        requires_employer_action=True,
        reduces_take_home_cash=True,
    )


def _lever_hra(profile, rules, regime_rules):
    if not profile.salaries or not regime_rules.allows_hra_and_10_14:
        return None
    salary = profile.salaries[0]
    rent = _annual_rent(salary)
    if rent <= 0:
        return None

    metro = any(p.is_metro for p in salary.rent_periods)
    basic = salary.basic_plus_da_annual
    ceiling = max(
        0,
        min(round((0.50 if metro else 0.40) * basic), rent - round(0.10 * basic)),
    )
    current_hra = sum(c.annual_amount for c in salary.components if c.is_hra)
    shortfall = ceiling - current_hra
    if shortfall <= 0:
        return None

    flexible = _flexible_component(salary)
    if flexible is None or flexible.annual_amount < shortfall:
        return None

    components, hra_seen = [], False
    for c in salary.components:
        if c.is_hra:
            components.append(replace(c, annual_amount=c.annual_amount + shortfall))
            hra_seen = True
        elif c is flexible:
            components.append(replace(c, annual_amount=c.annual_amount - shortfall))
        else:
            components.append(c)
    if not hra_seen:
        components.append(SalaryComponent(name="HRA", annual_amount=shortfall, is_hra=True))

    return _with_salary(profile, replace(salary, components=components)), Recommendation(
        action=f"Reclassify {shortfall:,} of {flexible.name} as HRA, taking HRA to {ceiling:,}",
        rationale=(
            f"On rent of {rent:,} against basic of {basic:,}, HRA is fully exempt up to "
            f"{ceiling:,} — the least of HRA received, rent less 10% of basic, and "
            f"{'50%' if metro else '40%'} of basic. Anything beyond that is taxed exactly "
            "like the allowance it came from, so this is the entire benefit available."
        ),
        annual_tax_saving=0,
        category="allocation",
        requires_employer_action=True,
    )


def _deduction_lever(field_name: str, cap_attr: str, label: str, why: str) -> Lever:
    def lever(profile, rules, regime_rules):
        if field_name not in regime_rules.allowed_deductions:
            return None
        cap = getattr(rules, cap_attr)
        current = getattr(profile.deductions, field_name)
        if current >= cap:
            return None
        mutated = replace(
            profile, deductions=replace(profile.deductions, **{field_name: cap})
        )
        return mutated, Recommendation(
            action=f"Use the remaining {cap - current:,} of {label} headroom",
            rationale=why,
            annual_tax_saving=0,
            category="deduction",
        )

    return lever


LEVERS: list[Lever] = [
    _lever_employer_nps,
    _lever_hra,
    _deduction_lever(
        "section_80c",
        "section_80c_cap",
        "80C",
        "EPF, ELSS, PPF, life-insurance premium, children's tuition fees and home-loan "
        "principal repayment all share this one limit — check what is already counted "
        "before investing more.",
    ),
    _deduction_lever(
        "section_80ccd_1b",
        "section_80ccd_1b_cap",
        "80CCD(1B)",
        "An additional self-contribution to NPS, over and above the 80C limit.",
    ),
    _deduction_lever(
        "section_80d_self_family",
        "section_80d_self_family_cap",
        "80D (self and family)",
        "Health-insurance premium for self, spouse and dependent children. A preventive "
        "health check-up counts within this limit.",
    ),
]


def analyse_salary_structure(
    profile: TaxpayerProfile,
    rules: AssessmentYearRules,
    has_business_or_professional_income: bool = False,
) -> SalaryAdvice:
    """Advise on structure and regime.

    `has_business_or_professional_income` drives the Form 10-IEA guidance only. It
    defaults to False because this engine models ITR-1/ITR-2 profiles, and telling a
    salaried taxpayer to file Form 10-IEA would make them file a form the law does not
    require of them.
    """
    comparison = compare_regimes(profile, rules)
    regime = comparison.recommended
    regime_rules = rules.old_regime if regime == str(Regime.OLD) else rules.new_regime
    baseline = _tax(profile, rules, regime)

    recommendations: list[Recommendation] = []
    warnings: list[str] = []

    if comparison.savings > 0:
        other = "old" if regime == str(Regime.NEW) else "new"
        recommendations.append(
            Recommendation(
                action=f"File under the {regime.upper()} regime",
                rationale=(
                    f"On this income and deduction profile the {regime} regime costs "
                    f"{comparison.savings:,} less than the {other} regime."
                ),
                annual_tax_saving=comparison.savings,
                category="regime",
            )
        )

    if profile.salaries:
        salary = profile.salaries[0]
        hra_paid = sum(c.annual_amount for c in salary.components if c.is_hra)
        if hra_paid > 0 and _annual_rent(salary) == 0:
            warnings.append(
                f"{hra_paid:,} is paid as HRA but no rent is recorded, so none of it is "
                "exempt. Record the rent actually paid, or treat this as ordinary salary."
            )

    # Individually measured, then applied cumulatively — each cumulative step re-derives
    # the lever from the already-mutated profile, since levers share the same source
    # component and would otherwise double-spend it.
    cumulative = profile
    for lever in LEVERS:
        outcome = lever(profile, rules, regime_rules)
        if outcome is None:
            continue
        candidate, recommendation = outcome
        saving = baseline - _tax(candidate, rules, regime)
        if saving <= 0:
            continue
        recommendations.append(replace(recommendation, annual_tax_saving=saving))

        cumulative_outcome = lever(cumulative, rules, regime_rules)
        if cumulative_outcome is not None:
            cumulative = cumulative_outcome[0]

    guidance = regime_choice_guidance(
        profile.assessment_year,
        regime,
        has_business_or_professional_income=has_business_or_professional_income,
    )
    if guidance is not None:
        recommendations.append(
            Recommendation(
                action=guidance.headline,
                rationale=guidance.detail,
                annual_tax_saving=0,
                category="compliance",
            )
        )

    optimised = _tax(cumulative, rules, regime)
    return SalaryAdvice(
        recommended_regime=regime,
        baseline_tax=baseline,
        combined_saving=max(0, baseline - optimised),
        optimised_tax=optimised,
        recommendations=recommendations,
        warnings=warnings,
    )
