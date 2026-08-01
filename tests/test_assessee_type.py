"""Individuals and HUFs are supported; the others must refuse rather than approximate.

A firm computed on the individual rules would silently pick up slab rates instead of
its flat 30%, and a company would collect a regime choice s.115BAC never offers it.
The whole point of this guard is that the wrong answer would look completely ordinary.
The HUF-specific rules (no s.87A, no age concession, no salary) live in test_huf.py.
"""

import pytest

from india_tax_guru.models import (
    AssesseeType,
    TaxpayerProfile,
    UnsupportedAssesseeError,
    assert_supported,
)

SUPPORTED = (AssesseeType.INDIVIDUAL, AssesseeType.HUF)


def test_individual_is_the_default_and_is_supported():
    profile = TaxpayerProfile(assessment_year="2026-27")
    assert profile.assessee_type == AssesseeType.INDIVIDUAL
    assert_supported(AssesseeType.INDIVIDUAL)


def test_huf_is_supported():
    profile = TaxpayerProfile(assessment_year="2026-27", assessee_type=AssesseeType.HUF)
    assert profile.assessee_type == AssesseeType.HUF


@pytest.mark.parametrize(
    "assessee_type",
    [t for t in AssesseeType if t not in SUPPORTED],
)
def test_every_other_assessee_type_refuses_at_construction(assessee_type):
    with pytest.raises(UnsupportedAssesseeError) as exc:
        TaxpayerProfile(assessment_year="2026-27", assessee_type=assessee_type)
    assert str(assessee_type) in str(exc.value)


def test_firm_refusal_explains_the_flat_rate():
    with pytest.raises(UnsupportedAssesseeError) as exc:
        TaxpayerProfile(assessment_year="2026-27", assessee_type=AssesseeType.FIRM)
    assert "30%" in str(exc.value)


def test_company_refusal_explains_it_is_outside_115bac():
    with pytest.raises(UnsupportedAssesseeError) as exc:
        TaxpayerProfile(assessment_year="2026-27", assessee_type=AssesseeType.COMPANY)
    message = str(exc.value)
    assert "115BAC" in message
    assert "115JB" in message or "alternate tax" in message


def test_string_value_is_coerced_and_still_validated():
    """A JSON caller passes a bare string; it must be checked, not trusted."""
    assert TaxpayerProfile(
        assessment_year="2026-27", assessee_type="individual"
    ).assessee_type is AssesseeType.INDIVIDUAL

    assert TaxpayerProfile(
        assessment_year="2026-27", assessee_type="huf"
    ).assessee_type is AssesseeType.HUF

    with pytest.raises(UnsupportedAssesseeError):
        TaxpayerProfile(assessment_year="2026-27", assessee_type="llp")


def test_unknown_assessee_string_is_rejected():
    with pytest.raises(ValueError):
        TaxpayerProfile(assessment_year="2026-27", assessee_type="partnership")


def test_error_is_a_notimplementederror_so_callers_can_catch_broadly():
    assert issubclass(UnsupportedAssesseeError, NotImplementedError)
