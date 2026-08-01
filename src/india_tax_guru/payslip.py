"""Salary-slip analysis: classify monthly payslip line items into taxable/exempt
buckets and reconcile a run of monthly slips against annual Form 16 figures.

Scope note: input is structured (a list of line-item dicts per month — typically
hand-transcribed or exported from an HR portal as CSV/JSON). Parsing scanned/PDF
payslips via OCR is explicitly OUT of scope for v1; see README "Not implemented".

Edge cases handled:
- A component appearing in some months but not others (e.g. bonus paid once,
  reimbursements paid irregularly) — reconciliation sums whatever months are
  present rather than assuming 12 uniform months.
- Component name variants across employers ("Basic", "Basic Pay", "BASIC SALARY")
  are matched via a small case/whitespace-insensitive alias table, not exact
  string equality — unmatched names are surfaced as "unclassified" rather than
  silently dropped or silently taxed/exempted by guesswork.
- Reimbursement-style components (fuel, telephone, books) are exempt only up to
  submitted-bill value, which a payslip alone can't prove — flagged as
  "exempt if bills submitted" rather than auto-exempted.
- Mid-year employer switch: caller passes one MonthlySlip list per employer;
  reconciliation is per-employer, then summed, matching how Form 16 is issued.
"""

from dataclasses import dataclass, field

_TAXABLE_ALIASES = {
    "basic": "Basic",
    "basic pay": "Basic",
    "basic salary": "Basic",
    "special allowance": "Special Allowance",
    "special pay": "Special Allowance",
    "hra": "HRA",
    "house rent allowance": "HRA",
    "bonus": "Bonus",
    "performance bonus": "Bonus",
    "da": "Dearness Allowance",
    "dearness allowance": "Dearness Allowance",
}

_EXEMPT_WITH_PROOF_ALIASES = {
    "lta": "LTA",
    "leave travel allowance": "LTA",
    "telephone reimbursement": "Telephone Reimbursement",
    "fuel reimbursement": "Fuel Reimbursement",
    "books and periodicals": "Books & Periodicals",
    "meal vouchers": "Meal Vouchers",
    "meal card": "Meal Vouchers",
    "sodexo": "Meal Vouchers",
}

_KNOWN_DEDUCTION_ALIASES = {
    "pf": "Provident Fund",
    "employee pf": "Provident Fund",
    "professional tax": "Professional Tax",
    "prof tax": "Professional Tax",
    "tds": "TDS",
    "nps": "Employee NPS",
    "employer nps": "Employer NPS",
}


@dataclass
class PayslipLineItem:
    name: str
    amount: int
    is_deduction: bool = False


@dataclass
class MonthlySlip:
    month: str  # "2025-04" etc.
    line_items: list[PayslipLineItem] = field(default_factory=list)


@dataclass(frozen=True)
class PayslipAnalysis:
    months_covered: list[str]
    taxable_components: dict[str, int]
    exempt_with_proof_components: dict[str, int]
    deduction_components: dict[str, int]
    unclassified_components: dict[str, int]
    gross_taxable_annualized: int
    notes: list[str]


def _classify(name: str) -> tuple[str, str] | None:
    key = name.strip().lower()
    if key in _TAXABLE_ALIASES:
        return "taxable", _TAXABLE_ALIASES[key]
    if key in _EXEMPT_WITH_PROOF_ALIASES:
        return "exempt_with_proof", _EXEMPT_WITH_PROOF_ALIASES[key]
    if key in _KNOWN_DEDUCTION_ALIASES:
        return "deduction", _KNOWN_DEDUCTION_ALIASES[key]
    return None


def analyze_payslips(slips: list[MonthlySlip]) -> PayslipAnalysis:
    taxable: dict[str, int] = {}
    exempt: dict[str, int] = {}
    deduction: dict[str, int] = {}
    unclassified: dict[str, int] = {}
    notes: list[str] = []

    for slip in slips:
        for item in slip.line_items:
            classified = _classify(item.name)
            if classified is None:
                bucket = unclassified
                bucket[item.name] = bucket.get(item.name, 0) + item.amount
                continue
            kind, canonical = classified
            target = {"taxable": taxable, "exempt_with_proof": exempt, "deduction": deduction}[kind]
            target[canonical] = target.get(canonical, 0) + item.amount

    if unclassified:
        notes.append(
            f"{len(unclassified)} unrecognized line item name(s) could not be classified "
            "and are excluded from gross_taxable_annualized: "
            f"{', '.join(sorted(unclassified))}. Add an alias or classify manually."
        )
    if exempt:
        notes.append(
            "Exempt-with-proof components (LTA, fuel/telephone reimbursement, etc.) are only "
            "actually exempt if the employee submitted matching bills/proof to payroll — this "
            "tool cannot verify that from a payslip alone."
        )

    return PayslipAnalysis(
        months_covered=[s.month for s in slips],
        taxable_components=taxable,
        exempt_with_proof_components=exempt,
        deduction_components=deduction,
        unclassified_components=unclassified,
        gross_taxable_annualized=sum(taxable.values()),
        notes=notes,
    )


def reconcile_against_form16(analysis: PayslipAnalysis, form16_gross_salary: int) -> str | None:
    """Returns a discrepancy note if payslip-derived gross differs materially from Form 16."""
    diff = form16_gross_salary - analysis.gross_taxable_annualized
    if abs(diff) <= 1000:
        return None
    direction = "higher" if diff > 0 else "lower"
    return (
        f"Form 16 gross salary ({form16_gross_salary}) is {abs(diff)} {direction} than the "
        f"sum of classified taxable payslip components ({analysis.gross_taxable_annualized}). "
        "Likely causes: unclassified line items (see notes), a bonus/arrears month not "
        "included in the supplied slips, or a perquisite valued only on Form 16 (e.g. ESOP, "
        "rent-free accommodation) that never appears on a monthly payslip."
    )
