"""CTC restructuring optimizer."""

from india_tax_guru.models import AgeBand, Deductions
from india_tax_guru.regime import compute_regime
from india_tax_guru.restructuring import (
    CTCOptimizationInput,
    best_ctc_split,
    optimize_ctc_split,
)


def base_input(**overrides) -> CTCOptimizationInput:
    kwargs = dict(
        annual_ctc=2_400_000,
        annual_rent=900_000,
        is_metro=True,
        age_band=AgeBand.BELOW_60,
        other_deductions=Deductions(section_80c=150_000, section_80ccd_1b=50_000),
    )
    kwargs.update(overrides)
    return CTCOptimizationInput(**kwargs)


def test_candidates_conserve_the_ctc(rules):
    """Every split must allocate exactly the CTC — no rupees invented or lost."""
    inp = base_input()
    for candidate in optimize_ctc_split(inp, rules):
        allocated = (
            candidate.basic_annual
            + candidate.hra_annual
            + candidate.employer_nps_annual
            + candidate.special_allowance_annual
            + inp.fixed_meal_voucher_exempt
        )
        assert allocated == inp.annual_ctc


def test_take_home_equals_ctc_less_nps_less_tax(rules):
    for candidate in optimize_ctc_split(base_input(), rules)[:10]:
        assert (
            candidate.take_home_annual
            == 2_400_000 - candidate.employer_nps_annual - candidate.total_tax
        )


def test_best_candidate_actually_maximizes_take_home(rules):
    candidates = optimize_ctc_split(base_input(), rules)
    best = best_ctc_split(base_input(), rules)
    assert best.take_home_annual == max(c.take_home_annual for c in candidates)


def test_reported_tax_matches_a_real_regime_computation(rules):
    """The optimizer's figure must reproduce under compute_regime, not drift from it."""
    from india_tax_guru.restructuring import _build_profile

    inp = base_input()
    best = best_ctc_split(inp, rules)
    profile, *_ = _build_profile(inp, best.basic_pct, best.employer_nps_pct, rules)
    assert compute_regime(profile, rules, best.regime).total_tax_liability == best.total_tax


def test_zero_rent_forces_zero_hra(rules):
    for candidate in optimize_ctc_split(base_input(annual_rent=0), rules):
        assert candidate.hra_annual == 0


def test_hra_never_exceeds_the_fully_exempt_amount(rules):
    """Allocating HRA above min(50% of basic, rent less 10% of basic) buys nothing."""
    inp = base_input(annual_rent=900_000)
    for candidate in optimize_ctc_split(inp, rules):
        ceiling = min(
            round(0.50 * candidate.basic_annual),
            inp.annual_rent - round(0.10 * candidate.basic_annual),
        )
        assert candidate.hra_annual <= max(0, ceiling)


def test_basic_pct_bounds_respected(rules):
    inp = base_input(basic_pct_range=(0.35, 0.35))
    assert all(c.basic_pct == 0.35 for c in optimize_ctc_split(inp, rules))


def test_both_regimes_are_evaluated(rules):
    regimes = {c.regime for c in optimize_ctc_split(base_input(), rules)}
    assert regimes == {"old", "new"}


def test_old_regime_nps_deduction_capped_at_10_pct(rules):
    """The optimizer must not hand old-regime candidates the new regime's 14% cap."""
    from india_tax_guru.restructuring import _build_profile

    inp = base_input(employer_nps_pct_range=(0.14, 0.14), employer_nps_pct_step=0.14)
    profile, basic, _hra, employer_nps, _special = _build_profile(inp, 0.40, 0.14, rules)
    assert employer_nps == round(basic * 0.14)
    assert compute_regime(profile, rules, "old").deductions_claimed >= round(basic * 0.10)
    old_nps_component = compute_regime(profile, rules, "old").deductions_claimed - (
        150_000 + 50_000
    )
    assert old_nps_component == round(basic * 0.10)
