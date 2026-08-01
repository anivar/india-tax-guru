"""Core data models. All money values are in whole INR (integers or floats)."""

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


@dataclass
class RentPeriod:
    """A stretch of months paying a fixed monthly rent in a given city."""

    months: int
    monthly_rent: int
    is_metro: bool  # metro = Mumbai/Delhi/Kolkata/Chennai -> 50% of basic, else 40%

    def __post_init__(self):
        if self.months <= 0:
            raise ValueError("months must be positive")
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
    basic_plus_da_annual: int = (
        0  # needed for HRA calc; DA counted only if part of retirement benefits
    )
    rent_periods: list[RentPeriod] = field(default_factory=list)
    professional_tax_paid: int = 0
    employer_nps_contribution: int = 0  # 80CCD(2), separate from components to track cap

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
    asset_class: str  # "equity_listed", "equity_mf", "debt_mf", "property", "other"
    is_long_term: bool
    gain: int  # can be negative (loss)
    acquired_on: date | None = None
    transferred_on: date | None = None


@dataclass
class Deductions:
    section_80c: int = 0  # PF, ELSS, life insurance, tuition, principal repayment...
    section_80ccd_1b: int = 0  # self NPS, additional 50k
    section_80d_self_family: int = 0
    section_80d_parents: int = 0
    parents_are_senior_citizens: bool = False
    section_80tta_or_ttb: int = 0  # savings interest (80TTA <60, 80TTB seniors incl. FD)
    section_80e_education_loan_interest: int = 0
    section_80g: int = 0
    section_80ddb: int = 0
    other_chapter_via: int = 0


@dataclass
class OtherIncome:
    savings_bank_interest: int = 0
    fd_interest: int = 0
    dividend_income: int = 0
    other_sources: int = 0  # gifts, family pension (taxable portion), honoraria, etc.


@dataclass
class TaxesPaid:
    tds_salary: int = 0
    tds_other: int = 0
    advance_tax: int = 0
    self_assessment_tax: int = 0


@dataclass
class TaxpayerProfile:
    assessment_year: str  # e.g. "2026-27"
    age_band: AgeBand
    salaries: list[SalaryIncome] = field(default_factory=list)
    house_properties: list[HouseProperty] = field(default_factory=list)
    capital_gains: list[CapitalGainLot] = field(default_factory=list)
    other_income: OtherIncome = field(default_factory=OtherIncome)
    deductions: Deductions = field(default_factory=Deductions)
    taxes_paid: TaxesPaid = field(default_factory=TaxesPaid)
    opted_out_of_new_regime: bool = (
        False  # relevant for ITR-3/4 (Form 10-IEA); ITR-1/2 choose per year
    )
