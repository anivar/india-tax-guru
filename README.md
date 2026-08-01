# india-tax-guru

[![CI](https://github.com/anivar/india-tax-guru/actions/workflows/ci.yml/badge.svg)](https://github.com/anivar/india-tax-guru/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/india-tax-guru)](https://pypi.org/project/india-tax-guru/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Install with skills.sh](https://img.shields.io/badge/skills.sh-npx%20skills%20add%20anivar%2Findia--tax--guru-blue)](https://skills.sh/anivar/india-tax-guru)

Compute your Indian income tax under **both regimes, always** — and see exactly
what to change to pay less. A deterministic engine with 247 hand-verified tests,
usable as a CLI, a Python library, or an AI-agent skill.

> **Verify before you file.** Treat the output as a well-tested second opinion,
> not as authority — check it against the ITD utility or a CA, and open an issue
> if a figure disagrees.

## Quick start

```bash
uv tool install "india-tax-guru[cli]"     # or: pip install "india-tax-guru[cli]"
itg compare profile.json
```

`profile.json` is your year in one file — salary, rent, gains, deductions, TDS
([full schema](docs/profile_schema.md), [example](docs/examples/profile.json)).
You get both regimes side by side, a recommendation, and every rule that changed
your number spelled out:

```text
[OLD regime]                              [NEW regime]
  TOTAL TAX LIABILITY     166,610           TOTAL TAX LIABILITY     220,970
  REFUND DUE              134,590           REFUND DUE               80,230

Recommended: OLD regime (saves 54,360)
note: HRA and s.10(14) exemptions worth 426,400 are not available under the
      new regime (s.115BAC) and have been disallowed.
```

Then:

```bash
itg advise profile.json        # what to change and what each change is worth
itg optimize-ctc ctc.json      # best Basic/HRA/employer-NPS split for take-home
```

## Use it with an AI agent

This repo is also an agent skill — point Claude Code (or any AGENTS.md-compatible
agent) at your Form 16 / payslips and let it fill in the profile while the engine
does all the arithmetic:

```bash
npx skills add anivar/india-tax-guru
```

The division of labour is strict: the agent reads documents, the engine computes
tax. The agent is never allowed to state a tax figure of its own. See
[docs/importing.md](docs/importing.md).

## Use it as a library

```bash
uv add india-tax-guru          # zero runtime dependencies
```

```python
from india_tax_guru.models import TaxpayerProfile, OtherIncome
from india_tax_guru.regime import compare_regimes
from india_tax_guru.rules import get_rules

profile = TaxpayerProfile(
    assessment_year="2026-27",
    other_income=OtherIncome(fd_interest=800_000),
)
result = compare_regimes(profile, get_rules(profile.assessment_year))
print(result.recommended, result.savings)   # new 75400 (s.87A wipes out new-regime tax)
```

## What it handles

- **Old vs new regime** — full computation under both, every time. Ties go to
  the new regime (the statutory default; no Form 10-IEA needed).
- **Salary & HRA** — period-wise HRA (mid-year rent or city changes come out
  right), s.16 standard deduction, professional tax, 80CCD(2) employer NPS.
- **Capital gains** — s.111A/112A rates and the ₹1,25,000 exemption, s.50AA,
  set-off ordering, basic-exemption set-off. Foreign-listed stock (US RSUs) is
  its own asset class: no equity concessions, 24-month threshold, and the
  classification is derived from your dates rather than trusted.
- **Presumptive business income** — s.44AD/44ADA with the real 6%/8% split
  rate, enhanced caps, and the single 15 March advance-tax instalment.
- **GST reconciliation** — ITR turnover checked against GSTR figures the way
  the AIS cross-match does it, catching both silent traps: GST-inclusive
  turnover (you overpay, and it *looks* clean) and under-reporting (you get an
  e-verification notice).
- **House property, deductions, surcharge** — aggregate s.24(b)/71(3A) caps,
  all the usual Chapter VI-A heads capped and regime-gated, surcharge with
  marginal relief and the 15% cap on gains/dividends.
- **Settlement** — TDS and advance tax netted to a refund/payable figure, with
  s.234B/234C interest.
- **Salary restructuring** — an optimizer and an advisory where every rupee of
  claimed saving is measured by re-running the engine, never estimated.
- **HUF assessees** — the individual machinery minus everything an HUF cannot
  claim, with illegal inputs rejected loudly at construction.

Every assessment year is its own rules module with the Finance Act cited —
adding a year never touches last year's numbers. Currently: **AY 2025-26 and
AY 2026-27**.

## What it refuses to do

Wrong tax that looks ordinary is the failure mode this project is built
against, so out-of-scope inputs are **refused with an explanation**, never
approximated:

- Firms, LLPs, companies, AOP/BOI (each taxed under different rules).
- Books-based business income and tax audit; multi-year loss carry-forward.
- Vesting-stage RSU/ESOP perquisite, Schedule FA, foreign tax credit (the
  *sale* gain of foreign stock is computed; the rest is not).
- Direct e-filing or portal automation.
- Parsing Form 16 / AIS PDFs in code — no published schema exists, so parsers
  fail silently; an agent reads them instead ([why](docs/importing.md)).

## Development

```bash
git clone https://github.com/anivar/india-tax-guru && cd india-tax-guru
uv sync --group dev
uv run pytest        # 247 tests, all asserting hand-derived figures
```

Contributions welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). Found a wrong
figure? That's the most valuable issue you can open: include the AY, regime,
a redacted profile, and the section/circular that shows the correct treatment.

## Disclaimer

This tool encodes the author's best understanding of Indian income-tax rules at
the time each `rules/ay*.py` module was written. Tax law is complex and changes
frequently; verify against CBDT circulars or a qualified CA before filing. No
warranty — see [LICENSE](LICENSE) (MIT).
