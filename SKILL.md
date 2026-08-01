---
name: india-tax-guru
description: >
  India income-tax planning, salary/CTC restructuring, and ITR-1/2
  filing-support toolkit. Computes old-vs-new regime comparison,
  HRA/capital-gains/house-property tax, advance-tax interest (234B/234C),
  and optimal CTC splits. Triggers on: India income tax, ITR-1/ITR-2, old vs
  new tax regime, HRA exemption, CTC structuring/salary restructuring,
  capital gains tax India, Form 16/payslip reconciliation, or advance tax
  interest questions.
license: MIT
user-invocable: true
agentic: true
compatibility: "Requires Python >=3.11 and uv. CLI: itg. Library: india_tax_guru."
metadata:
  author: Anivar Aravind
  author_url: https://anivar.net
  version: 0.1.0
  tags: india, income-tax, itr, tax-planning, salary-structuring, ctc, hra, capital-gains, regime-comparison
allowed-tools: Bash(uv:*) Bash(itg:*)
---

# india-tax-guru

A computation engine, not a chat-only assistant — every claim it makes about
tax owed traces back to a specific function in this repo, and every rule is
versioned per assessment year so nothing drifts silently across Budgets.

## When to use this skill

- User asks which tax regime (old vs new) is better for their income/deductions.
- User wants their CTC restructured (Basic/HRA/employer-NPS split) to maximize
  take-home pay.
- User wants HRA exemption, capital gains tax, or house-property income/loss
  computed correctly (period-wise, not a flat annual shortcut).
- User wants to reconcile monthly payslips against Form 16.
- User wants advance-tax interest (234B/234C) estimated.

## Importing documents

There are no document parsers in this repo, by design — ITD publishes no schema for
the prefill JSON or AIS JSON, and Form 16 Part B renders differently per payroll
vendor, so a hardcoded parser fails silently. **You are the importer.** Read the
document, fill in `profile.json`, and let the engine do the arithmetic.

The division of labour is not negotiable: **you never compute tax.** Reading a
semi-structured document you have never seen before is what you are good at;
arithmetic that nobody can unit-test is what the engine is for. If you catch yourself
about to state a tax figure you did not get from `itg`, stop and run it.

`docs/importing.md` has per-document guidance (prefill JSON, Form 26AS, AIS, Form 16)
and the reconciliation checks to run before trusting anything you extracted. The
short version: echo every extracted figure back to the user, never invent a field you
could not find, never mark a reimbursement exempt on the strength of a payslip line,
and report any figure that two documents disagree on rather than silently picking one.

## How to use it

1. Gather the taxpayer's inputs into the JSON shape documented in
   `docs/profile_schema.md` — from documents (see above) or by asking. Ask only for
   what's missing; don't re-derive figures the user already gave you.
2. Run `uv run itg compare <profile.json>` for a regime comparison, or
   `uv run itg optimize-ctc <ctc_input.json>` for salary structuring.
3. For anything not covered by the CLI (payslip reconciliation, one-off
   set-off questions), import the library directly: `india_tax_guru.payslip`,
   `india_tax_guru.capital_gains`, `india_tax_guru.interest`.
4. **Always surface the result's `notes` list verbatim.** It carries every
   disallowance, statutory cap and unmodelled simplification that changed the
   number — for example that a new-regime computation dropped the user's HRA
   and 80C entirely, or that a house-property loss is being carried forward
   rather than set off. Reporting the figure without them is misleading.
5. Distinguish `total_tax_liability` (gross) from `refund_due` /
   `balance_payable` (settled after TDS and advance tax). Users asking "how
   much tax do I owe" almost always mean the latter.
6. State the assessment year's rule source (cited at the top of the matching
   `src/india_tax_guru/rules/ay*.py` file) so the user can sanity-check it
   against a current CBDT circular before filing.

## Boundaries

- **Individuals and HUFs only.** AOP/BOI, firm, LLP and company are each taxed under
  different rules — a firm pays a flat 30% with no regime choice; a company is outside
  s.115BAC entirely and has its own rates and MAT. Constructing a profile with any of
  these raises `UnsupportedAssesseeError` rather than quietly returning an individual's
  tax. Relay the refusal; don't work around it. For an HUF, use
  `assessee_type="huf"`: the engine then withholds the s.87A rebate, the age
  concession, salary heads, 80CCD(1B), 80E and s.44ADA, and rejects inputs an HUF
  cannot have instead of taxing them.
- **Business income only if presumptive.** s.44AD and s.44ADA are modelled
  (`presumptive.py`) and flow into the computation as business income; actual
  (books-based) business profits and the tax-audit machinery are not — say so rather
  than guessing at rules this repo doesn't implement.
- This tool does not file returns or talk to the e-filing portal. It produces numbers
  and recommendations for the user (or another tool) to act on.
- If the assessment year requested has no rules module in
  `src/india_tax_guru/rules/`, say so explicitly rather than extrapolating from the
  nearest year — tax law does not change linearly.
