# india-tax-guru — Agent Guide

> For AI agents/LLMs using this repo as a tool: computation engine for India
> income-tax planning, salary/CTC restructuring, and ITR filing support.
> See `SKILL.md` for the Claude Code skill manifest; this file is the
> tool-agnostic version for any AGENTS.md-compatible agent.

**Scope:** individuals and HUFs — salaried income, capital gains (including
foreign-listed equity), house property, presumptive business/professional
income under s.44AD/44ADA (with GST-turnover reconciliation), for any
assessment year with a rules module under `src/india_tax_guru/rules/`.
**Not in scope:** firms/LLPs/companies/AOP-BOI (refused with
`UnsupportedAssesseeError`), books-based business income and the tax-audit
machinery, PDF/OCR parsing, e-filing automation, cross-year loss
carry-forward. See README "Not implemented".

## Install

```bash
uv sync
```

## Core operations

| Task | Command / entry point |
|---|---|
| Compare old vs new regime | `uv run itg compare <profile.json>` |
| Salary-structure advisory | `uv run itg advise <profile.json>` |
| Optimize CTC split | `uv run itg optimize-ctc <ctc_input.json>` |
| List supported years | `uv run itg years` |
| Presumptive income (s.44AD/44ADA) | `india_tax_guru.presumptive.compute_44ad` / `compute_44ada` — feed the result into `profile.business_income` |
| GST-turnover reconciliation | `india_tax_guru.gst.reconcile_gst_turnover` — run BEFORE computing for a GST-registered presumptive filer |
| Payslip reconciliation | `india_tax_guru.payslip.analyze_payslips` / `reconcile_against_form16` (library only) |
| Advance-tax interest | computed inside `compute_regime` when `taxes_paid.advance_tax_by_checkpoint` is supplied; also callable directly from `india_tax_guru.interest` |

Input JSON shape: `docs/profile_schema.md`. Examples: `docs/examples/*.json`.

## Rules for agents working in or on this repo

1. **Never guess a tax figure.** Every number the engine returns traces to a
   function in `src/india_tax_guru/`; don't hand-compute a workaround when a
   module already exists (`salary.py`, `capital_gains.py`, `house_property.py`,
   `deductions.py`, `compute.py`, `regime.py`, `interest.py`, `restructuring.py`,
   `presumptive.py`, `gst.py`, `advisory.py`, `compliance.py`, `payslip.py`).
2. **Surface `RegimeResult.notes` verbatim.** It aggregates every disallowance,
   statutory cap and unmodelled simplification that changed the number.
   Dropping it when reporting to a user is a correctness bug, not a style
   choice.
3. **`total_tax_liability` is gross.** Use `refund_due` / `balance_payable` for
   what the taxpayer actually settles.
4. **Adding a new assessment year:** copy the newest `rules/ay<yy>_<yy>.py`,
   update every figure, cite the Finance Act / CBDT notification in the module
   docstring, register it in `rules/__init__.py`. Never edit an existing year's
   numbers to fix a new year's requirement — see CONTRIBUTING.md.
5. **Regime-gating is load-bearing and has bitten repeatedly.** The new regime
   disallows HRA and s.10(14) allowances, professional tax, s.24(b)
   self-occupied interest, house-property loss set-off, and all of Chapter VI-A
   except 80CCD(2). Each is driven by an explicit flag on `RegimeRules` —
   `allows_hra_and_10_14`, `allows_professional_tax`,
   `allows_self_occupied_interest`, `allows_house_property_loss_setoff`,
   `allowed_deductions`. Add a new relief by adding a flag, never by branching
   on a bare `regime == "old"` string somewhere downstream.
6. **Tests assert hand-derived figures**, with the derivation in the docstring.
   Do not add a test that asserts only a range or a sign — that is precisely the
   class of test that let ten wrong-figure bugs through a green suite.
7. **Before merging:** `uv run pytest` and `uv run ruff check .` must both pass
   (CI enforces this via `.github/workflows/ci.yml`).

## Boundaries

- Does not file returns or talk to the e-filing portal — produces numbers
  and recommendations for the user or a downstream tool to act on.
- If an assessment year has no rules module, say so explicitly rather than
  extrapolating from the nearest year.
