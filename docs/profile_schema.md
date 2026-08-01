# Input JSON schemas

## Taxpayer profile (`itg compare profile.json`)

```jsonc
{
  "assessment_year": "2026-27",        // must match a module in src/india_tax_guru/rules/
  "age_band": "below_60",              // below_60 | senior_60_80 | super_senior_80_plus
  "salaries": [
    {
      "employer_name": "Acme Corp",
      "basic_plus_da_annual": 800000,
      "components": [
        {"name": "Basic", "annual_amount": 800000, "taxable": true},
        {"name": "HRA", "annual_amount": 400000, "is_hra": true},
        {"name": "Special Allowance", "annual_amount": 800000}
      ],
      "rent_periods": [
        {"months": 12, "monthly_rent": 45000, "is_metro": true}
      ],
      "employer_nps_contribution": 80000
    }
  ],
  "house_properties": [
    {"is_self_occupied": true, "home_loan_interest": 180000}
  ],
  "capital_gains": [
    {"asset_class": "equity_mf", "is_long_term": true, "gain": 300000}
  ],
  "other_income": {"savings_bank_interest": 8000, "fd_interest": 20000},
  "deductions": {
    "section_80c": 150000,
    "section_80ccd_1b": 50000,
    "section_80d_self_family": 25000,
    "section_80d_parents": 50000,
    "parents_are_senior_citizens": true
  }
}
```

Multiple `salaries` entries model a job change mid-year — each is summed
independently. `rent_periods` supports multiple entries for a mid-year rent
or city change; HRA exemption is computed period-by-period, not annually.

`asset_class` for capital gains: `equity_listed`, `equity_mf`, `debt_mf`,
`property`, `other`. Long-term equity threshold is `equity_listed`/`equity_mf`
with `is_long_term: true`.

## CTC optimization input (`itg optimize-ctc ctc_input.json`)

```jsonc
{
  "assessment_year": "2026-27",
  "annual_ctc": 2400000,
  "annual_rent": 900000,          // 0 if the employee owns their home / claims no HRA
  "is_metro": true,
  "age_band": "below_60",
  "other_deductions": {"section_80c": 150000, "section_80ccd_1b": 50000},
  "fixed_meal_voucher_exempt": 26400,   // optional, defaults shown
  "fixed_lta_exempt": 0                 // optional, only if travel proof will be submitted
}
```

The optimizer searches Basic% (30–50% of CTC by default) and employer-NPS%
(0–10% of Basic by default) in both regimes and returns candidates sorted by
take-home pay, highest first. Bounds are constructor parameters in
`restructuring.CTCOptimizationInput` if you need to widen them.
