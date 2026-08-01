from india_tax_guru.models import AgeBand, Deductions
from india_tax_guru.restructuring import CTCOptimizationInput, optimize_ctc_split
from india_tax_guru.rules import get_rules


def test_optimizer_returns_candidates_sorted_by_take_home():
    rules = get_rules("2026-27")
    inp = CTCOptimizationInput(
        annual_ctc=1_800_000,
        annual_rent=600_000,
        is_metro=True,
        age_band=AgeBand.BELOW_60,
        other_deductions=Deductions(section_80c=150_000, section_80ccd_1b=50_000),
    )
    candidates = optimize_ctc_split(inp, rules)
    assert len(candidates) > 1
    take_homes = [c.take_home_annual for c in candidates]
    assert take_homes == sorted(take_homes, reverse=True)


def test_optimizer_respects_basic_pct_bounds():
    rules = get_rules("2026-27")
    inp = CTCOptimizationInput(
        annual_ctc=1_800_000,
        annual_rent=0,
        is_metro=False,
        age_band=AgeBand.BELOW_60,
        other_deductions=Deductions(),
        basic_pct_range=(0.35, 0.35),
    )
    candidates = optimize_ctc_split(inp, rules)
    assert all(c.basic_pct == 0.35 for c in candidates)


def test_zero_rent_forces_zero_hra():
    rules = get_rules("2026-27")
    inp = CTCOptimizationInput(
        annual_ctc=1_800_000,
        annual_rent=0,
        is_metro=True,
        age_band=AgeBand.BELOW_60,
        other_deductions=Deductions(),
    )
    candidates = optimize_ctc_split(inp, rules)
    assert all(c.hra_annual == 0 for c in candidates)


def test_optimizer_considers_both_regimes():
    rules = get_rules("2026-27")
    inp = CTCOptimizationInput(
        annual_ctc=1_800_000,
        annual_rent=600_000,
        is_metro=True,
        age_band=AgeBand.BELOW_60,
        other_deductions=Deductions(section_80c=150_000),
    )
    candidates = optimize_ctc_split(inp, rules)
    regimes_seen = {c.regime for c in candidates}
    assert regimes_seen == {"old", "new"}
