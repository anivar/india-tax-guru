"""Core data models. All money values are in whole INR."""

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum


class Regime(StrEnum):
    OLD = "old"
    NEW = "new"


class AgeBand(StrEnum):
    BELOW_60 = "below_60"
    SENIOR_60_80 = "senior_60_80"
    SUPER_SENIOR_80_PLUS = "super_senior_80_plus"


class AssesseeType(StrEnum):
    """Class of person being assessed.

    INDIVIDUAL and HUF are implemented. The others are named rather than omitted so
    that supplying one produces a refusal instead of an individual's tax computed on
    a firm's or a company's figures — the reliefs differ enough that the answer would
    be wrong without anything looking wrong.
    """

    INDIVIDUAL = "individual"
    HUF = "huf"
    AOP_BOI = "aop_boi"
    FIRM = "firm"
    LLP = "llp"
    COMPANY = "company"


class UnsupportedAssesseeError(NotImplementedError):
    """Raised for an assessee class whose rules this engine does not implement."""


#: Why each unsupported class cannot borrow the individual computation.
_UNSUPPORTED_REASONS: dict[str, str] = {
    AssesseeType.AOP_BOI: (
        "An AOP or BOI is charged under its own paragraph of the Finance Act, with rules "
        "turning on whether the members' shares are determinate and on the members' own "
        "rates — not the individual slab structure."
    ),
    AssesseeType.FIRM: (
        "A firm is taxed at a flat 30% with its own surcharge threshold, and s.115BAC does "
        "not apply to it, so there is no old-versus-new regime choice to make."
    ),
    AssesseeType.LLP: (
        "An LLP is taxed as a firm at a flat rate, is outside s.115BAC entirely, and is "
        "also ineligible for presumptive taxation under s.44AD."
    ),
    AssesseeType.COMPANY: (
        "A company is outside s.115BAC altogether. It is charged at its own flat rates "
        "(with concessional regimes under s.115BAA and s.115BAB), is subject to minimum "
        "alternate tax under s.115JB, has a different surcharge structure, and files "
        "ITR-6. Essentially none of this engine applies."
    ),
}


def assert_supported(assessee_type: "AssesseeType") -> None:
    if assessee_type in (AssesseeType.INDIVIDUAL, AssesseeType.HUF):
        return
    reason = _UNSUPPORTED_REASONS.get(
        assessee_type, "This engine implements the individual and HUF computations only."
    )
    raise UnsupportedAssesseeError(
        f"assessee_type={assessee_type!s} is not supported. {reason} "
        "This engine covers INDIVIDUALS and HUFs filing ITR-1 through ITR-4."
    )


class AssetClass(StrEnum):
    """Capital asset classes, split by how they are TAXED rather than by what they are.

    `SPECIFIED_MF` exists because s.50AA deems gains on specified mutual funds (debt-
    oriented funds acquired on or after 1 April 2023, and market-linked debentures) to
    be SHORT-TERM regardless of holding period, taxed at slab rates. Lumping these in
    with `DEBT_MF_LEGACY` would tax a long-held debt fund at 12.5% instead of the
    taxpayer's marginal rate — a large understatement for a high earner.
    """

    EQUITY_LISTED = "equity_listed"  # Indian recognised exchange, STT paid
    EQUITY_MF = "equity_mf"  # equity-oriented fund, STT paid
    #: Shares listed OUTSIDE India — a US-listed RSU or ESPP holding, typically. NOT a
    #: s.112A asset: no STT is paid and a foreign exchange is not a recognised stock
    #: exchange, so there is no 1,25,000 exemption and no concessional equity rate. The
    #: charge is under s.112, and the long-term threshold is 24 months rather than 12.
    #: Kept distinct from EQUITY_LISTED precisely because the obvious choice for someone
    #: holding foreign stock would otherwise hand them a concession they cannot claim.
    FOREIGN_EQUITY = "foreign_equity"
    SPECIFIED_MF = "specified_mf"  # s.50AA — always short-term, slab rate
    DEBT_MF_LEGACY = "debt_mf_legacy"  # acquired before 1 Apr 2023
    UNLISTED_EQUITY = "unlisted_equity"
    PROPERTY = "property"
    GOLD = "gold"
    OTHER = "other"


#: Months of holding after which a gain is long-term, by asset class. Applies to transfers
#: on or after 23 July 2024, when Finance (No. 2) Act 2024 collapsed three holding-period
#: tiers into two: 12 months for any listed security, 24 months for everything else.
LONG_TERM_MONTHS: dict[str, int] = {
    AssetClass.EQUITY_LISTED: 12,
    AssetClass.EQUITY_MF: 12,
    AssetClass.FOREIGN_EQUITY: 24,
    AssetClass.DEBT_MF_LEGACY: 24,
    AssetClass.UNLISTED_EQUITY: 24,
    AssetClass.PROPERTY: 24,
    AssetClass.GOLD: 24,
    AssetClass.OTHER: 24,
}


#: Asset classes eligible for the s.111A / s.112A concessional equity rates.
EQUITY_CLASSES = frozenset({AssetClass.EQUITY_LISTED, AssetClass.EQUITY_MF})

#: Asset classes deemed short-term by s.50AA irrespective of holding period.
DEEMED_SHORT_TERM_CLASSES = frozenset({AssetClass.SPECIFIED_MF})


@dataclass
class RentPeriod:
    """A stretch of months paying a fixed monthly rent in a given city."""

    months: int
    monthly_rent: int
    is_metro: bool  # metro = Mumbai/Delhi/Kolkata/Chennai -> 50% of basic, else 40%

    def __post_init__(self):
        if self.months <= 0:
            raise ValueError("months must be positive")
        if self.months > 12:
            raise ValueError("a single rent period cannot exceed 12 months")
        if self.monthly_rent < 0:
            raise ValueError("monthly_rent cannot be negative")


@dataclass
class SalaryComponent:
    """One line item from a payslip or Form 16, annualized."""

    name: str
    annual_amount: int
    taxable: bool = True
    is_hra: bool = False
    section_10_14_exempt_amount: int = 0  # e.g. conveyance, meal vouchers, LTA


@dataclass
class SalaryIncome:
    employer_name: str
    components: list[SalaryComponent] = field(default_factory=list)
    #: Needed for HRA and 80CCD(2) caps. DA counted only if it forms part of
    #: retirement benefits.
    basic_plus_da_annual: int = 0
    rent_periods: list[RentPeriod] = field(default_factory=list)
    professional_tax_paid: int = 0  # s.16(iii), old regime only
    employer_nps_contribution: int = 0  # 80CCD(2), tracked apart to apply its own cap

    @property
    def gross_taxable(self) -> int:
        return sum(c.annual_amount for c in self.components if c.taxable)


@dataclass
class HouseProperty:
    is_self_occupied: bool
    annual_rent_received: int = 0
    municipal_taxes_paid: int = 0
    home_loan_interest: int = 0
    is_under_construction: bool = False


@dataclass
class CapitalGainLot:
    asset_class: AssetClass
    is_long_term: bool
    gain: int  # may be negative (loss)
    acquired_on: date | None = None
    transferred_on: date | None = None
    #: True where this engine overrode the caller's `is_long_term` (s.50AA deeming, or
    #: a classification derived from the dates that contradicted the flag). Downstream
    #: reporting surfaces this — a silently corrected input is still a surprise.
    reclassified: bool = False

    def __post_init__(self):
        self.asset_class = AssetClass(self.asset_class)
        claimed = self.is_long_term
        # s.50AA overrides whatever the caller claimed about holding period.
        if self.asset_class in DEEMED_SHORT_TERM_CLASSES:
            self.is_long_term = False
        elif self.acquired_on and self.transferred_on:
            # Both dates given, so derive the classification rather than trusting the
            # caller's flag — getting this wrong is the difference between 12.5% and
            # a marginal rate, and it is exactly what people misjudge on foreign stock.
            self.is_long_term = self.held_for_months() >= LONG_TERM_MONTHS.get(
                self.asset_class, 24
            )
        self.reclassified = self.is_long_term != claimed

    def held_for_months(self) -> int:
        """Whole months between acquisition and transfer. 0 if either date is missing."""
        if not self.acquired_on or not self.transferred_on:
            return 0
        months = (self.transferred_on.year - self.acquired_on.year) * 12 + (
            self.transferred_on.month - self.acquired_on.month
        )
        if self.transferred_on.day < self.acquired_on.day:
            months -= 1
        return max(0, months)

    @property
    def is_equity(self) -> bool:
        """Eligible for the s.111A/112A concessional equity treatment.

        Deliberately excludes FOREIGN_EQUITY: a foreign-listed share pays no STT and is
        not traded on a recognised stock exchange in India, so neither section reaches it.
        """
        return self.asset_class in EQUITY_CLASSES


@dataclass
class Deductions:
    section_80c: int = 0  # PF, ELSS, life insurance, tuition, principal repayment...
    section_80ccd_1b: int = 0  # self NPS, additional 50,000
    section_80d_self_family: int = 0
    section_80d_parents: int = 0
    parents_are_senior_citizens: bool = False
    section_80tta_or_ttb: int = 0  # savings interest (80TTA <60) / all interest (80TTB seniors)
    section_80e_education_loan_interest: int = 0  # no cap
    section_80ddb: int = 0  # capped, higher cap for seniors
    #: Donations already reduced to their DEDUCTIBLE amount by the caller (i.e. the 50%
    #: or 100% rate already applied). The 10%-of-gross-total-income qualifying limit is
    #: applied here, since it depends on income the caller may not have computed yet.
    section_80g_deductible: int = 0
    section_80g_subject_to_qualifying_limit: bool = True
    other_chapter_via: int = 0  # escape hatch; NOT capped — see compute_deductions note


@dataclass
class OtherIncome:
    savings_bank_interest: int = 0
    fd_interest: int = 0
    dividend_income: int = 0  # surcharge on tax attributable to this is capped at 15%
    other_sources: int = 0  # gifts, family pension (taxable portion), honoraria, etc.


@dataclass
class TaxesPaid:
    tds_salary: int = 0
    tds_other: int = 0
    advance_tax: int = 0
    self_assessment_tax: int = 0
    #: Cumulative advance tax paid as of 15 Jun / 15 Sep / 15 Dec / 15 Mar. Supply all
    #: four to have s.234B and s.234C interest computed; leave as None to skip interest
    #: entirely rather than have it silently assumed to be nil.
    advance_tax_by_checkpoint: list[int] | None = None
    #: Whole months from 1 April of the assessment year to the date of payment, for
    #: s.234B. Only consulted when `advance_tax_by_checkpoint` is supplied.
    months_elapsed_for_234b: int = 0

    def __post_init__(self):
        if self.advance_tax_by_checkpoint is not None and len(self.advance_tax_by_checkpoint) != 4:
            raise ValueError(
                "advance_tax_by_checkpoint must have exactly 4 cumulative figures "
                "(15 Jun / 15 Sep / 15 Dec / 15 Mar)"
            )

    @property
    def total(self) -> int:
        return self.tds_salary + self.tds_other + self.advance_tax + self.self_assessment_tax


@dataclass
class TaxpayerProfile:
    assessment_year: str  # e.g. "2026-27"
    age_band: AgeBand = AgeBand.BELOW_60
    is_resident: bool = True  # basic-exemption set-off against capital gains is resident-only
    #: Validated at construction. Anything but INDIVIDUAL raises rather than being
    #: silently computed on the individual's rules.
    assessee_type: AssesseeType = AssesseeType.INDIVIDUAL
    salaries: list[SalaryIncome] = field(default_factory=list)
    house_properties: list[HouseProperty] = field(default_factory=list)
    capital_gains: list[CapitalGainLot] = field(default_factory=list)
    #: Income under the head Profits and Gains of Business or Profession, taxed at slab
    #: rates. Feed the figure from `presumptive.compute_44ad`/`compute_44ada` for a
    #: presumptive filer. Any non-zero value makes this an ITR-3/ITR-4 return and, if
    #: the old regime is chosen, triggers the Form 10-IEA obligation.
    business_income: int = 0
    other_income: OtherIncome = field(default_factory=OtherIncome)
    deductions: Deductions = field(default_factory=Deductions)
    taxes_paid: TaxesPaid = field(default_factory=TaxesPaid)

    def __post_init__(self):
        self.age_band = AgeBand(self.age_band)
        self.assessee_type = AssesseeType(self.assessee_type)
        assert_supported(self.assessee_type)
        if self.assessee_type == AssesseeType.HUF:
            self._validate_huf()

    def _validate_huf(self) -> None:
        """Reject inputs an HUF cannot legally have, rather than silently taxing them.

        Each of these would otherwise flow through the individual machinery and hand
        the HUF a relief it is not entitled to — with nothing in the output looking
        wrong. What IS available to an HUF needs no gating here: 80C, 80D (premium on
        members' health), 80TTA (which extends to HUFs, at the same 10,000 cap), 80DDB
        (a dependent member's treatment), 80G, s.44AD, and the s.115BAC regime choice
        with its Form 10-IEA machinery all apply as-is.
        """
        problems: list[str] = []
        if self.salaries:
            problems.append(
                "salary income — an HUF cannot hold an office of employment, so s.15 "
                "salary (and with it the s.16(ia) standard deduction and s.10(13A) HRA) "
                "cannot arise to it; remuneration from a family business is PGBP or the "
                "karta's own salary, not the HUF's"
            )
        if self.age_band != AgeBand.BELOW_60:
            problems.append(
                "a senior age band — the raised basic exemption at 60 and 80 is an "
                "individual's age concession; an HUF has no age, so age_band must be "
                "left at below_60 (the karta's age is irrelevant)"
            )
        if self.deductions.section_80ccd_1b:
            problems.append(
                "s.80CCD(1B) — NPS deductions are confined to individuals; an HUF "
                "cannot hold an NPS account"
            )
        if self.deductions.section_80e_education_loan_interest:
            problems.append(
                "s.80E — education-loan interest is deductible only to an individual"
            )
        if problems:
            raise ValueError(
                "An HUF profile cannot include " + "; ".join(problems) + "."
            )
