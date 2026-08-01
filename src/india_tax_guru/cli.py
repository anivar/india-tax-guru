"""CLI entry point. Reads a JSON profile (see docs/profile_schema.md) and runs a
regime comparison, or a CTC-optimization input.
"""

import json
from dataclasses import asdict

import click

from .advisory import analyse_salary_structure
from .models import (
    AgeBand,
    AssesseeType,
    CapitalGainLot,
    Deductions,
    HouseProperty,
    OtherIncome,
    RentPeriod,
    SalaryComponent,
    SalaryIncome,
    TaxesPaid,
    TaxpayerProfile,
)
from .regime import RegimeResult, compare_regimes
from .restructuring import CTCOptimizationInput, optimize_ctc_split
from .rules import available_years, get_rules


def _profile_from_dict(d: dict) -> TaxpayerProfile:
    salaries = [
        SalaryIncome(
            employer_name=s["employer_name"],
            components=[SalaryComponent(**c) for c in s.get("components", [])],
            basic_plus_da_annual=s.get("basic_plus_da_annual", 0),
            rent_periods=[RentPeriod(**r) for r in s.get("rent_periods", [])],
            professional_tax_paid=s.get("professional_tax_paid", 0),
            employer_nps_contribution=s.get("employer_nps_contribution", 0),
        )
        for s in d.get("salaries", [])
    ]
    return TaxpayerProfile(
        assessment_year=d["assessment_year"],
        age_band=AgeBand(d.get("age_band", "below_60")),
        assessee_type=AssesseeType(d.get("assessee_type", "individual")),
        is_resident=d.get("is_resident", True),
        salaries=salaries,
        house_properties=[HouseProperty(**h) for h in d.get("house_properties", [])],
        capital_gains=[CapitalGainLot(**g) for g in d.get("capital_gains", [])],
        business_income=d.get("business_income", 0),
        other_income=OtherIncome(**d.get("other_income", {})),
        deductions=Deductions(**d.get("deductions", {})),
        taxes_paid=TaxesPaid(**d.get("taxes_paid", {})),
    )


def _print_regime(r: RegimeResult) -> None:
    click.echo(f"\n[{r.regime.upper()} regime]")
    rows = [
        ("Gross salary", r.gross_salary),
        ("Net salary (after s.16)", r.net_salary),
        ("House property", r.house_property),
        ("Other income", r.other_income),
        ("Business income", r.business_income),
        ("Capital gains (slab rate)", r.slab_rate_capital_gains),
        ("Gross total income", r.gross_total_income),
        ("Deductions claimed", -r.deductions_claimed),
        ("Capital gains (special rate)", r.special_rate_capital_gains),
        ("TOTAL INCOME", r.total_income),
        ("", None),
        ("Tax on slab income", r.tax_on_slab_income),
        ("Less: s.87A rebate", -r.rebate_87a),
        ("Tax on special-rate income", r.tax_on_special_rate_income),
        ("Surcharge", r.surcharge),
        ("Cess", r.cess),
        ("TOTAL TAX LIABILITY", r.total_tax_liability),
    ]
    if r.interest_234b or r.interest_234c:
        rows += [("Interest u/s 234B", r.interest_234b), ("Interest u/s 234C", r.interest_234c)]
    rows += [("Less: taxes already paid", -r.taxes_already_paid)]
    if r.refund_due:
        rows.append(("REFUND DUE", r.refund_due))
    else:
        rows.append(("BALANCE PAYABLE", r.balance_payable))

    for label, value in rows:
        if value is None:
            click.echo()
            continue
        click.echo(f"  {label:<30}{value:>14,}")

    for note in r.notes:
        click.echo(f"  note: {note}")


@click.group()
def main():
    """india-tax-guru: India income-tax planning and filing support."""


@main.command("years")
def years_cmd():
    """List supported assessment years."""
    for year in available_years():
        click.echo(year)


@main.command("compare")
@click.argument("profile_json", type=click.Path(exists=True))
def compare_cmd(profile_json: str):
    """Compare old vs new regime tax for a taxpayer profile JSON file."""
    with open(profile_json) as f:
        data = json.load(f)
    profile = _profile_from_dict(data)
    rules = get_rules(profile.assessment_year)
    result = compare_regimes(profile, rules)

    click.echo(f"AY {profile.assessment_year}")
    _print_regime(result.old)
    _print_regime(result.new)
    if result.savings:
        click.echo(
            f"\nRecommended: {result.recommended.upper()} regime "
            f"(saves {result.savings:,})"
        )
    else:
        click.echo(
            f"\nRecommended: {result.recommended.upper()} regime "
            "(identical tax either way; the new regime is the statutory default and "
            "needs no opt-out filing)"
        )


@main.command("advise")
@click.argument("profile_json", type=click.Path(exists=True))
def advise_cmd(profile_json: str):
    """Expert salary-structure advice: what to change and what each change is worth."""
    with open(profile_json) as f:
        data = json.load(f)
    profile = _profile_from_dict(data)
    rules = get_rules(profile.assessment_year)
    advice = analyse_salary_structure(profile, rules)

    click.echo(f"AY {profile.assessment_year}")
    click.echo(f"\nRecommended regime : {advice.recommended_regime.upper()}")
    click.echo(f"Tax as things stand: {advice.baseline_tax:>14,}")
    click.echo(f"Tax if all applied : {advice.optimised_tax:>14,}")
    click.echo(f"Total opportunity  : {advice.combined_saving:>14,}")

    if advice.recommendations:
        click.echo("\nRecommendations (savings are measured individually and do not add up):")
        for rec in sorted(advice.recommendations, key=lambda r: -r.annual_tax_saving):
            flags = []
            if rec.requires_employer_action:
                flags.append("needs employer")
            if rec.reduces_take_home_cash:
                flags.append("locks up cash")
            suffix = f"  [{', '.join(flags)}]" if flags else ""
            click.echo(f"\n  [{rec.category}] {rec.action}{suffix}")
            if rec.annual_tax_saving:
                click.echo(f"      worth {rec.annual_tax_saving:,} a year")
            click.echo(f"      {rec.rationale}")

    for warning in advice.warnings:
        click.echo(f"\n  warning: {warning}")


@main.command("optimize-ctc")
@click.argument("ctc_json", type=click.Path(exists=True))
@click.option("--top", default=5, help="Show top N candidates")
def optimize_ctc_cmd(ctc_json: str, top: int):
    """Search CTC component splits to minimize tax / maximize take-home."""
    with open(ctc_json) as f:
        data = json.load(f)
    rules = get_rules(data["assessment_year"])
    inp = CTCOptimizationInput(
        annual_ctc=data["annual_ctc"],
        annual_rent=data.get("annual_rent", 0),
        is_metro=data.get("is_metro", False),
        age_band=AgeBand(data.get("age_band", "below_60")),
        other_deductions=Deductions(**data.get("other_deductions", {})),
        fixed_meal_voucher_exempt=data.get("fixed_meal_voucher_exempt", 26_400),
        fixed_lta_exempt=data.get("fixed_lta_exempt", 0),
    )
    for candidate in optimize_ctc_split(inp, rules)[:top]:
        click.echo(json.dumps(asdict(candidate), indent=2))
        click.echo("---")


if __name__ == "__main__":
    main()
