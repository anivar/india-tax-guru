"""Only individuals are supported, and the others must refuse rather than approximate.

An HUF computed on the individual rules would silently pick up the s.87A rebate, the
s.16(ia) standard deduction and the age-based basic exemption, none of which it is
entitled to. The whole point of this guard is that the wrong answer would look
completely ordinary.
"""

import pytest

from india_tax_guru.models import (
    AssesseeType,
    TaxpayerProfile,
    UnsupportedAssesseeError,
    assert_supported,
)


def test_individual_is_the_default_and_is_supported():
    profile = TaxpayerProfile(assessment_year="2026-27")
    assert profile.assessee_type == AssesseeType.INDIVIDUAL
    assert_supported(AssesseeType.INDIVIDUAL)


@pytest.mark.parametrize(
    "assessee_type",
    [t for t in AssesseeType if t != AssesseeType.INDIVIDUAL],
)
def test_every_other_assessee_type_refuses_at_construction(assessee_type):
    with pytest.raises(UnsupportedAssesseeError) as exc:
        TaxpayerProfile(assessment_year="2026-27", assessee_type=assessee_type)
    assert str(assessee_type) in str(exc.value)


def test_huf_refusal_names_the_reliefs_it_would_wrongly_receive():
    with pytest.raises(UnsupportedAssesseeError) as exc:
        TaxpayerProfile(assessment_year="2026-27", assessee_type=AssesseeType.HUF)
    message = str(exc.value)
    assert "87A" in message
    assert "16(ia)" in message
    assert "80CCD" in message


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

    with pytest.raises(UnsupportedAssesseeError):
        TaxpayerProfile(assessment_year="2026-27", assessee_type="huf")


def test_unknown_assessee_string_is_rejected():
    with pytest.raises(ValueError):
        TaxpayerProfile(assessment_year="2026-27", assessee_type="partnership")


def test_error_is_a_notimplementederror_so_callers_can_catch_broadly():
    assert issubclass(UnsupportedAssesseeError, NotImplementedError)
