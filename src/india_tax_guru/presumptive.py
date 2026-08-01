"""Presumptive taxation of business and professional income — s.44AD and s.44ADA.

Edge cases handled:
- **The 6% rate is a split, not an alternative.** The proviso to s.44AD(1) substitutes 6%
  for 8% only "in respect of the AMOUNT of total turnover or gross receipts WHICH IS
  RECEIVED" by account-payee cheque, account-payee draft, ECS or another prescribed
  electronic mode. Presumptive income is therefore 6% of the digitally-received turnover
  PLUS 8% of everything else, not 6% of the whole where some threshold is met.
- The deadline for that receipt is unusually generous: money collected after year end but
  **before the s.139(1) due date** still earns the 6% rate. Turnover still unreceived at
  that date falls back to 8%.
- A cheque or bank draft that is **not account payee** does not qualify for 6%, and is
  additionally *deemed to be cash* when testing the enhanced turnover threshold.
- The turnover cap lives inside the DEFINITION of "eligible business". Breaching it does
  not cap the relief — it removes s.44AD altogether, which is why this module raises
  rather than silently returning a capped figure.
- The enhanced threshold (3 crore / 75 lakh) turns on **cash receipts** not exceeding 5%
  of turnover, tested against total turnover.
- s.44AD(4)'s five-year lock-in requires a s.44AD declaration **in an earlier year**. A
  taxpayer who never opted in and simply declares a thin profit is not caught by it at
  all — a distinction commentary routinely blurs, so it is modelled explicitly.
- Declaring below the presumptive rate triggers books under s.44AA and audit under s.44AB
  only where total income also exceeds the maximum amount not chargeable to tax, which is
  regime- and year-dependent rather than a fixed figure.
- Advance tax: s.211(1)(b) puts a presumptive assessee on a SINGLE instalment due 15 March
  at 100%, not the usual four. The s.234C consequence for missing it is a one-time 1%, not
  1% per month — so the ordinary four-checkpoint schedule must not be applied to them.

Not modelled: LLPs (expressly excluded from s.44AD), s.44AE goods carriage, and the
interaction with a tax-audit report, which is a compliance artefact rather than a figure.
"""

from dataclasses import dataclass, field

from .models import AssesseeType

#: Professions within s.44AA(1), which alone may use s.44ADA.
SECTION_44ADA_PROFESSIONS = frozenset(
    {
        "legal",
        "medical",
        "engineering",
        "architectural",
        "accountancy",
        "technical_consultancy",
        "interior_decoration",
        "authorised_representative",
        "film_artist",
        "company_secretary",
        "information_technology",
    }
)

#: Businesses and receipt types that s.44AD(6) and the eligible-business definition bar.
SECTION_44AD_EXCLUDED = frozenset(
    {
        "profession_44aa_1",  # covered by s.44ADA instead
        "commission_or_brokerage",
        "agency_business",
        "goods_carriage",  # s.44AE territory
    }
)


class PresumptiveIneligible(ValueError):
    """Raised where the taxpayer cannot use the presumptive section at all."""


@dataclass(frozen=True)
class PresumptiveRules:
    """Per-assessment-year presumptive parameters. Identical across AY 2025-26 and
    AY 2026-27 — Finance Act 2023 set these and nothing since has moved them."""

    section_44ad_rate_cash: float = 0.08
    section_44ad_rate_digital: float = 0.06
    section_44ad_turnover_cap: int = 20_000_000
    section_44ad_turnover_cap_enhanced: int = 30_000_000
    section_44ada_rate: float = 0.50
    section_44ada_receipts_cap: int = 5_000_000
    section_44ada_receipts_cap_enhanced: int = 7_500_000
    #: Cash receipts must be within this fraction of turnover for the enhanced cap.
    enhanced_cap_cash_fraction: float = 0.05


PRESUMPTIVE_RULES = PresumptiveRules()


@dataclass(frozen=True)
class PresumptiveResult:
    section: str  # "44AD" or "44ADA"
    turnover: int
    presumptive_income: int
    declared_income: int  # what the taxpayer actually declares
    turnover_cap_applied: int
    books_required: bool
    audit_required: bool
    single_advance_tax_instalment: bool
    notes: list[str] = field(default_factory=list)


def _assert_eligible_assessee(assessee_type: AssesseeType) -> None:
    if assessee_type == AssesseeType.LLP:
        raise PresumptiveIneligible(
            "An LLP is excluded from s.44AD by name in Explanation (a), which admits only "
            "a resident individual, HUF or partnership firm."
        )
    if assessee_type not in (AssesseeType.INDIVIDUAL, AssesseeType.HUF, AssesseeType.FIRM):
        raise PresumptiveIneligible(
            f"{assessee_type!s} is not an eligible assessee under s.44AD — the section "
            "admits only a resident individual, HUF or partnership firm (not an LLP)."
        )


def _assert_eligible_assessee_44ada(assessee_type: AssesseeType) -> None:
    """s.44ADA is NARROWER than s.44AD: individual or partnership firm only.

    Finance Act 2021 rewrote the opening words to "an assessee, being an individual
    or a partnership firm other than a limited liability partnership" — an HUF, which
    s.44AD does admit, has been outside s.44ADA since AY 2021-22. Reusing the 44AD
    test here would hand an HUF-run profession the 50% presumptive rate it lost.
    """
    if assessee_type not in (AssesseeType.INDIVIDUAL, AssesseeType.FIRM):
        detail = (
            "an HUF was eligible only up to AY 2020-21; Finance Act 2021 confined the "
            "section to a resident individual or partnership firm (not an LLP)"
            if assessee_type == AssesseeType.HUF
            else "the section admits only a resident individual or a partnership firm "
            "other than an LLP"
        )
        raise PresumptiveIneligible(
            f"{assessee_type!s} is not an eligible assessee under s.44ADA — {detail}."
        )


def compute_44ad(
    turnover: int,
    digital_receipts: int,
    cash_receipts: int,
    *,
    assessee_type: AssesseeType = AssesseeType.INDIVIDUAL,
    is_resident: bool = True,
    business_kind: str = "general",
    declared_income: int | None = None,
    opted_in_an_earlier_year: bool = False,
    basic_exemption_limit: int = 400_000,
    rules: PresumptiveRules = PRESUMPTIVE_RULES,
) -> PresumptiveResult:
    """Presumptive business income under s.44AD.

    `digital_receipts` is turnover received by account-payee cheque or draft, ECS, or
    another prescribed electronic mode, whether during the year or before the s.139(1)
    due date. `cash_receipts` includes non-account-payee cheques and drafts, which the
    second proviso deems to be cash for the enhanced-threshold test.

    For a GST-registered filer, `turnover` (and the receipt split) must be EXCLUSIVE
    of GST: tax collected on outward supplies is a liability held for the government,
    not turnover, and feeding a GST-inclusive figure both overstates presumptive
    income and can flip the cap test near the threshold. Reconcile against the GSTR
    figures with `gst.reconcile_gst_turnover` before computing.

    `basic_exemption_limit` defaults to 4,00,000 — the NEW-regime figure for
    AY 2026-27. It is year- and regime-dependent; pass the actual limit for the
    taxpayer's year and regime (the old regime's is 2,50,000) or the books/audit
    consequence of declaring below the presumptive rate may be mis-stated.
    """
    _assert_eligible_assessee(assessee_type)
    if not is_resident:
        raise PresumptiveIneligible(
            "s.44AD is available only to a RESIDENT individual, HUF or firm."
        )
    if business_kind in SECTION_44AD_EXCLUDED:
        raise PresumptiveIneligible(
            f"s.44AD(6) and the eligible-business definition exclude {business_kind!r}. "
            "Commission or brokerage income, agency business, a s.44AA(1) profession and "
            "goods-carriage plying are each outside the section."
        )

    notes: list[str] = []
    cash_fraction = (cash_receipts / turnover) if turnover else 0.0
    enhanced = cash_fraction <= rules.enhanced_cap_cash_fraction
    cap = (
        rules.section_44ad_turnover_cap_enhanced
        if enhanced
        else rules.section_44ad_turnover_cap
    )
    if enhanced and turnover > rules.section_44ad_turnover_cap:
        notes.append(
            f"Enhanced turnover cap of {cap:,} applied: cash receipts are "
            f"{cash_fraction:.2%} of turnover, within the 5% condition."
        )
    if turnover > cap:
        raise PresumptiveIneligible(
            f"Turnover of {turnover:,} exceeds the s.44AD cap of {cap:,}. The cap sits "
            "inside the definition of 'eligible business', so breaching it removes the "
            "section entirely rather than capping the relief — compute actual profits."
        )

    # The 6% rate applies to the digitally-received slice only; everything else bears 8%.
    digital = min(max(0, digital_receipts), turnover)
    remainder = turnover - digital
    presumptive = round(
        digital * rules.section_44ad_rate_digital + remainder * rules.section_44ad_rate_cash
    )
    if digital and remainder:
        notes.append(
            f"Split rate applied: 6% on {digital:,} received through qualifying modes and "
            f"8% on the remaining {remainder:,}. The 6% rate is not an alternative rate on "
            "the whole turnover."
        )

    declared = presumptive if declared_income is None else declared_income
    books = audit = False
    if declared < presumptive:
        if not opted_in_an_earlier_year:
            notes.append(
                "Declaring below the presumptive rate without having opted into s.44AD in "
                "an earlier year does not engage s.44AD(4). The ordinary s.44AA(2) and "
                "s.44AB(a) tests apply instead."
            )
        elif declared > basic_exemption_limit:
            books = audit = True
            notes.append(
                "s.44AD(4) is engaged: a lower figure is declared after opting into the "
                "section in an earlier year, and total income exceeds the maximum amount "
                "not chargeable to tax. Books under s.44AA and audit under s.44AB(e) "
                "follow, and s.44AD is barred for the five subsequent assessment years."
            )
        else:
            notes.append(
                "A lower figure is declared, but total income is within the maximum amount "
                f"not chargeable to tax ({basic_exemption_limit:,}), so no books or audit "
                "obligation arises."
            )

    notes.append(
        "Advance tax for a presumptive assessee is a single instalment of 100% due "
        "15 March (s.211(1)(b)); the usual four-instalment schedule does not apply, and "
        "the s.234C consequence for a shortfall is a one-time 1%."
    )

    return PresumptiveResult(
        section="44AD",
        turnover=turnover,
        presumptive_income=presumptive,
        declared_income=declared,
        turnover_cap_applied=cap,
        books_required=books,
        audit_required=audit,
        single_advance_tax_instalment=True,
        notes=notes,
    )


def compute_44ada(
    gross_receipts: int,
    cash_receipts: int,
    *,
    profession: str,
    assessee_type: AssesseeType = AssesseeType.INDIVIDUAL,
    is_resident: bool = True,
    declared_income: int | None = None,
    basic_exemption_limit: int = 400_000,
    rules: PresumptiveRules = PRESUMPTIVE_RULES,
) -> PresumptiveResult:
    """Presumptive professional income under s.44ADA — a flat 50% of gross receipts.

    Unlike s.44AD there is no split rate and no five-year lock-in; the cash-receipt test
    governs only the enhanced receipts cap.

    As with s.44AD, `gross_receipts` must be EXCLUSIVE of GST for a registered
    professional — at 50%, counting the tax collected as receipts overstates income
    by half the GST component. See `gst.reconcile_gst_turnover`.

    `basic_exemption_limit` is year- and regime-dependent, as on `compute_44ad`.
    """
    _assert_eligible_assessee_44ada(assessee_type)
    if not is_resident:
        raise PresumptiveIneligible("s.44ADA is available only to a RESIDENT assessee.")
    if profession not in SECTION_44ADA_PROFESSIONS:
        raise PresumptiveIneligible(
            f"{profession!r} is not a profession within s.44AA(1), so s.44ADA does not "
            f"apply. Recognised professions: {', '.join(sorted(SECTION_44ADA_PROFESSIONS))}."
        )

    notes: list[str] = []
    cash_fraction = (cash_receipts / gross_receipts) if gross_receipts else 0.0
    enhanced = cash_fraction <= rules.enhanced_cap_cash_fraction
    cap = (
        rules.section_44ada_receipts_cap_enhanced
        if enhanced
        else rules.section_44ada_receipts_cap
    )
    if enhanced and gross_receipts > rules.section_44ada_receipts_cap:
        notes.append(
            f"Enhanced receipts cap of {cap:,} applied: cash receipts are "
            f"{cash_fraction:.2%} of gross receipts, within the 5% condition."
        )
    if gross_receipts > cap:
        raise PresumptiveIneligible(
            f"Gross receipts of {gross_receipts:,} exceed the s.44ADA cap of {cap:,}; the "
            "section is unavailable and actual profits must be computed."
        )

    presumptive = round(gross_receipts * rules.section_44ada_rate)
    declared = presumptive if declared_income is None else declared_income

    books = audit = False
    if declared < presumptive and declared > basic_exemption_limit:
        books = audit = True
        notes.append(
            "Declaring below 50% of gross receipts while total income exceeds the maximum "
            "amount not chargeable to tax engages books under s.44AA and audit under "
            "s.44AB(d)."
        )

    notes.append(
        "Advance tax for a presumptive assessee is a single instalment of 100% due "
        "15 March (s.211(1)(b)); the s.234C consequence for a shortfall is a one-time 1%."
    )

    return PresumptiveResult(
        section="44ADA",
        turnover=gross_receipts,
        presumptive_income=presumptive,
        declared_income=declared,
        turnover_cap_applied=cap,
        books_required=books,
        audit_required=audit,
        single_advance_tax_instalment=True,
        notes=notes,
    )


def presumptive_234c_interest(assessed_tax: int, paid_by_15_march: int) -> tuple[int, str]:
    """s.234C for a presumptive assessee: a one-time 1% on the shortfall, not per month."""
    shortfall = max(0, assessed_tax - paid_by_15_march)
    base = (shortfall // 100) * 100  # Rule 119A
    interest = round(base * 0.01)
    if interest == 0:
        return 0, "Advance tax met in full by 15 March; no s.234C interest."
    return interest, (
        f"s.234C: shortfall of {shortfall:,} against the single 15 March instalment. "
        f"Interest is a one-time 1% ({interest:,}), not 1% per month — a presumptive "
        "assessee has one instalment, so there are no earlier checkpoints to run from."
    )
