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


class AssetClass(StrEnum):
    """Capital asset classes, split by how they are TAXED rather than by what they are.

    `SPECIFIED_MF` exists because s.50AA deems gains on specified mutual funds (debt-
    oriented funds acquired on or after 1 April 2023, and market-linked debentures) to
    be SHORT-TERM regardless of holding period, taxed at slab rates. Lumping these in
    with `DEBT_MF_LEGACY` would tax a long-held debt fund at 12.5% instead of the
    taxpayer's marginal rate — a large understatement for a high earner.
    """

    EQUITY_LISTED = "equity_listed"  # s.111A / s.112A eligible (STT paid)
    EQUITY_MF = "equity_mf"  # s.111A / s.112A eligible
    SPECIFIED_MF = "specified_mf"  # s.50AA — always short-term, slab rate
    DEBT_MF_LEGACY = "debt_mf_legacy"  # acquired before 1 Apr 2023
    UNLISTED_EQUITY = "unlisted_equity"
    PROPERTY = "property"
    GOLD = "gold"
    OTHER = "other"


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

    def __post_init__(self):
        self.asset_class = AssetClass(self.asset_class)
        # s.50AA overrides whatever the caller claimed about holding period.
        if self.asset_class in DEEMED_SHORT_TERM_CLASSES:
            self.is_long_term = False

    @property
    def is_equity(self) -> bool:
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
    salaries: list[SalaryIncome] = field(default_factory=list)
    house_properties: list[HouseProperty] = field(default_factory=list)
    capital_gains: list[CapitalGainLot] = field(default_factory=list)
    other_income: OtherIncome = field(default_factory=OtherIncome)
    deductions: Deductions = field(default_factory=Deductions)
    taxes_paid: TaxesPaid = field(default_factory=TaxesPaid)

    def __post_init__(self):
        self.age_band = AgeBand(self.age_band)
