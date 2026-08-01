"""Regime-choice compliance: who files Form 10-IEA, and by when the choice must be made.

The single most damaging thing a tax tool can do here is tell a salaried taxpayer to
file Form 10-IEA. They must NOT file it — a taxpayer with no income under the head
"Profits and Gains of Business or Profession" exercises the old-regime option inside
the ITR itself, and prompting them for a Form 10-IEA acknowledgement number makes them
file a form the law does not ask for. The obligation is triggered by the presence of
PGBP income, not by which ITR form is being used, so it is keyed on that here.

What DOES bind a salaried taxpayer is the deadline. Under s.115BAC(6)(ii) the option
must be exercised "along with the return of income to be furnished under sub-section
(1) of section 139" — a belated return under s.139(4) is not a s.139(1) return, so
filing late forfeits the old regime entirely for that year. For a taxpayer the engine
has just told to use the old regime, that is the most consequential thing to say.

Due dates are table-driven per assessment year and per category because CBDT moves them
by circular, sometimes repeatedly and sometimes on the day itself: AY 2025-26's
non-audit date went 31 Jul -> 15 Sep -> 16 Sep 2025, and audit cases went to 10 Dec 2025.
A hard-coded 31 July would have produced false "you have missed the deadline" warnings
for weeks. Operators are expected to update this table mid-season.
"""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class DueDates:
    """s.139(1) due dates for one assessment year, as extended by CBDT."""

    non_audit: date  # ITR-1/ITR-2, and ITR-3/ITR-4 where no audit is required
    audit: date
    #: True where these are the originally-notified dates rather than confirmed
    #: post-extension ones, so a caller can hedge its wording.
    provisional: bool = False


#: Verify against the current CBDT circulars before relying on these — they move.
DUE_DATES: dict[str, DueDates] = {
    # Extended twice by circular; the second extension issued on the day itself.
    "2025-26": DueDates(non_audit=date(2025, 9, 16), audit=date(2025, 12, 10)),
    # As notified; no extension known at the time of writing.
    "2026-27": DueDates(non_audit=date(2026, 7, 31), audit=date(2026, 10, 31), provisional=True),
}


def due_dates_for(assessment_year: str) -> DueDates | None:
    return DUE_DATES.get(assessment_year)


@dataclass(frozen=True)
class RegimeChoiceGuidance:
    requires_form_10iea: bool
    headline: str
    detail: str


def regime_choice_guidance(
    assessment_year: str,
    recommended_regime: str,
    has_business_or_professional_income: bool = False,
    is_audit_case: bool = False,
) -> RegimeChoiceGuidance | None:
    """Guidance on securing the recommended regime. None when nothing need be done.

    The new regime is the default under s.115BAC, so choosing it requires no action and
    carries no deadline risk — guidance is only produced where the OLD regime is
    recommended and something could therefore go wrong.
    """
    if recommended_regime != "old":
        return None

    dates = due_dates_for(assessment_year)
    if dates is None:
        deadline_phrase = "the applicable s.139(1) due date"
    else:
        deadline = dates.audit if is_audit_case else dates.non_audit
        qualifier = (
            " (as notified; confirm no CBDT extension has moved it)"
            if dates.provisional
            else ""
        )
        deadline_phrase = f"{deadline:%d %B %Y}{qualifier}"

    if has_business_or_professional_income:
        return RegimeChoiceGuidance(
            requires_form_10iea=True,
            headline="File Form 10-IEA to opt out of the new regime",
            detail=(
                "Because the return includes income under the head Profits and Gains of "
                f"Business or Profession, Form 10-IEA must be filed on or before "
                f"{deadline_phrase}, and its acknowledgement number quoted in the ITR. "
                "A form filed after the due "
                "date is marked invalid and the old regime is lost for the year. Note also that "
                "a taxpayer with business income gets only one round trip: having opted out and "
                "later withdrawn, the old regime cannot be chosen again while business income "
                "continues."
            ),
        )

    return RegimeChoiceGuidance(
        requires_form_10iea=False,
        headline=f"File the return on or before {deadline_phrase} to keep the old regime",
        detail=(
            "No Form 10-IEA is required — with no business or professional income the choice "
            "is made in the return itself, and filing that form would be unnecessary. But the "
            "choice is only available in a return filed under s.139(1): a belated return under "
            "s.139(4) cannot claim the old regime, so missing the due date forfeits the saving "
            "entirely for this year. A different regime may be chosen afresh next year."
        ),
    )
