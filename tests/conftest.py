"""Shared fixtures. Helpers here build profiles whose figures are hand-checkable, so a
test that fails points at a rule rather than at fixture plumbing.
"""

import pytest

from india_tax_guru.models import (
    AgeBand,
    Deductions,
    SalaryComponent,
    SalaryIncome,
    TaxpayerProfile,
)
from india_tax_guru.rules import get_rules


@pytest.fixture
def rules():
    return get_rules("2026-27")


def make_profile(
    gross_salary: int,
    *,
    age_band: AgeBand = AgeBand.BELOW_60,
    deductions: Deductions | None = None,
    professional_tax: int = 0,
    assessment_year: str = "2026-27",
    **kwargs,
) -> TaxpayerProfile:
    """A salaried taxpayer with a single fully-taxable component.

    Deliberately has NO HRA component: HRA interacts with regime gating, so tests that
    are not about HRA should not have it silently shifting their numbers.
    """
    salary = SalaryIncome(
        employer_name="Test Employer",
        basic_plus_da_annual=gross_salary,
        components=[SalaryComponent(name="Basic", annual_amount=gross_salary)],
        professional_tax_paid=professional_tax,
    )
    return TaxpayerProfile(
        assessment_year=assessment_year,
        age_band=age_band,
        salaries=[salary],
        deductions=deductions or Deductions(),
        **kwargs,
    )
