# Importing documents with an agent

There are no document importers in this codebase, and that is deliberate — see the
README for why hand-written parsers for the prefill JSON, AIS JSON and Form 16 PDF
would fail silently. What works instead is to let an agent do the **extraction** and
let this engine do the **arithmetic**.

That split matters. An LLM is good at reading a semi-structured document whose exact
shape it has never seen, and bad at arithmetic you can't test. This engine is the
reverse. So:

> **The agent never computes tax. It only fills in `profile.json`.**

If you find yourself asking a model what someone's tax is, stop and run `itg compare`.

## The flow

1. Agent reads the source document.
2. Agent writes a `profile.json` conforming to [`profile_schema.md`](profile_schema.md).
3. Agent runs the reconciliation checks below and reports every figure to the user.
4. `itg compare` / `itg advise` produce the numbers.

## What to pull from each document

### Prefill JSON (e-filing portal)

Downloaded from the portal or from within the offline ITR utility. Keys are not
documented by ITD and vary; read what is actually there rather than assuming names.
Look for a personal-information block, a salary block derived from the employer's
24Q return, a TDS block, and Chapter VI-A deductions.

Maps to: `salaries[].components`, `salaries[].basic_plus_da_annual`, `deductions`,
`taxes_paid.tds_salary`, `taxes_paid.tds_other`.

**Do not** try to turn a prefill file into an upload file. The prefill and the ITR
export are different formats with different roots and different conventions; there is
no round trip. The ITR **export** schemas *are* published as JSON Schema documents and
are the right target if you ever generate a return.

### Form 26AS

The text export is caret (`^`) delimited and each PART carries its own header row, so
parse it as a self-describing stream: split on `^`, build the column map from the
header line of the part you are in, and skip parts you do not recognise instead of
assuming a layout. Amounts can be negative (over-booked corrections) — read them as
signed decimals, never floats. Dates in the body are `DD-Mon-YYYY`.

Only TDS with a booking status of Final or Matched is safely claimable; treat
Provisional, Overbooked and Unmatched entries as at-risk and tell the user rather than
adding them to `taxes_paid`.

Maps to: `taxes_paid.tds_salary`, `taxes_paid.tds_other`, `taxes_paid.advance_tax`,
`taxes_paid.self_assessment_tax`.

### AIS / TIS

Useful for interest, dividend and SFT entries the taxpayer may have forgotten. AIS
figures are *reported by third parties* and are frequently wrong — never overwrite a
figure the taxpayer gave you with an AIS figure. Surface the discrepancy and let them
decide.

Maps to: `other_income.savings_bank_interest`, `other_income.fd_interest`,
`other_income.dividend_income`.

### Form 16

Part A gives TDS and the employer's TAN. Part B gives the salary breakup. Key your
extraction on section tokens — `16(ia)`, `10(13A)`, `80C`, `80D` — and never on row
numbers or sub-item letters, which move between payroll vendors and can even differ
between two renderings inside the same PDF.

Form 16A (non-salary TDS) is better taken from 26AS, which is already structured.
Form 16B and 16C are TDS certificates for property purchase and rent paid; they
concern the *deductor*, not a salaried filer's own return.

Maps to: `salaries[].components`, `salaries[].professional_tax_paid`, `deductions`,
`taxes_paid.tds_salary`.

### GST returns (GSTR-1 / GSTR-3B / CMP-08) — presumptive filers

For a GST-registered s.44AD/44ADA filer, pull the year's aggregate **taxable value
of outward supplies** and the **tax collected** from GSTR-1/GSTR-3B (a composition
dealer's turnover comes from CMP-08, with no tax collected on invoices). Run
`gst.reconcile_gst_turnover(itr_turnover, gst_taxable_value, gst_collected)` before
any presumptive computation and relay its warnings verbatim. The invoice total is
not the ITR turnover: presumptive income is computed on the GST-exclusive taxable
value, and the AIS will display the GSTR-sourced figure, so an on-portal "mismatch"
against a correctly-filed return is explainable rather than wrong.

Maps to: the `turnover`/`gross_receipts` arguments of
`presumptive.compute_44ad`/`compute_44ada`, whose result goes into
`business_income`.

## Reconciliation — do this before trusting anything

Run these and report the result. They catch most extraction errors:

- **Gross salary** from the payslips or prefill must match Form 16's gross to within
  a rounding tolerance. `payslip.reconcile_against_form16()` does this check.
- **Section 10 exemptions** must sum to Form 16's total-exemption control figure.
- **TDS** in Form 16 Part A must match the 26AS entry for the same TAN.
- **Chapter VI-A**: Form 16 reports both a gross and a deductible amount for several
  sections. The deductible one is what belongs in `deductions`.
- **Any figure appearing in two documents with two values** is a finding to report,
  not a conflict to resolve silently. Prefill and Form 16 disagreeing on 80TTA is
  common and usually means one of them is stale.

## Rules for the agent

1. **Never state a tax figure you did not get from the engine.** Extraction is your
   job; arithmetic is not.
2. **Never invent a field.** If you cannot find something, leave it out and say so.
   A missing 80D is visible in the output; a guessed one is not.
3. **Echo every extracted figure back to the user** before computing. They are the
   only party who knows whether the reimbursement had bills behind it.
4. **Do not mark reimbursements or LTA exempt** on the strength of a payslip line.
   Exemption there depends on submitted proof, which no document you are reading can
   evidence. `to_salary_income()` defaults these to taxable for that reason.
5. **Report the `notes` list** from every result verbatim. It carries the
   disallowances and caps that explain the number.
