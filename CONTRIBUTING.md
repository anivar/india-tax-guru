# Contributing

## Adding a new assessment year

Tax rules change every Budget. To add AY support:

1. Copy the newest `src/india_tax_guru/rules/ay<yy>_<yy>.py` as a starting
   point — never edit an existing year's module to "fix" it for a new year.
2. Update every number and cite the source (Finance Act / CBDT notification)
   in the module docstring.
3. Register it in `src/india_tax_guru/rules/__init__.py`.
4. Add or update tests in `tests/` that exercise the new year's boundary
   conditions (rebate threshold, surcharge brackets, LTCG exemption).

## Adding a feature

- Read the "Not implemented" list in README.md first — if you're closing one
  of those gaps, say so in the PR description.
- Every non-obvious rule (a cap, an exclusion, a set-off order) belongs in
  the module's docstring under "Edge cases handled", not just in a test.
- `uv run pytest` and `uv run ruff check .` must pass before a PR.

## Reporting a wrong number

Open an issue with: assessment year, regime, the input profile (redact
personal figures — use round numbers), and what the correct figure should be
per which section/circular. A repro without the "why it's wrong" citation is
hard to act on given how many provisions interact.
