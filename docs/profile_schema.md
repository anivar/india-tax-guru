# Input JSON schemas

## Taxpayer profile (`itg compare profile.json`)

```jsonc
{
  "assessment_year": "2026-27",   // must match a module in src/india_tax_guru/rules/
  "age_band": "below_60",         // below_60 | senior_60_80 | super_senior_80_plus
  "is_resident": true,            // non-residents cannot set basic exemption off against gains

  "salaries": [
    {
      "employer_name": "Acme Corp",
      "basic_plus_da_annual": 800000,   // drives the HRA and 80CCD(2) caps
      "components": [
        {"name": "Basic", "annual_amount": 800000},
        {"name": "HRA", "annual_amount": 400000, "is_hra": true},
        {"name": "Meal Vouchers", "annual_amount": 26400,
         "section_10_14_exempt_amount": 26400},
        {"name": "Special Allowance", "annual_amount": 800000}
      ],
      "rent_periods": [
        {"months": 6, "monthly_rent": 45000, "is_metro": true},
        {"months": 6, "monthly_rent": 52000, "is_metro": true}
      ],
      "professional_tax_paid": 2500,     // s.16(iii), old regime only
      "employer_nps_contribution": 80000 // 80CCD(2); do NOT also list as a component
    }
  ],

  "house_properties": [
    {"is_self_occupied": true, "home_loan_interest": 180000},
    {"is_self_occupied": false, "annual_rent_received": 300000,
     "municipal_taxes_paid": 20000, "home_loan_interest": 400000}
  ],

  "capital_gains": [
    {"asset_class": "equity_mf", "is_long_term": true, "gain": 300000},
    {"asset_class": "equity_listed", "is_long_term": false, "gain": -50000},
    {"asset_class": "specified_mf", "is_long_term": true, "gain": 200000}
  ],

  "other_income": {
    "savings_bank_interest": 8000,
    "fd_interest": 20000,
    "dividend_income": 15000,
    "other_sources": 0
  },

  "deductions": {
    "section_80c": 150000,
    "section_80ccd_1b": 50000,
    "section_80d_self_family": 25000,
    "section_80d_parents": 50000,
    "parents_are_senior_citizens": true,
    "section_80tta_or_ttb": 8000,
    "section_80ddb": 40000,
    "section_80e_education_loan_interest": 0,
    "section_80g_deductible": 25000,
    "section_80g_subject_to_qualifying_limit": true,
    "other_chapter_via": 0
  },

  "taxes_paid": {
    "tds_salary": 300000,
    "tds_other": 1200,
    "advance_tax": 0,
    "self_assessment_tax": 0,
    "advance_tax_by_checkpoint": [0, 0, 0, 0],  // omit to skip 234B/234C entirely
    "months_elapsed_for_234b": 4
  }
}
```

### Notes on the fields that bite

**`rent_periods`** — supply one entry per stretch of unchanged rent and city.
HRA is computed period by period, so a mid-year rent rise or a move between a
metro and a non-metro city produces the right answer instead of an average.
Periods that do not add up to twelve months are allowed but produce a warning.

**`employer_nps_contribution`** — part of gross salary AND deductible under
80CCD(2), capped at 10% of basic+DA in the old regime and 14% in the new.
Anything above the cap stays taxable. Do not also list it as a component or it
will be counted twice.

**`asset_class`** — one of `equity_listed`, `equity_mf`, `specified_mf`,
`debt_mf_legacy`, `unlisted_equity`, `property`, `gold`, `other`.
`specified_mf` (debt-oriented funds acquired on or after 1 April 2023) is
forced short-term by s.50AA whatever `is_long_term` says, and is taxed at slab
rates rather than 12.5%.

**`section_80g_deductible`** — supply the amount already reduced by the 50% or
100% rate for that donee. The 10%-of-gross-total-income qualifying limit is
applied for you; set `section_80g_subject_to_qualifying_limit` to false for
donations not subject to it.

**`other_chapter_via`** — an uncapped escape hatch for heads this tool does not
model. It bypasses every statutory limit, so using it emits a warning.

**`advance_tax_by_checkpoint`** — four cumulative figures as of 15 Jun, 15 Sep,
15 Dec and 15 Mar. Omit the field entirely to skip s.234B/234C rather than have
nil interest silently assumed.

### What comes back

`total_tax_liability` is gross of any credit for taxes paid. `refund_due` and
`balance_payable` are the settled position after TDS, advance tax and interest.
Always surface the `notes` list — it carries every disallowance, cap and
unmodelled simplification that changed the number.

## CTC optimization input (`itg optimize-ctc ctc_input.json`)

```jsonc
{
  "assessment_year": "2026-27",
  "annual_ctc": 2400000,
  "annual_rent": 900000,      // 0 if the employee owns their home
  "is_metro": true,
  "age_band": "below_60",
  "other_deductions": {"section_80c": 150000, "section_80ccd_1b": 50000},
  "fixed_meal_voucher_exempt": 26400,
  "fixed_lta_exempt": 0
}
```

Searches Basic (30–50% of CTC by default) and employer NPS (0–14% of basic)
under both regimes, returning candidates sorted by take-home pay. Bounds are
fields on `restructuring.CTCOptimizationInput` if you need to widen them.
