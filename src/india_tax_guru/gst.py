"""GST-turnover reconciliation for presumptive filers — s.44AD/44ADA vs GSTR figures.

Why this exists: the ITD's Annual Information Statement carries a "GST turnover" line
sourced from GSTR-3B, and the e-verification machinery machine-matches it against the
turnover declared in the ITR. A presumptive filer sits at the sharp end of this match,
because the two figures are *supposed* to differ and almost nobody can say by how much:

- **GST collected is not turnover.** Tax collected on outward supplies is a statutory
  liability held for the government, not the assessee's receipt. The s.44AD/44ADA base
  is the GST-EXCLUSIVE taxable value. A filer who copies the invoice total (or the
  GSTR-3B figure plus tax) into the ITR overstates presumptive income by 6-8% (or 50%)
  of the GST component — an error that produces a *clean* AIS match and is therefore
  never questioned, only overpaid.
- **A shortfall the other way is what draws notices.** ITR turnover materially below
  the GSTR taxable value is exactly the pattern e-verification targets. Sometimes it
  is real suppression; often it is explainable (GSTR includes a capital-asset sale or
  a branch transfer that is not business turnover) — but the explanation has to be
  ready, not improvised after the notice.
- **Legitimate excesses exist too.** Exempt or non-GST supplies, and turnover from the
  part of the year before GST registration, appear in the ITR but never in a GSTR.
  These are declared here as `non_gst_receipts` so the reconciliation can bless them
  instead of flagging them.

This module does no tax arithmetic. It classifies the relationship between the two
figures and produces the explanation — so the wrong-but-ordinary-looking cases
(GST-inclusive turnover, silent under-reporting) are caught before filing rather than
by a notice.
"""

from dataclasses import dataclass, field
from enum import StrEnum


class GstReconciliationStatus(StrEnum):
    #: ITR turnover equals GSTR taxable value plus declared non-GST receipts.
    MATCHED = "matched"
    #: ITR turnover equals the GST-INCLUSIVE figure — the filer has counted the tax
    #: collected as their own turnover and is overstating presumptive income.
    GST_INCLUSIVE_TURNOVER = "gst_inclusive_turnover"
    #: ITR turnover falls short of the GSTR taxable value — the AIS cross-match will
    #: flag this, so the gap needs a documented explanation before filing.
    UNDER_REPORTED = "under_reported"
    #: ITR turnover exceeds GSTR taxable value beyond what `non_gst_receipts`
    #: accounts for. Not a notice risk, but tax is being paid on unexplained receipts.
    EXCESS_UNEXPLAINED = "excess_unexplained"


@dataclass(frozen=True)
class GstReconciliation:
    status: GstReconciliationStatus
    itr_turnover: int
    gst_taxable_value: int
    gst_collected: int
    non_gst_receipts: int
    #: ITR turnover less (GSTR taxable value + non-GST receipts). Positive = excess.
    difference: int
    #: The amount wrongly counted as turnover when status is GST_INCLUSIVE_TURNOVER;
    #: presumptive income is overstated by the applicable rate applied to this. Zero
    #: otherwise.
    overstated_turnover: int
    notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def reconcile_gst_turnover(
    itr_turnover: int,
    gst_taxable_value: int,
    gst_collected: int,
    *,
    non_gst_receipts: int = 0,
    tolerance: int = 1_000,
) -> GstReconciliation:
    """Reconcile the ITR's presumptive turnover against GST-return figures.

    `gst_taxable_value` is the aggregate taxable value of outward supplies per
    GSTR-1/GSTR-3B for the year (for a composition dealer, the turnover per CMP-08);
    `gst_collected` is the total tax charged on those supplies. `non_gst_receipts`
    is business turnover legitimately absent from the GST returns — exempt supplies,
    non-GST supplies, and pre-registration turnover — NOT non-business income like
    bank interest, which belongs under other sources and in neither figure.

    `tolerance` absorbs rounding and small credit-note timing differences; anything
    inside it is treated as matched.
    """
    if min(itr_turnover, gst_taxable_value, gst_collected, non_gst_receipts) < 0:
        raise ValueError("reconciliation figures cannot be negative")

    expected = gst_taxable_value + non_gst_receipts
    difference = itr_turnover - expected
    notes: list[str] = []
    warnings: list[str] = []

    if abs(difference) <= tolerance:
        notes.append(
            f"ITR turnover of {itr_turnover:,} reconciles with the GSTR taxable value "
            f"of {gst_taxable_value:,}"
            + (
                f" plus {non_gst_receipts:,} of declared non-GST receipts"
                if non_gst_receipts
                else ""
            )
            + ". The AIS will still display the GSTR-sourced figure, so a mismatch "
            "prompt on the portal is explainable, not a defect."
        )
        return GstReconciliation(
            status=GstReconciliationStatus.MATCHED,
            itr_turnover=itr_turnover,
            gst_taxable_value=gst_taxable_value,
            gst_collected=gst_collected,
            non_gst_receipts=non_gst_receipts,
            difference=difference,
            overstated_turnover=0,
            notes=notes,
        )

    inclusive_figure = gst_taxable_value + gst_collected + non_gst_receipts
    if gst_collected and abs(itr_turnover - inclusive_figure) <= tolerance:
        warnings.append(
            f"ITR turnover of {itr_turnover:,} equals the GST-INCLUSIVE figure "
            f"(taxable value {gst_taxable_value:,} + tax collected {gst_collected:,}"
            + (f" + non-GST receipts {non_gst_receipts:,}" if non_gst_receipts else "")
            + "). GST collected is a liability held for the government, not turnover: "
            f"the presumptive base is overstated by {gst_collected:,}, and tax is "
            "being paid on money that was never income. Declare the taxable value "
            "instead. Note the trap: this error produces a CLEAN-looking AIS match "
            "and will never be questioned — only overpaid."
        )
        return GstReconciliation(
            status=GstReconciliationStatus.GST_INCLUSIVE_TURNOVER,
            itr_turnover=itr_turnover,
            gst_taxable_value=gst_taxable_value,
            gst_collected=gst_collected,
            non_gst_receipts=non_gst_receipts,
            difference=difference,
            overstated_turnover=gst_collected,
            warnings=warnings,
        )

    if difference < 0:
        warnings.append(
            f"ITR turnover of {itr_turnover:,} is {-difference:,} BELOW the GSTR "
            f"taxable value of {gst_taxable_value:,}"
            + (
                f" plus {non_gst_receipts:,} of declared non-GST receipts"
                if non_gst_receipts
                else ""
            )
            + ". This is the exact pattern the AIS cross-match flags for "
            "e-verification. If the GSTR figure includes receipts that are not "
            "business turnover — a capital-asset sale on which GST was charged, or a "
            "branch transfer — document that reconciliation now, before filing, "
            "rather than after a notice. If it does not, the ITR turnover is short."
        )
        return GstReconciliation(
            status=GstReconciliationStatus.UNDER_REPORTED,
            itr_turnover=itr_turnover,
            gst_taxable_value=gst_taxable_value,
            gst_collected=gst_collected,
            non_gst_receipts=non_gst_receipts,
            difference=difference,
            overstated_turnover=0,
            warnings=warnings,
        )

    notes.append(
        f"ITR turnover of {itr_turnover:,} exceeds the GSTR taxable value "
        f"plus declared non-GST receipts by {difference:,}. Over-reporting draws no "
        "notice, but presumptive tax is being paid on the excess. If it is exempt, "
        "non-GST or pre-registration turnover, declare it via `non_gst_receipts` so "
        "the reconciliation records the explanation; if it is not real turnover, "
        "correct the ITR figure."
    )
    return GstReconciliation(
        status=GstReconciliationStatus.EXCESS_UNEXPLAINED,
        itr_turnover=itr_turnover,
        gst_taxable_value=gst_taxable_value,
        gst_collected=gst_collected,
        non_gst_receipts=non_gst_receipts,
        difference=difference,
        overstated_turnover=0,
        notes=notes,
    )


__all__ = [
    "GstReconciliation",
    "GstReconciliationStatus",
    "reconcile_gst_turnover",
]
