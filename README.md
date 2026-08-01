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
  Form 16, flagging unclassified line items instead of guessing.

## Not implemented (out of scope for v1)

- ITR-3 / ITR-4 (business/professional income, presumptive taxation).
- PDF/OCR parsing of Form 16, AIS, or scanned payslips — inputs are
  structured JSON/CSV. Document-parsing is a natural v2 addition; contributions
  welcome.
- Foreign income / foreign assets (Schedule FA), RSU/ESOP cross-border tax.
- Pre-construction home-loan interest amortization.
- Capital-loss carry-forward across years (single-year computation only).
- 234C's carve-out for gains arising after an instalment due date.
- Direct e-filing / portal automation.

Every one of these is called out at the point in the code where it would
otherwise silently produce a wrong number — grep for "not modelled" if you
want the full list with context.

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
