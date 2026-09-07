"""The saved-decision contract. The frontend asserts the same file in economics.contract.test.ts."""
import json
from pathlib import Path

import pytest

from app.economics import FORMULA_VERSION, Inputs, calculate

CONTRACT = json.loads((Path(__file__).resolve().parents[3] / 'contracts' / 'economics_cases.json').read_text())
CASES = [pytest.param(case, id=case['name']) for case in CONTRACT['cases']]


def test_contract_pins_the_current_formula_version():
    assert CONTRACT['formula_version'] == FORMULA_VERSION


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
