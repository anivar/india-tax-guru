"""CLI entry point. Reads a JSON profile file (see docs/profile_schema.md) and
runs regime comparison, or a CTC-optimization JSON input.
"""

import json
from dataclasses import asdict

import click

from .models import (
    AgeBand,
    CapitalGainLot,
    Deductions,
    HouseProperty,
    OtherIncome,
    RentPeriod,
    SalaryComponent,
    SalaryIncome,
    TaxpayerProfile,
)
from .regime import compare_regimes
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
    house_properties = [HouseProperty(**h) for h in d.get("house_properties", [])]
    capital_gains = [CapitalGainLot(**g) for g in d.get("capital_gains", [])]
    return TaxpayerProfile(
        assessment_year=d["assessment_year"],
        age_band=AgeBand(d.get("age_band", "below_60")),
        salaries=salaries,
        house_properties=house_properties,
        capital_gains=capital_gains,
        other_income=OtherIncome(**d.get("other_income", {})),
        deductions=Deductions(**d.get("deductions", {})),
    )


@click.group()
def main():
    """india-tax-guru: India income-tax planning and filing support."""


@main.command("years")
def years_cmd():
    """List supported assessment years."""
    for y in available_years():
        click.echo(y)


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
    for r in (result.old, result.new):
        click.echo(f"\n[{r.regime.upper()} regime]")
        click.echo(f"  Taxable salary:        {r.taxable_salary:>12,}")
        click.echo(f"  House property net:    {r.house_property_net:>12,}")
        click.echo(f"  Other income:          {r.other_income:>12,}")
        click.echo(f"  Deductions claimed:    {r.deductions_claimed:>12,}")
        click.echo(f"  Slab taxable income:   {r.slab_taxable_income:>12,}")
        click.echo(f"  Tax on slab income:    {r.tax_on_slab_income:>12,}")
        click.echo(f"  Tax on capital gains:  {r.tax_on_capital_gains:>12,}")
        click.echo(f"  87A rebate applied:    {r.rebate_87a_applied:>12,}")
        click.echo(f"  Surcharge:             {r.surcharge:>12,}")
        click.echo(f"  Cess:                  {r.cess:>12,}")
        click.echo(f"  TOTAL TAX PAYABLE:     {r.total_tax_payable:>12,}")
        for n in r.deduction_notes:
            click.echo(f"  note: {n}")

    click.echo(f"\nRecommended: {result.recommended.upper()} regime (saves {result.savings:,})")


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
    candidates = optimize_ctc_split(inp, rules)
    for c in candidates[:top]:
        click.echo(json.dumps(asdict(c), indent=2))
        click.echo("---")


if __name__ == "__main__":
    main()
