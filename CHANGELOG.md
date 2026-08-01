# Changelog

## v0.2.1

Documentation, packaging and agent-experience hardening after an independent
cold-review of the skill; first PyPI release.

- CLI refusals (unsupported assessee, illegal HUF inputs, unknown assessment
  year) are printed as one-line errors with exit code 1 instead of tracebacks.
- Capital-gain lots silently reclassified by the engine (dates contradicting
  `is_long_term`, or s.50AA deeming) are now reported in `notes`.
- Fixed: ISO date strings on capital-gain lots crashed the CLI JSON path.
- Docs: the foreign-stock boundary is drawn explicitly (sale gain modelled;
  vesting-stage perquisite, Schedule FA and foreign tax credit not);
  `profile_schema.md` documents `assessee_type`, `business_income`,
  `foreign_equity`, lot dates and `months_elapsed_for_234b`; SKILL.md carries
  the ordered GST-then-presumptive pipeline with a runnable snippet; an HUF
  example profile is included.
- Packaging: PyPI metadata, Trusted Publishing workflow, install paths for
  skills.sh, `uv tool`, `uv add`/`pip`, and source.

## v0.2.0

Extends the engine beyond the salaried individual: presumptive business income,
foreign-listed equity, HUF assessees, and GST reconciliation — plus two classes
of correctness fixes, each of the silently-wrong kind this project exists to
refuse.

- **Presumptive taxation under s.44AD and s.44ADA**, wired into the computation
  as business income. Models the split rate (6% only on the digitally-received
  slice of turnover, 8% on the rest), the receipt deadline running to the
  s.139(1) due date, non-account-payee instruments deemed cash for the enhanced
  ₹3 crore / ₹75 lakh cap test, the turnover cap sitting inside the
  eligible-business definition (breach removes the section, not just the
  relief), the s.44AD(4) lock-in, and the single 15 March advance-tax
  instalment under s.211(1)(b).
- **Foreign-listed equity as its own asset class.** A US-listed RSU is not a
  s.112A asset: no STT, not a recognised Indian exchange — so no ₹1,25,000
  exemption, no concessional rate, and a 24-month long-term threshold. Holding
  period is derived from acquisition and transfer dates where both are given,
  rather than trusting the caller's flag.
- **HUF assessees supported.** The individual machinery minus the individual-only
  reliefs: no s.87A rebate (including its new-regime marginal relief), no age-based
  basic exemption, no salary heads (and so no s.16 standard deduction or HRA), no
  80CCD(1B) or 80E. What remains applies unchanged: slabs, surcharge, cess, 80C,
  80D, 80TTA at its ₹10,000 cap, 80DDB, 80G, s.44AD, and the s.115BAC regime choice
  with Form 10-IEA. Illegal HUF inputs are rejected at construction.
- **GST-turnover reconciliation for presumptive filers** (`gst.py`). Classifies the
  ITR-vs-GSTR relationship the way the AIS cross-match does: matched (with declared
  exempt/non-GST/pre-registration receipts), GST-inclusive turnover (the
  copy-the-invoice-total error — overstates presumptive income by the tax collected,
  yet produces a clean AIS match), under-reported (the e-verification pattern), or
  unexplained excess. The s.44AD/44ADA docstrings now state the GST-exclusive
  turnover convention explicitly.
- **Fixed: residency-conditioned reliefs were granted to non-residents.** The
  s.87A rebate and the raised basic exemption at 60 and 80 are resident-only;
  the engine was wiping out real non-resident liabilities on age or income
  alone. An external golden corpus of hand-verified scenarios now pins these.
- **Fixed: s.44ADA wrongly admitted an HUF.** The eligibility test was shared with
  s.44AD, but Finance Act 2021 confined s.44ADA to a resident individual or
  partnership firm (not an LLP) from AY 2021-22 — an HUF-run profession would have
  been granted the 50% presumptive rate it lost. The advisory's 80CCD(1B) lever is
  likewise now individual-only.

## v0.1.0 — initial release

Deterministic India income-tax engine for ITR-1 and ITR-2 profiles, with
per-assessment-year rule modules, a CLI, and an agent skill manifest.
Supports AY 2025-26 and AY 2026-27.

### Computation

- Regime comparison under both the old regime and s.115BAC, always both.
- Age-aware old-regime slabs (basic exemption ₹2.5L / ₹3L at 60 / ₹5L at 80).
- Salary: s.16 standard deduction and professional tax, s.10(14) allowances,
  and period-wise HRA that handles a mid-year rent or city change.
- Capital gains: s.111A and s.112A rates, the ₹1,25,000 equity exemption,
  s.50AA specified mutual funds, s.70/74 set-off ordering, and the resident
  basic-exemption set-off against gains.
- House property: s.24(b) and s.71(3A) limits applied in aggregate across
  properties, let-out NAV/30%/interest, carry-forward reported.
- Surcharge: thresholds, the new regime's 25% ceiling, the 15% cap on
  surcharge attributable to capital gains and dividends, and marginal relief
  computed against tax recomputed at the threshold.
- Deductions: 80C, 80CCD(1B), 80CCD(2), 80D, 80TTA/80TTB, 80DDB, 80E, 80G —
  capped, regime-gated, bounded by gross total income.
- Settlement: TDS, advance tax and self-assessment tax netted to a refund or
  balance-payable figure, with s.234B/234C interest.
- s.288A/288B rounding to the nearest ₹10, halves up.

### Advice and compliance

- Salary-structure advisory: employer-NPS headroom, HRA sized to the rent
  actually paid, and Chapter VI-A headroom. Every saving is measured by running
  the counterfactual through the same engine, never estimated from a marginal
  rate. Levers are reported individually and applied cumulatively, since they
  overlap and are not additive.
- Regime-choice compliance. Form 10-IEA is surfaced only where the return has
  business or professional income — a salaried ITR-1/ITR-2 filer must not file
  it. What they get instead is the deadline that actually binds them: the old
  regime exists only in a return furnished under s.139(1), so a belated return
  under s.139(4) forfeits it. Due dates are table-driven per assessment year,
  because CBDT moves them by circular.

### Tooling

- `itg compare`, `itg advise` and `itg optimize-ctc`.
- CTC restructuring optimizer across both regimes.
- Payslip classification, Form 16 reconciliation, and a bridge from analysed
  payslips into the engine.
- `SKILL.md` for Claude Code, `AGENTS.md` for other agents.
- Core is dependency-free; `click` is an optional `cli` extra, so the engine
  runs under Pyodide in a browser.

### Verification

158 tests. Eight canonical scenarios were computed three times each,
independently of this codebase and from the statute, using different
approaches; a figure was accepted only on majority agreement. All eight agreed,
seven unanimously, and the engine reproduces all sixteen figures exactly. Those
are locked in as `tests/test_golden_scenarios.py` and are the suite's oracle.

### Not in this release

Actual (non-presumptive) business income and the tax-audit machinery. Assessees
other than individuals — HUF, AOP/BOI, firm, LLP and company each refuse rather
than borrowing the individual computation. Document importers, which an agent
handles instead (`docs/importing.md`).
