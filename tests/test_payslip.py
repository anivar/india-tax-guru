from india_tax_guru.payslip import (
    MonthlySlip,
    PayslipLineItem,
    analyze_payslips,
    reconcile_against_form16,
)


def test_classifies_known_aliases_case_insensitively():
    slips = [
        MonthlySlip(
            month="2025-04",
            line_items=[
                PayslipLineItem(name="BASIC SALARY", amount=50_000),
                PayslipLineItem(name="hra", amount=25_000),
                PayslipLineItem(name="Sodexo", amount=2_200),
                PayslipLineItem(name="Employee PF", amount=6_000, is_deduction=True),
            ],
        )
    ]
    result = analyze_payslips(slips)
    assert result.taxable_components["Basic"] == 50_000
    assert result.taxable_components["HRA"] == 25_000
    assert result.exempt_with_proof_components["Meal Vouchers"] == 2_200
    assert result.deduction_components["Provident Fund"] == 6_000


def test_unclassified_component_surfaced_not_dropped():
    slips = [
        MonthlySlip(
            month="2025-04", line_items=[PayslipLineItem(name="Shift Allowance XYZ", amount=1000)]
        )
    ]
    result = analyze_payslips(slips)
    assert "Shift Allowance XYZ" in result.unclassified_components
    assert result.gross_taxable_annualized == 0
    assert result.notes


def test_irregular_months_summed_not_assumed_uniform():
    slips = [
        MonthlySlip(month="2025-04", line_items=[PayslipLineItem(name="Basic", amount=50_000)]),
        MonthlySlip(
            month="2025-05",
            line_items=[
                PayslipLineItem(name="Basic", amount=50_000),
                PayslipLineItem(name="Bonus", amount=100_000),
            ],
        ),
    ]
    result = analyze_payslips(slips)
    assert result.taxable_components["Basic"] == 100_000
    assert result.taxable_components["Bonus"] == 100_000


def test_reconcile_flags_material_discrepancy():
    slips = [
        MonthlySlip(month="2025-04", line_items=[PayslipLineItem(name="Basic", amount=50_000)])
    ]
    analysis = analyze_payslips(slips)
    note = reconcile_against_form16(analysis, form16_gross_salary=800_000)
    assert note is not None
    assert (
        "750,000" not in note
    )  # sanity: just checking it doesn't crash formatting; real check below
    assert "higher" in note


def test_reconcile_no_note_when_close():
    slips = [
        MonthlySlip(month="2025-04", line_items=[PayslipLineItem(name="Basic", amount=50_000)])
    ]
    analysis = analyze_payslips(slips)
    note = reconcile_against_form16(analysis, form16_gross_salary=50_500)
    assert note is None
