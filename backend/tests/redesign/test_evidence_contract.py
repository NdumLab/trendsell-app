"""The shared evidence-quality contract (action plan E07).

The browser only runs this method for the demo — a real workspace reads the reading from
the server — but the demo GO example has to pass the *production* method rather than a
friendlier copy of it, so the two implementations are held together the same way the
economics are. `frontend/src/lib/evidence.contract.test.ts` asserts the same file.
"""
import json
from datetime import datetime
from pathlib import Path

import pytest

from app.evidence import MANUAL_ONLY_CAP, METHOD_VERSION, quality

CONTRACT = json.loads((Path(__file__).resolve().parents[3] / 'contracts' / 'evidence_cases.json').read_text())
EVALUATED_AT = datetime.fromisoformat(CONTRACT['evaluated_at'])
CASES = [pytest.param(case, id=case['name']) for case in CONTRACT['cases']]


def test_the_contract_pins_the_current_method_version():
    assert CONTRACT['method_version'] == METHOD_VERSION


@pytest.mark.parametrize('case', CASES)
def test_case_reproduces_exactly(case):
    assert quality(case['records'], case['compliance_resolved'], EVALUATED_AT) == case['expected']


@pytest.mark.parametrize('case', CASES)
def test_every_component_is_explained_and_within_its_maximum(case):
    expected = case['expected']
    assert sum(component['points'] for component in expected['components']) == expected['raw_points']
    for component in expected['components']:
        assert component['detail'], component['name']
        assert 0 <= component['points'] <= component['max']


def test_the_score_is_labelled_as_coverage_not_probability():
    for case in CONTRACT['cases']:
        assert 'Not a probability' in case['expected']['score_meaning']


def test_self_reported_evidence_is_capped_below_the_go_threshold():
    capped = next(c for c in CONTRACT['cases'] if c['name'] == 'manual-rich-but-capped')
    assert capped['expected']['raw_points'] > MANUAL_ONLY_CAP
    assert capped['expected']['confidence'] == MANUAL_ONLY_CAP
    assert capped['expected']['confidence'] < 70, 'a GO needs 70'


def test_a_resolved_review_does_not_by_itself_raise_the_score():
    """Compliance is a separate gate; approving it must not inflate evidence coverage."""
    without = next(c for c in CONTRACT['cases'] if c['name'] == 'manual-rich-but-capped')
    with_review = next(c for c in CONTRACT['cases'] if c['name'] == 'manual-rich-with-approved-review')
    assert with_review['expected']['compliance_resolved'] is True
    assert with_review['expected']['confidence'] == without['expected']['confidence']


def test_a_collected_observation_is_what_lifts_the_cap():
    lifted = next(c for c in CONTRACT['cases'] if c['name'] == 'collected-lifts-the-cap')
    assert lifted['expected']['capped_at'] is None
    assert lifted['expected']['confidence'] == lifted['expected']['raw_points'] == 100


def test_stale_evidence_scores_nothing_and_says_why():
    stale = next(c for c in CONTRACT['cases'] if c['name'] == 'stale-records-score-nothing')
    assert stale['expected']['records_total'] == 2
    assert stale['expected']['records_in_window'] == 0
    assert stale['expected']['confidence'] == 0
    assert any('within the last' in limitation for limitation in stale['expected']['limitations'])


def test_one_source_across_many_metrics_scores_less_than_many_sources():
    single = next(c for c in CONTRACT['cases'] if c['name'] == 'one-source-many-metrics')
    many = next(c for c in CONTRACT['cases'] if c['name'] == 'manual-rich-but-capped')
    assert single['expected']['raw_points'] < many['expected']['raw_points']


def test_missing_evidence_is_never_treated_as_favourable():
    """Nothing about an empty ledger may look better than a populated one."""
    empty = next(c for c in CONTRACT['cases'] if c['name'] == 'no-records')
    assert empty['expected']['confidence'] == 0
    assert empty['expected']['coverage'] is False
    assert empty['expected']['overall'] == 0
    assert empty['expected']['observation_ids'] == []
