"""House property: aggregate caps, let-out computation, and carry-forward reporting."""

from india_tax_guru.house_property import compute_house_properties
from india_tax_guru.models import HouseProperty


def test_self_occupied_interest_cap_is_aggregate_not_per_property(rules):
    """Two self-occupied houses with 2,00,000 interest each still get 2,00,000 total."""
    props = [
        HouseProperty(is_self_occupied=True, home_loan_interest=200_000),
        HouseProperty(is_self_occupied=True, home_loan_interest=200_000),
    ]
    result = compute_house_properties(props, rules, rules.old_regime)
    assert result.net_income_or_loss == -200_000
    assert result.contribution_to_total_income == -200_000
    assert any("capped" in note for note in result.notes)


def test_single_self_occupied_within_cap(rules):
    props = [HouseProperty(is_self_occupied=True, home_loan_interest=150_000)]
    result = compute_house_properties(props, rules, rules.old_regime)
    assert result.contribution_to_total_income == -150_000


def test_let_out_property_income(rules):
    """NAV 2,80,000 less 30% (84,000) less interest 100,000 = 96,000 income."""
    props = [
        HouseProperty(
            is_self_occupied=False,
            annual_rent_received=300_000,
            municipal_taxes_paid=20_000,
            home_loan_interest=100_000,
        )
    ]
    result = compute_house_properties(props, rules, rules.old_regime)
    assert result.net_income_or_loss == 96_000
    assert result.contribution_to_total_income == 96_000
    assert result.carried_forward_loss == 0


def test_let_out_loss_capped_at_2l_with_remainder_carried_forward(rules):
    """NAV 2,80,000 less 84,000 less 600,000 interest = 404,000 loss."""
    props = [
        HouseProperty(
            is_self_occupied=False,
            annual_rent_received=300_000,
            municipal_taxes_paid=20_000,
            home_loan_interest=600_000,
        )
    ]
    result = compute_house_properties(props, rules, rules.old_regime)
    assert result.net_income_or_loss == -404_000
    assert result.contribution_to_total_income == -200_000
    assert result.carried_forward_loss == 204_000
    assert any("carried forward" in note for note in result.notes)


def test_setoff_cap_is_aggregate_across_properties(rules):
    """Two loss-making properties still surrender only 2,00,000 against other heads."""
    prop = HouseProperty(
        is_self_occupied=False,
        annual_rent_received=0,
        home_loan_interest=300_000,
    )
    result = compute_house_properties([prop, prop], rules, rules.old_regime)
    assert result.net_income_or_loss == -600_000
    assert result.contribution_to_total_income == -200_000
    assert result.carried_forward_loss == 400_000


def test_new_regime_disallows_self_occupied_interest_entirely(rules):
    props = [HouseProperty(is_self_occupied=True, home_loan_interest=200_000)]
    result = compute_house_properties(props, rules, rules.new_regime)
    assert result.contribution_to_total_income == 0
    assert any("new regime" in note for note in result.notes)


def test_new_regime_disallows_loss_setoff_but_reports_carry_forward(rules):
    props = [
        HouseProperty(
            is_self_occupied=False,
            annual_rent_received=300_000,
            municipal_taxes_paid=20_000,
            home_loan_interest=600_000,
        )
    ]
    result = compute_house_properties(props, rules, rules.new_regime)
    assert result.contribution_to_total_income == 0
    assert result.carried_forward_loss == 404_000


def test_let_out_income_is_still_taxable_in_new_regime(rules):
    """Disallowing the LOSS set-off must not also exempt let-out INCOME."""
    props = [
        HouseProperty(
            is_self_occupied=False,
            annual_rent_received=300_000,
            municipal_taxes_paid=20_000,
        )
    ]
    result = compute_house_properties(props, rules, rules.new_regime)
    assert result.contribution_to_total_income == 196_000


def test_no_properties_is_zero(rules):
    result = compute_house_properties([], rules, rules.old_regime)
    assert result.contribution_to_total_income == 0
    assert result.notes == []


def test_under_construction_flagged(rules):
    props = [
        HouseProperty(
            is_self_occupied=True, home_loan_interest=100_000, is_under_construction=True
        )
    ]
    result = compute_house_properties(props, rules, rules.old_regime)
    assert any("pre-construction" in note.lower() for note in result.notes)
