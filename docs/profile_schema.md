# Input JSON schemas

## Taxpayer profile (`itg compare profile.json`)

```jsonc
{
  "assessment_year": "2026-27",   // must match a module in src/india_tax_guru/rules/
  "age_band": "below_60",         // below_60 | senior_60_80 | super_senior_80_plus
  "is_resident": true,            // non-residents lose s.87A, the age concession, and the gains set-off
  "assessee_type": "individual",  // individual (default) | huf — anything else refuses
  "business_income": 0,           // PGBP at slab rates; feed compute_44ad/44ada output here

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
    {"asset_class": "specified_mf", "is_long_term": true, "gain": 200000},
    {"asset_class": "foreign_equity", "gain": 400000,
     "acquired_on": "2023-05-10", "transferred_on": "2025-09-01"}
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

**`assessee_type`** — `individual` (default) or `huf`. An HUF profile must have
no salaries, `age_band` left at `below_60` (an HUF has no age; the karta's is
irrelevant), and no 80CCD(1B) or 80E — each is rejected at construction. The
engine then withholds the s.87A rebate automatically. Any other assessee type
raises `UnsupportedAssesseeError`.

**`business_income`** — income under the head Profits and Gains of Business or
Profession, taxed at slab rates. For a presumptive filer, compute it with
`presumptive.compute_44ad` / `compute_44ada` (GST-registered? reconcile turnover
with `gst.reconcile_gst_turnover` first) and put the declared income here. Any
non-zero value makes this an ITR-3/ITR-4 return and, if the old regime is
chosen, triggers the Form 10-IEA obligation.

**`asset_class`** — one of `equity_listed`, `equity_mf`, `foreign_equity`,
`specified_mf`, `debt_mf_legacy`, `unlisted_equity`, `property`, `gold`,
`other`. `specified_mf` (debt-oriented funds acquired on or after 1 April 2023)
is forced short-term by s.50AA whatever `is_long_term` says, and is taxed at
slab rates rather than 12.5%. `foreign_equity` (a US-listed RSU, say) gets no
s.111A/112A treatment — no ₹1,25,000 exemption, no concessional rate, and a
24-month long-term threshold.

**`acquired_on` / `transferred_on`** — optional ISO dates on a capital-gain
lot. Supply BOTH and the engine derives the long-term classification from the
holding period instead of trusting `is_long_term` — worth doing for foreign
stock, where the 24-month threshold is exactly what people misjudge.

**`section_80g_deductible`** — supply the amount already reduced by the 50% or
100% rate for that donee. The 10%-of-gross-total-income qualifying limit is
applied for you; set `section_80g_subject_to_qualifying_limit` to false for
donations not subject to it.

**`other_chapter_via`** — an uncapped escape hatch for heads this tool does not
model. It bypasses every statutory limit, so using it emits a warning.

**`advance_tax_by_checkpoint`** — four cumulative figures as of 15 Jun, 15 Sep,
15 Dec and 15 Mar. Omit the field entirely to skip s.234B/234C rather than have
nil interest silently assumed.

**`months_elapsed_for_234b`** — whole months from 1 April of the assessment
year to the date the balance will actually be paid, counting a part month as a
whole one. For tax still unpaid, use the intended payment date (filing day,
typically) — e.g. paying on 20 July is 4 months (Apr, May, Jun, Jul). s.234B
runs to the date of payment, not the due date, so leaving this at 0 with a
balance outstanding understates the interest.

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
