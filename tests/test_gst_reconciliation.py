"""GST-turnover reconciliation: the two silent failure modes must be caught.

The dangerous cases are the quiet ones. A GST-inclusive turnover produces a clean AIS
match while overpaying tax on money that was never income; an under-reported turnover
looks fine in the ITR and surfaces only as an e-verification notice months later. Both
must be classified, not merely diffed.
"""

import pytest

from india_tax_guru.gst import (
    GstReconciliationStatus,
    reconcile_gst_turnover,
)

# A year of a GST-registered trader: 1,00,00,000 taxable value, 18% GST charged.
TAXABLE = 10_000_000
GST = 1_800_000


def test_exact_match():
    result = reconcile_gst_turnover(TAXABLE, TAXABLE, GST)
    assert result.status == GstReconciliationStatus.MATCHED
    assert result.difference == 0
    assert result.overstated_turnover == 0
    assert not result.warnings


def test_match_within_tolerance():
    result = reconcile_gst_turnover(TAXABLE + 900, TAXABLE, GST)
    assert result.status == GstReconciliationStatus.MATCHED
    assert result.difference == 900


def test_gst_inclusive_turnover_is_named_not_just_flagged_as_excess():
    """1,18,00,000 declared: the classic copy-the-invoice-total error."""
    result = reconcile_gst_turnover(TAXABLE + GST, TAXABLE, GST)
    assert result.status == GstReconciliationStatus.GST_INCLUSIVE_TURNOVER
    assert result.overstated_turnover == GST
    assert any("liability" in w for w in result.warnings)
    # The trap is that this looks fine — the warning must say so.
    assert any("CLEAN" in w for w in result.warnings)


def test_gst_inclusive_detection_needs_gst_actually_collected():
    """With no GST collected there is no inclusive figure to match — plain excess."""
    result = reconcile_gst_turnover(TAXABLE + 500_000, TAXABLE, 0)
    assert result.status == GstReconciliationStatus.EXCESS_UNEXPLAINED


def test_under_reported_turnover_warns_about_the_ais_cross_match():
    result = reconcile_gst_turnover(9_000_000, TAXABLE, GST)
    assert result.status == GstReconciliationStatus.UNDER_REPORTED
    assert result.difference == -1_000_000
    assert any("e-verification" in w for w in result.warnings)


def test_non_gst_receipts_explain_a_legitimate_excess():
    """4,00,000 of exempt supplies appear in the ITR but in no GSTR — that is fine."""
    result = reconcile_gst_turnover(
        TAXABLE + 400_000, TAXABLE, GST, non_gst_receipts=400_000
    )
    assert result.status == GstReconciliationStatus.MATCHED


def test_non_gst_receipts_do_not_mask_an_inclusive_error():
    """Exempt supplies AND the GST component both folded in: still the inclusive error."""
    result = reconcile_gst_turnover(
        TAXABLE + 400_000 + GST, TAXABLE, GST, non_gst_receipts=400_000
    )
    assert result.status == GstReconciliationStatus.GST_INCLUSIVE_TURNOVER
    assert result.overstated_turnover == GST


def test_unexplained_excess_is_reported_not_blessed():
    result = reconcile_gst_turnover(TAXABLE + 700_000, TAXABLE, GST)
    assert result.status == GstReconciliationStatus.EXCESS_UNEXPLAINED
    assert result.difference == 700_000
    assert any("non_gst_receipts" in n for n in result.notes)


def test_negative_figures_are_rejected():
    with pytest.raises(ValueError):
        reconcile_gst_turnover(-1, TAXABLE, GST)


def test_composition_dealer_shape_works_the_same():
    """CMP-08 turnover 60,00,000, 1% composition levy paid out of pocket (not
    collected on invoices) — gst_collected is 0 and the figures should just match."""
    result = reconcile_gst_turnover(6_000_000, 6_000_000, 0)
    assert result.status == GstReconciliationStatus.MATCHED
