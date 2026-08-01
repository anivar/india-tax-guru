# india-tax-guru

[![CI](https://github.com/anivar/india-tax-guru/actions/workflows/ci.yml/badge.svg)](https://github.com/anivar/india-tax-guru/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Install with skills.sh](https://img.shields.io/badge/skills.sh-npx%20skills%20add%20anivar%2Findia--tax--guru-blue)](https://skills.sh/anivar)

Open-source India income-tax **planning, salary-structuring, and ITR-filing
support** toolkit. Library + CLI, usable standalone or as an agent skill
(Claude Code `SKILL.md`, or any AGENTS.md-compatible agent).

```bash
npx skills add anivar/india-tax-guru
```

Not a filing agent for the government e-filing portal, and not a substitute
for a CA. Rules are versioned per assessment year and non-obvious edge cases
are documented in the module that handles them.

> **Verify before you file.** Tax law is intricate and changes every Budget.
> Treat the output as a well-tested second opinion, not as authority — check it
> against the ITD utility or a CA before filing, and please open an issue if a
> figure disagrees.

## Features

- **Old vs new regime comparison** — full computation under both regimes,
  always both, never just the one you assumed. Ties go to the new regime,
  which is the statutory default and needs no Form 10-IEA opt-out.
- **Age-aware slabs** — the old regime's basic exemption rises to ₹3,00,000 at
  60 and ₹5,00,000 at 80, and super-seniors lose the 5% bracket entirely.
- **Salary & HRA** — period-wise HRA exemption that handles a mid-year rent or
  city change correctly, plus s.16 standard deduction and professional tax.
- **Capital gains** — s.111A/112A equity rates, the ₹1,25,000 s.112A exemption,
  s.50AA (specified mutual funds deemed short-term at slab rates), s.70/74
  set-off ordering, and the resident basic-exemption set-off against gains.
- **Foreign-listed equity** — a US-listed RSU is *not* a s.112A asset. No STT, not a
  recognised Indian exchange, so no ₹1,25,000 exemption, no concessional rate, and a
  24-month long-term threshold rather than 12. Held as its own asset class precisely
  because picking `equity_listed` for it would silently grant all three.
- **Presumptive taxation** — s.44AD and s.44ADA, including the split rate (6% applies
  only to the digitally-received slice of turnover, 8% to the rest — it is not an
  alternative rate on the whole), the ₹3 crore / ₹75 lakh enhanced caps and their 5%
  cash test, the s.44AD(4) lock-in, and the single 15 March advance-tax instalment.
- **House property** — s.24(b) and s.71(3A) caps applied in *aggregate* across
  properties, let-out NAV/30%/interest, carry-forward reported not dropped.
- **Surcharge** — thresholds, the new regime's 25% ceiling, the **15% cap on
  surcharge attributable to capital gains and dividends**, and marginal relief
  computed against tax recomputed at the threshold.
- **Deductions** — 80C/80CCD(1B)/80CCD(2)/80D/80TTA vs 80TTB/80DDB/80E/80G,
  capped, regime-gated, and bounded by gross total income.
- **Settlement** — TDS, advance tax and self-assessment tax netted off to a
  refund or balance-payable figure, with s.234B/234C interest.
- **CTC / salary restructuring optimizer** — searches Basic/HRA/employer-NPS
  splits within realistic employer policy bounds, across both regimes, to
  maximize take-home pay.
- **Salary-slip analysis** — classify and reconcile monthly payslips against
  Form 16, flagging unclassified line items instead of guessing, and feed them
  straight into the engine.
- **Salary-structure advisory** — what to change and what each change is worth,
  with every figure measured by re-running the engine on the counterfactual
  rather than estimated from a marginal rate.
- **Regime-choice compliance** — Form 10-IEA only where business income makes it
  necessary, and the s.139(1) deadline that decides whether the old regime is
  available at all.
- **HUF assessees** — the individual machinery minus the reliefs an HUF cannot
  claim: no s.87A rebate, no age-based exemption, no salary heads, no 80CCD(1B)
  or 80E, and no s.44ADA (individuals and firms only since Finance Act 2021).
  Illegal inputs — an HUF with salary income, a senior age band, or an NPS
  deduction — are rejected at construction rather than silently taxed.

## Not implemented — and why

- **Anyone but an individual or HUF.** AOP/BOI, firm, LLP and company are each taxed
  under different rules — a firm pays a flat 30% with no regime choice; a company sits
  outside s.115BAC entirely, with its own rates and minimum alternate tax. Constructing
  a profile with any of these raises `UnsupportedAssesseeError` rather than quietly
  handing back an individual's tax, because that wrong answer would look completely
  ordinary.
- Actual (non-presumptive) business income, and the tax-audit machinery.
- Foreign income and foreign assets (Schedule FA), cross-border RSU/ESOP tax.
- Pre-construction home-loan interest amortisation.
- Capital-loss carry-forward across years — this is a single-year computation.
- s.234C's carve-out for gains arising after an instalment due date, which needs
  transaction-level dates.
- Direct e-filing or portal automation.

### Document importers: the agent is the importer

There is no code that parses the **prefill JSON**, **AIS JSON** or **Form 16 Part B
PDF**, and that is a decision rather than a gap. ITD publishes no schema for
any of them. Everything that could be learned about their key names came from a
single real file each — n=1 — and the one Form 16 sample already contained two
different Part B renderings with shifted sub-item letters and a self-inconsistent
80D figure. A parser built on that would work on one payroll vendor and fail
silently on the rest, and silent failure in a tax tool is the failure mode this
project exists to avoid.

What works instead is to let an **agent** do the extraction and this engine do the
arithmetic. Reading a semi-structured document whose exact shape it has never seen is
what a model is good at; arithmetic nobody can unit-test is what it is bad at. So the
agent fills in `profile.json` and never states a tax figure of its own.
[`docs/importing.md`](docs/importing.md) carries the per-document guidance and the
reconciliation checks to run before trusting any extracted value.

Two things *are* worth building and are the natural next step, because they rest
on published or self-describing formats rather than guesswork:

- The **ITR export schemas** are real JSON Schema documents published by ITD, with
  `additionalProperties: false` set at the root. Generate types from them and
  validate in CI; do not hand-write the structs.
- **Form 26AS in its text export** is caret-delimited and carries its own column
  headers per part, so it can be parsed as a self-describing stream rather than
  against a fixed layout.

Every limitation above is also called out at the point in the code where it would
otherwise silently produce a wrong number — grep for `not modelled` for the full
list with context.

## Why per-year rule modules

Tax law changes every Budget. Rather than one code path with `if year >=
2024` branches accumulating forever, each assessment year is a small,
self-contained module under `src/india_tax_guru/rules/` with the source
Finance Act cited in a comment. Adding a new year means writing a new file,
not editing old ones — so last year's numbers can never regress.

## Install

```bash
uv sync
uv run itg years
```

## Usage

```bash
uv run itg compare path/to/profile.json
uv run itg optimize-ctc path/to/ctc_input.json
```

See `docs/profile_schema.md` for the input JSON shape, or use the library
directly:

```python
from india_tax_guru.models import TaxpayerProfile, AgeBand
from india_tax_guru.regime import compare_regimes
from india_tax_guru.rules import get_rules

profile = TaxpayerProfile(assessment_year="2026-27", age_band=AgeBand.BELOW_60, ...)
rules = get_rules(profile.assessment_year)
comparison = compare_regimes(profile, rules)
print(comparison.recommended, comparison.savings)
```

## Development

```bash
uv sync --group dev
uv run pytest
uv run ruff check .
```

## Disclaimer

This tool encodes the author's best understanding of Indian income-tax rules
at the time each `rules/ay*.py` module was written. Tax law is complex and
changes frequently; verify figures against CBDT circulars / a qualified CA
before relying on this for an actual filing. No warranty, express or implied
— see LICENSE.

## License

MIT — see [LICENSE](LICENSE).
