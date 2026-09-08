"""The saved-decision contract. The frontend asserts the same files in economics.contract.test.ts."""
import json
from pathlib import Path

import pytest

from app import money as m
from app.economics import FORMULA_VERSION, THRESHOLD_VERSION, Inputs, calculate

CONTRACTS = Path(__file__).resolve().parents[3] / 'contracts'
CONTRACT = json.loads((CONTRACTS / 'economics_cases.json').read_text())
LEGACY = json.loads((CONTRACTS / 'economics_legacy_cases.json').read_text())
CASES = [pytest.param(case, id=case['name']) for case in CONTRACT['cases']]
LEGACY_CASES = [pytest.param(case, id=case['name']) for case in LEGACY['cases']]


def test_contract_pins_the_current_formula_version():
    assert CONTRACT['formula_version'] == FORMULA_VERSION
    assert CONTRACT['threshold_version'] == THRESHOLD_VERSION


@pytest.mark.parametrize('case', CASES)
def test_case_reproduces_exactly(case):
    assert calculate(Inputs(**case['inputs']), case['evidence']) == case['expected']


@pytest.mark.parametrize('case', CASES)
def test_case_is_deterministic(case):
    inputs = Inputs(**case['inputs'])
    assert calculate(inputs, case['evidence']) == calculate(inputs, case['evidence'])


@pytest.mark.parametrize('case', CASES)
def test_every_money_value_is_rounded_to_two_places(case):
    for scenario in case['expected']['scenarios']:
        for key, value in scenario.items():
            if isinstance(value, float):
                assert round(value, 2) == value, f'{case["name"]}.{scenario["name"]}.{key}'


def test_all_four_decision_states_are_covered():
    assert {case['expected']['decision'] for case in CONTRACT['cases']} == {'GO', 'WATCH', 'NO-GO', 'INSUFFICIENT EVIDENCE'}


def test_prohibited_status_always_blocks_regardless_of_margin():
    case = next(c for c in CONTRACT['cases'] if c['inputs']['compliance'] == 'prohibited')
    assert case['expected']['scenarios'][1]['margin_pct'] > 25
    assert case['expected']['decision'] == 'NO-GO'
    assert case['expected']['blockers'][0].startswith('The product is marked prohibited')


def test_go_requires_resolved_compliance_and_confidence():
    for case in CONTRACT['cases']:
        if case['expected']['decision'] == 'GO':
            assert case['evidence']['compliance_resolved'] is True
            assert case['evidence']['confidence'] >= 70
            assert case['expected']['blockers'] == []


def test_scenarios_are_ordered_downside_base_upside():
    for case in CONTRACT['cases']:
        assert [s['name'] for s in case['expected']['scenarios']] == ['Downside', 'Base', 'Upside']


def test_break_even_units_is_none_when_the_unit_cannot_cover_itself():
    case = next(c for c in CONTRACT['cases'] if c['name'] == 'negative-contribution')
    assert case['expected']['scenarios'][1]['break_even_units'] is None


def test_inputs_are_stored_with_the_assessment():
    for case in CONTRACT['cases']:
        assert case['expected']['inputs'] == case['inputs']
        assert case['expected']['input_truth_state'] == 'User input'
        assert case['expected']['truth_state'] == 'Calculated'


def test_the_reviewed_rounding_disagreement_is_pinned():
    """Python reported 10.08 and JavaScript 10.07 for the same inputs (review finding 5)."""
    case = next(c for c in CONTRACT['cases'] if c['name'] == 'review-repro-half-cent-supplier-cost')
    assert case['inputs']['unit_cost_usd'] == 10.075
    assert case['expected']['scenarios'][1]['supplier'] == 10.08


# --- Replay of superseded formula versions -----------------------------------------

def test_the_legacy_contract_is_frozen_at_its_own_version():
    assert LEGACY['formula_version'] == 'unit-economics/1.0.0'
    assert LEGACY['formula_version'] != FORMULA_VERSION


@pytest.mark.parametrize('case', LEGACY_CASES)
def test_a_legacy_assessment_still_replays_to_its_saved_values(case):
    replayed = calculate(Inputs(**case['inputs']), case['evidence'], formula_version=LEGACY['formula_version'])
    assert replayed == case['expected']


def test_replaying_under_an_unknown_version_is_refused():
    with pytest.raises(ValueError):
        calculate(Inputs(**CONTRACT['cases'][0]['inputs']), formula_version='unit-economics/9.9.9')


def test_the_current_version_is_used_by_default():
    inputs = Inputs(**CONTRACT['cases'][0]['inputs'])
    assert calculate(inputs)['formula_version'] == FORMULA_VERSION


# --- The shared decimal primitives -------------------------------------------------

@pytest.mark.parametrize('text,expected', [
    ('0', 0), ('1', m.UNIT), ('-1', -m.UNIT), ('0.5', m.UNIT // 2), ('-0.5', -m.UNIT // 2),
    ('1e-12', 1), ('1E+3', 1000 * m.UNIT), ('  2.5  ', m.UNIT * 5 // 2),
    ('0.0000000000005', 1),   # half a unit rounds away from zero
    ('-0.0000000000005', -1),
    ('0.0000000000004', 0),
])
def test_decimal_strings_scale_as_documented(text, expected):
    assert m.from_decimal_string(text) == expected


@pytest.mark.parametrize('numerator,denominator,expected', [
    (5, 10, 1), (-5, 10, -1), (4, 10, 0), (-4, 10, 0), (15, 10, 2), (-15, 10, -2),
    (5, -10, -1), (0, 7, 0),
])
def test_division_rounds_half_away_from_zero(numerator, denominator, expected):
    assert m.div_round(numerator, denominator) == expected


@pytest.mark.parametrize('value', [0, 0.01, -0.01, 8.4, 10.075, -10.075, 1e12, 1e-6, 123456.789])
def test_a_float_round_trips_through_the_scaled_representation(value):
    assert m.to_float(m.quantize(m.parse(value), 12)) == float(value)


def test_money_quantises_to_two_places_in_both_directions():
    assert m.money(m.parse('10.075')) == 10.08
    assert m.money(m.parse('-10.075')) == -10.08
    assert m.money(m.parse('10.074')) == 10.07
    assert m.money(m.parse('10.085')) == 10.09


def test_ceil_units_matches_mathematical_ceiling():
    assert m.ceil_units(m.parse('2')) == 2
    assert m.ceil_units(m.parse('2.0000000001')) == 3
    assert m.ceil_units(m.parse('-1.5')) == -1
    assert m.ceil_units(m.parse('0')) == 0


EXACT_MONEY_LIMIT = (2 ** 53 - 1) / 100


def test_the_documented_exact_money_limit_is_stated_rather_than_implied():
    """Above this magnitude a JSON number cannot carry two decimal places on either side.

    The two implementations still agree exactly there — the parity case covers it — but a
    reader must not take cents off a figure that large.
    """
    extreme = next(c for c in CONTRACT['cases'] if c['name'] == 'accepted-range-maximums')
    assert extreme['expected']['scenarios'][1]['cash_required'] > EXACT_MONEY_LIMIT
    modest = next(c for c in CONTRACT['cases'] if c['name'] == 'worked-example-no-evidence')
    for value in modest['expected']['scenarios'][1].values():
        if isinstance(value, float):
            assert abs(value) <= EXACT_MONEY_LIMIT


def test_a_boolean_is_not_a_number():
    with pytest.raises(TypeError):
        m.parse(True)
