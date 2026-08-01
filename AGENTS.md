# india-tax-guru — Agent Guide

> For AI agents/LLMs using this repo as a tool: computation engine for India
> income-tax planning, salary/CTC restructuring, and ITR-1/2 filing support.
> See `SKILL.md` for the Claude Code skill manifest; this file is the
> tool-agnostic version for any AGENTS.md-compatible agent.

**Scope:** ITR-1/ITR-2 (salaried + capital gains/house property), any
assessment year with a rules module under `src/india_tax_guru/rules/`.
**Not in scope:** ITR-3/4 (business income), PDF/OCR parsing, e-filing
automation, cross-year loss carry-forward. See README "Not implemented".

## Install

```bash
uv sync
```

## Core operations

| Task | Command / entry point |
|---|---|
| Compare old vs new regime | `uv run itg compare <profile.json>` |
| Optimize CTC split | `uv run itg optimize-ctc <ctc_input.json>` |
| List supported years | `uv run itg years` |
| Payslip reconciliation | `india_tax_guru.payslip.analyze_payslips` / `reconcile_against_form16` (library only, no CLI) |
| Advance-tax interest | `india_tax_guru.interest.compute_advance_tax_interest` (library only) |

Input JSON shape: `docs/profile_schema.md`. Examples: `docs/examples/*.json`.

## Rules for agents working in or on this repo

1. **Never guess a tax figure.** Every number the engine returns traces to a
   function in `src/india_tax_guru/`; don't hand-compute a workaround when a
   module already exists (`salary.py`, `capital_gains.py`, `house_property.py`,
   `deductions.py`, `compute.py`, `regime.py`, `interest.py`, `restructuring.py`).
2. **Surface `notes` fields verbatim.** `RegimeResult.deduction_notes`,
   `CapitalGainsResult.unabsorbed_loss_note`, `HousePropertyResult.note`, and
   `PayslipAnalysis.notes` flag simplifications that change what a number
   means (e.g. "carry-forward not modelled"). Dropping these when reporting
   to a user is a correctness bug, not a style choice.
3. **Adding a new assessment year:** copy the newest `rules/ay<yy>_<yy>.py`,
   update every figure, cite the Finance Act / CBDT notification in the
   module docstring, register it in `rules/__init__.py`. Never edit an
   existing year's numbers to "fix" a new year's requirement — see
   CONTRIBUTING.md.
4. **Regime-gating is load-bearing.** New regime disallows HRA exemption,
   most Section 10(14) allowances, and nearly all Chapter VI-A deductions
   except 80CCD(2). This is enforced in `salary.taxable_salary(regime=...)`
   and `deductions.compute_deductions(..., regime)` — do not bypass by
   computing exemptions regime-agnostically.
5. **Before merging a change:** `uv run pytest` and `uv run ruff check .`
   must both pass (CI enforces this on `.github/workflows/ci.yml`).

## Boundaries

- Does not file returns or talk to the e-filing portal — produces numbers
  and recommendations for the user or a downstream tool to act on.
- If an assessment year has no rules module, say so explicitly rather than
  extrapolating from the nearest year.
