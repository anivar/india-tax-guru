# Changelog

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
- Foreign-listed equity as its own asset class: no s.112A exemption, no
  concessional rate, 24-month long-term threshold.
- Presumptive taxation under s.44AD and s.44ADA, wired into the computation as
  business income.
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
