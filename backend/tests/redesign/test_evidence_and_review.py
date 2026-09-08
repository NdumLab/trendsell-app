"""Manual evidence, import-readiness review and server-computed gates (E06, N02, N03, D03).

Three reviewed problems meet here:

* there was no way to record evidence at all, so every product sat at zero confidence
  with a blocker pointing at a Data Health page that could not resolve it;
* the compliance gate could never be cleared — the Decision Room had a dropdown, and a
  self-entered assumption is not a classification;
* the gate inputs were constants, so nothing a workspace actually held could move them.

The rules these tests hold to: a typed number is user input and never an observation;
self-reported evidence alone cannot reach the confidence a GO needs; and only a reviewer
resolves compliance.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.compliance import DEFAULT_VALIDITY_DAYS
from app.db import Record, User
from app.evidence import MANUAL_ONLY_CAP, METHOD_VERSION
from conftest import HEADERS

AMAZON = 'https://www.amazon.com/dp/B0ABCDEFGH'
INPUTS = {'quantity': 300, 'unit_cost_usd': 8.4, 'fx_ngn': 1500, 'freight_ngn': 900000, 'duty_pct': 5,
          'import_tax_pct': 7.5, 'selling_price_ngn': 32000, 'channel_fee_pct': 5, 'returns_pct': 3,
          'marketing_ngn': 300000, 'fixed_cost_ngn': 150000, 'stress_pct': 10,
          'compliance': 'unresolved', 'channel': 'Direct sales', 'shipping': 'Air'}
REVIEW_REQUEST = {
    'specifications': '1500 W handheld garment steamer, 260 ml tank, 220 V, plastic housing, 0.9 kg.',
    'intended_use': 'Retail sale to consumers in Lagos',
    'question': 'Which classification applies, and does it need SONCAP certification before import?',
    'hs_code_candidate': '8451.30',
    'destination': 'NG',
}
APPROVAL = {
    'status': 'approved',
    'rationale': 'Classified as a domestic steam appliance; certification requirement confirmed against the '
                 'published import guidelines in force on the date below.',
    'hs_code': '8451.30.00',
    'requirements': ['SONCAP product certificate before shipment', 'Form M registration prior to import'],
    'sources': [{'title': 'Import guidelines, chapter 84', 'url': 'https://example-regulator.test/guidelines/84',
                 'publisher': 'Example regulator', 'effective_from': '2026-01-01'}],
    'validity_days': DEFAULT_VALIDITY_DAYS,
}


def days_ago(count):
    return (datetime.now(timezone.utc) - timedelta(days=count)).strftime('%Y-%m-%d')


def evidence_body(**overrides):
    return {'metric': 'Search interest', 'value': 68, 'unit': 'index / 100', 'market': 'US',
            'observed_at': days_ago(5), 'source_name': 'Google Trends export',
            'source_url': 'https://trends.google.com/trends/explore?q=garment%20steamer',
            'method': 'Exported the 12-month series for Nigeria and read the latest weekly point.',
            'notes': '', **overrides}


@pytest.fixture
def confirmed(client, owner):
    job = client.post('/api/v1/xray', json={'input': AMAZON}, headers={**HEADERS, 'Idempotency-Key': 'x'}).json()
    client.post(f'/api/v1/products/{job["product_id"]}/confirm', json={'name': 'Steamer'}, headers=HEADERS)
    return job['product_id']


@pytest.fixture
def reviewer(client, second_client, stranger, owner):
    """A reviewer inside the *owner's* workspace, since review is a workspace role."""
    with client.app.state.database.session() as db:
        user = db.query(User).filter_by(email='stranger@example.com').one()
        user.workspace_id = owner['workspace_id']
        user.role = 'reviewer'
        db.commit()
    return second_client


def record(client, product_id, **overrides):
    response = client.post(f'/api/v1/products/{product_id}/evidence', json=evidence_body(**overrides),
                           headers=HEADERS)
    assert response.status_code == 201, response.text
    return response.json()


def rich_evidence(client, product_id):
    """Enough dated, independent, current evidence to max the method's components."""
    record(client, product_id, metric='Search interest', source_name='Google Trends export', market='US')
    record(client, product_id, metric='Review velocity', value=14, unit='reviews / week',
           source_name='Marketplace listing page', market='US')
    record(client, product_id, metric='Marketplace rank', value=812, unit='rank in category',
           source_name='Marketplace category page', market='US')
    record(client, product_id, metric='Local listing price', value=27500, unit='NGN',
           source_name='Lagos market survey', market='NG')


# --- Recording evidence -------------------------------------------------------------

def test_a_recorded_number_is_user_input_and_never_an_observation(client, confirmed):
    body = record(client, confirmed)
    assert body['truth_state'] == 'User input'
    assert body['verification'] == 'Unverified'
    assert body['input_author']
    assert body['method'] and body['source_name'] and body['observed_at']


def test_the_caller_cannot_claim_its_number_was_observed(client, confirmed):
    response = client.post(f'/api/v1/products/{confirmed}/evidence',
                           json={**evidence_body(), 'truth_state': 'Observed'}, headers=HEADERS)
    assert response.status_code == 422, 'truth_state is set by the server, not the caller'


def test_evidence_requires_a_date_a_source_and_a_method(client, confirmed):
    for missing in ('observed_at', 'source_name', 'method', 'unit', 'metric'):
        body = evidence_body()
        body.pop(missing)
        assert client.post(f'/api/v1/products/{confirmed}/evidence', json=body,
                           headers=HEADERS).status_code == 422, missing


@pytest.mark.parametrize('bad', [
    {'observed_at': '2026-02-31'},
    {'observed_at': (datetime.now(timezone.utc) + timedelta(days=30)).strftime('%Y-%m-%d')},
    {'source_url': 'http://insecure.example.com'},
    {'market': 'FR'},
])
def test_unusable_evidence_is_refused(client, confirmed, bad):
    assert client.post(f'/api/v1/products/{confirmed}/evidence', json=evidence_body(**bad),
                       headers=HEADERS).status_code == 422


def test_recorded_evidence_appears_on_the_product_with_its_provenance(client, confirmed):
    stored = record(client, confirmed)
    body = client.get(f'/api/v1/products/{confirmed}/evidence').json()
    assert [o['id'] for o in body['observations']] == [stored['id']]
    assert body['truth_state'] == 'User input'
    assert 'entered by people in this workspace' in body['reason']


def test_a_product_with_no_evidence_says_unavailable_not_zero(client, confirmed):
    body = client.get(f'/api/v1/products/{confirmed}/evidence').json()
    assert body['observations'] == []
    assert body['truth_state'] == 'Unavailable'
    assert body['quality']['confidence'] == 0
    assert body['quality']['coverage'] is False


def test_withdrawing_a_record_removes_it_from_the_current_reading(client, confirmed):
    stored = record(client, confirmed)
    assert client.delete(f'/api/v1/products/{confirmed}/evidence/{stored["id"]}',
                         headers=HEADERS).status_code == 200
    assert client.get(f'/api/v1/products/{confirmed}/evidence').json()['observations'] == []


def test_evidence_is_scoped_to_its_workspace(client, confirmed, second_client, stranger):
    stored = record(client, confirmed)
    assert second_client.get(f'/api/v1/products/{confirmed}/evidence').status_code == 404
    assert second_client.post(f'/api/v1/products/{confirmed}/evidence', json=evidence_body(),
                              headers=HEADERS).status_code == 404
    assert second_client.delete(f'/api/v1/products/{confirmed}/evidence/{stored["id"]}',
                                headers=HEADERS).status_code == 404
    assert len(client.get(f'/api/v1/products/{confirmed}/evidence').json()['observations']) == 1


# --- The evidence-quality method ----------------------------------------------------

def test_the_method_explains_every_component_it_scored(client, confirmed):
    rich_evidence(client, confirmed)
    reading = client.get(f'/api/v1/products/{confirmed}/evidence').json()['quality']
    assert reading['method_version'] == METHOD_VERSION
    assert 'Not a probability' in reading['score_meaning']
    assert sum(component['points'] for component in reading['components']) == reading['raw_points']
    for component in reading['components']:
        assert component['detail'] and component['points'] <= component['max']


def test_self_reported_evidence_alone_cannot_reach_the_confidence_a_go_needs(client, confirmed):
    rich_evidence(client, confirmed)
    reading = client.get(f'/api/v1/products/{confirmed}/evidence').json()['quality']
    assert reading['raw_points'] > MANUAL_ONLY_CAP, 'the components should have scored above the cap'
    assert reading['confidence'] == MANUAL_ONLY_CAP
    assert reading['capped_at'] == MANUAL_ONLY_CAP
    assert reading['confidence'] < 70, 'a GO needs 70; typed numbers must not get there'
    assert any('self-reported' in limitation for limitation in reading['limitations'])


def test_evidence_outside_the_window_does_not_count_as_current(client, confirmed):
    record(client, confirmed, observed_at=days_ago(200))
    reading = client.get(f'/api/v1/products/{confirmed}/evidence').json()['quality']
    assert reading['records_total'] == 1
    assert reading['records_in_window'] == 0
    assert reading['confidence'] == 0
    assert any('within the last' in limitation for limitation in reading['limitations'])


def test_missing_destination_evidence_reduces_coverage_rather_than_helping(client, confirmed):
    record(client, confirmed, metric='Search interest', market='US')
    record(client, confirmed, metric='Review velocity', value=9, unit='reviews / week',
           source_name='Marketplace listing page', market='US')
    reading = client.get(f'/api/v1/products/{confirmed}/evidence').json()['quality']
    assert reading['coverage'] is False
    assert any('Missing local listings are not low competition' in l for l in reading['limitations'])


def test_a_viewer_cannot_record_evidence(client, confirmed, owner):
    with client.app.state.database.session() as db:
        db.query(User).filter_by(id=owner['id']).update({'role': 'viewer'})
        db.commit()
    assert client.post(f'/api/v1/products/{confirmed}/evidence', json=evidence_body(),
                       headers=HEADERS).status_code == 403


# --- Import-readiness review ---------------------------------------------------------

def test_a_product_starts_with_no_review_and_an_unresolved_gate(client, confirmed):
    body = client.get(f'/api/v1/products/{confirmed}/compliance').json()
    assert body['gate'] == {'resolved': False, 'status': 'none',
                            'reason': 'No import-readiness review has been requested for this product.'}
    assert body['current'] is None and body['history'] == []


def test_a_review_request_carries_the_context_the_reviewer_needs(client, confirmed):
    body = client.post(f'/api/v1/products/{confirmed}/compliance/requests',
                       json={**REVIEW_REQUEST, 'product_id': confirmed}, headers=HEADERS).json()
    assert body['status'] == 'requested'
    assert body['specifications'] and body['intended_use'] and body['question']
    assert body['hs_code_candidate'] == '8451.30'
    assert body['product_name'] == 'Steamer'
    assert client.get(f'/api/v1/products/{confirmed}/compliance').json()['gate']['status'] == 'requested'


def test_a_request_without_enough_context_is_refused(client, confirmed):
    for missing in ('specifications', 'question', 'intended_use'):
        body = {**REVIEW_REQUEST, 'product_id': confirmed}
        body[missing] = 'x'
        assert client.post(f'/api/v1/products/{confirmed}/compliance/requests', json=body,
                           headers=HEADERS).status_code == 422, missing


def test_an_analyst_cannot_decide_their_own_review(client, confirmed, owner):
    review = client.post(f'/api/v1/products/{confirmed}/compliance/requests',
                         json={**REVIEW_REQUEST, 'product_id': confirmed}, headers=HEADERS).json()
    with client.app.state.database.session() as db:
        db.query(User).filter_by(id=owner['id']).update({'role': 'analyst'})
        db.commit()
    response = client.post(f'/api/v1/compliance/reviews/{review["id"]}/decision', json=APPROVAL, headers=HEADERS)
    assert response.status_code == 403
    assert 'reviewer' in response.json()['detail']
    assert client.get(f'/api/v1/products/{confirmed}/compliance').json()['gate']['resolved'] is False


def test_a_reviewer_resolves_the_gate_and_the_decision_cites_its_sources(client, confirmed, reviewer):
    review = client.post(f'/api/v1/products/{confirmed}/compliance/requests',
                         json={**REVIEW_REQUEST, 'product_id': confirmed}, headers=HEADERS).json()
    decided = reviewer.post(f'/api/v1/compliance/reviews/{review["id"]}/decision', json=APPROVAL,
                            headers=HEADERS)
    assert decided.status_code == 200, decided.text
    body = decided.json()
    assert body['status'] == 'approved' and body['reviewer_id'] and body['decided_at'] and body['expires_at']
    assert body['sources'][0]['publisher'] == 'Example regulator'
    gate = client.get(f'/api/v1/products/{confirmed}/compliance').json()['gate']
    assert gate['resolved'] is True and gate['status'] == 'approved'
    assert gate['hs_code'] == '8451.30.00'
    assert 'SONCAP product certificate before shipment' in gate['requirements']


def test_an_approval_must_cite_official_sources(client, confirmed, reviewer):
    review = client.post(f'/api/v1/products/{confirmed}/compliance/requests',
                         json={**REVIEW_REQUEST, 'product_id': confirmed}, headers=HEADERS).json()
    response = reviewer.post(f'/api/v1/compliance/reviews/{review["id"]}/decision',
                             json={**APPROVAL, 'sources': []}, headers=HEADERS)
    assert response.status_code == 422
    assert 'official sources' in response.json()['detail']


def test_a_rejection_blocks_the_gate_and_says_so(client, confirmed, reviewer):
    review = client.post(f'/api/v1/products/{confirmed}/compliance/requests',
                         json={**REVIEW_REQUEST, 'product_id': confirmed}, headers=HEADERS).json()
    reviewer.post(f'/api/v1/compliance/reviews/{review["id"]}/decision',
                  json={'status': 'rejected', 'rationale': 'Prohibited for import under the cited notice.',
                        'sources': []}, headers=HEADERS)
    gate = client.get(f'/api/v1/products/{confirmed}/compliance').json()['gate']
    assert gate['resolved'] is False and gate['status'] == 'rejected'
    assert 'Do not proceed' in gate['reason']


def test_an_expired_approval_stops_resolving_the_gate(client, confirmed, reviewer):
    review = client.post(f'/api/v1/products/{confirmed}/compliance/requests',
                         json={**REVIEW_REQUEST, 'product_id': confirmed}, headers=HEADERS).json()
    reviewer.post(f'/api/v1/compliance/reviews/{review["id"]}/decision', json=APPROVAL, headers=HEADERS)
    with client.app.state.database.session() as db:
        row = db.query(Record).filter_by(id=review['id']).one()
        row.payload = {**row.payload, 'expires_at': (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()}
        db.commit()
    gate = client.get(f'/api/v1/products/{confirmed}/compliance').json()['gate']
    assert gate['resolved'] is False and gate['status'] == 'expired'
    assert 'Request a fresh review' in gate['reason']


def test_a_decided_review_is_superseded_rather_than_edited(client, confirmed, reviewer):
    first = client.post(f'/api/v1/products/{confirmed}/compliance/requests',
                        json={**REVIEW_REQUEST, 'product_id': confirmed}, headers=HEADERS).json()
    reviewer.post(f'/api/v1/compliance/reviews/{first["id"]}/decision', json=APPROVAL, headers=HEADERS)
    assert reviewer.post(f'/api/v1/compliance/reviews/{first["id"]}/decision', json=APPROVAL,
                         headers=HEADERS).status_code == 409

    second = client.post(f'/api/v1/products/{confirmed}/compliance/requests',
                         json={**REVIEW_REQUEST, 'product_id': confirmed}, headers=HEADERS).json()
    state = client.get(f'/api/v1/products/{confirmed}/compliance').json()
    assert state['current']['id'] == second['id']
    assert len(state['history']) == 2
    superseded = next(r for r in state['history'] if r['id'] == first['id'])
    assert superseded['superseded_by'] == second['id']
    assert superseded['status'] == 'approved', 'the prior decision is retained, not rewritten'
    assert superseded['rationale'] == APPROVAL['rationale']


def test_two_reviews_cannot_be_pending_at_once(client, confirmed):
    client.post(f'/api/v1/products/{confirmed}/compliance/requests',
                json={**REVIEW_REQUEST, 'product_id': confirmed}, headers=HEADERS)
    assert client.post(f'/api/v1/products/{confirmed}/compliance/requests',
                       json={**REVIEW_REQUEST, 'product_id': confirmed}, headers=HEADERS).status_code == 409


# --- The gate the decision actually uses (D03) ---------------------------------------

def test_a_saved_assessment_uses_the_workspace_records_not_the_client(client, confirmed, reviewer):
    rich_evidence(client, confirmed)
    review = client.post(f'/api/v1/products/{confirmed}/compliance/requests',
                         json={**REVIEW_REQUEST, 'product_id': confirmed}, headers=HEADERS).json()
    reviewer.post(f'/api/v1/compliance/reviews/{review["id"]}/decision', json=APPROVAL, headers=HEADERS)

    saved = client.post('/api/v1/decisions', json={'product_id': confirmed, 'inputs': INPUTS},
                        headers={**HEADERS, 'Idempotency-Key': 'd'}).json()
    assert saved['confidence'] == MANUAL_ONLY_CAP
    assert saved['evidence_quality']['method_version'] == METHOD_VERSION
    assert saved['compliance']['resolved'] is True
    assert saved['compliance_review_id'] == review['id']
    assert len(saved['evidence']) == 4
    assert {record['truth_state'] for record in saved['evidence']} == {'User input'}


def test_the_client_cannot_set_confidence_or_coverage(client, confirmed):
    """Anything the browser sends about evidence is ignored; the server reads records."""
    response = client.post('/api/v1/decisions',
                           json={'product_id': confirmed, 'inputs': INPUTS,
                                 'evidence': {'confidence': 99, 'coverage': True, 'compliance_resolved': True}},
                           headers={**HEADERS, 'Idempotency-Key': 'forged'})
    assert response.status_code == 422, 'unknown fields are rejected outright'
    saved = client.post('/api/v1/decisions', json={'product_id': confirmed, 'inputs': INPUTS},
                        headers={**HEADERS, 'Idempotency-Key': 'honest'}).json()
    assert saved['confidence'] == 0
    assert saved['decision'] == 'INSUFFICIENT EVIDENCE'


def test_a_reviewed_product_with_thin_evidence_still_cannot_be_a_go(client, confirmed, reviewer):
    """Resolving compliance is necessary, not sufficient."""
    record(client, confirmed, metric='Search interest', market='US')
    record(client, confirmed, metric='Local listing price', value=27500, unit='NGN',
           source_name='Lagos market survey', market='NG')
    review = client.post(f'/api/v1/products/{confirmed}/compliance/requests',
                         json={**REVIEW_REQUEST, 'product_id': confirmed}, headers=HEADERS).json()
    reviewer.post(f'/api/v1/compliance/reviews/{review["id"]}/decision', json=APPROVAL, headers=HEADERS)
    saved = client.post('/api/v1/decisions', json={'product_id': confirmed, 'inputs': INPUTS},
                        headers={**HEADERS, 'Idempotency-Key': 'thin'}).json()
    assert saved['decision'] != 'GO'
    assert saved['confidence'] < 70


def test_a_saved_assessment_keeps_the_evidence_it_was_calculated_from(client, confirmed):
    """Withdrawing a record later must not change what a saved assessment says."""
    rich_evidence(client, confirmed)
    saved = client.post('/api/v1/decisions', json={'product_id': confirmed, 'inputs': INPUTS},
                        headers={**HEADERS, 'Idempotency-Key': 'kept'}).json()
    recorded = client.get(f'/api/v1/products/{confirmed}/evidence').json()['observations']
    for record_row in recorded:
        client.delete(f'/api/v1/products/{confirmed}/evidence/{record_row["id"]}', headers=HEADERS)

    assert client.get(f'/api/v1/products/{confirmed}/evidence').json()['observations'] == []
    stored = client.get(f'/api/v1/decisions/{saved["id"]}').json()
    assert len(stored['evidence']) == 4
    assert stored['confidence'] == saved['confidence']
    assert stored['evidence_quality'] == saved['evidence_quality']


def test_recording_evidence_and_reviewing_are_both_audited(client, confirmed, reviewer):
    record(client, confirmed)
    review = client.post(f'/api/v1/products/{confirmed}/compliance/requests',
                         json={**REVIEW_REQUEST, 'product_id': confirmed}, headers=HEADERS).json()
    reviewer.post(f'/api/v1/compliance/reviews/{review["id"]}/decision', json=APPROVAL, headers=HEADERS)
    actions = {event['action']: event for event in client.get('/api/v1/audit').json()['events']}
    assert 'evidence.recorded' in actions
    assert actions['evidence.recorded']['detail']['metric'] == 'Search interest'
    assert 'compliance.review_requested' in actions
    assert actions['compliance.reviewed']['detail']['status'] == 'approved'
    assert actions['compliance.reviewed']['detail']['sources'] == 1


# --- R03: an approval must rest on support that actually applies ---------------------
#
# Review finding R03: effective dates were regex-checked, stored, shown — and never
# consulted. An approval citing a rule that stopped applying in 2011, naming no
# classification and listing no requirements, cleared the gate in September 2026.

EXPIRED_SOURCE = {'title': 'Withdrawn tariff schedule', 'url': 'https://example-regulator.test/withdrawn',
                  'publisher': 'Example regulator', 'effective_from': '2010-01-01',
                  'effective_to': '2011-01-01'}


def approve(client, review_id, **overrides):
    return client.post(f'/api/v1/compliance/reviews/{review_id}/decision',
                       json={**APPROVAL, **overrides}, headers=HEADERS)


@pytest.fixture
def requested(client, confirmed):
    """A review waiting for a decision."""
    response = client.post(f'/api/v1/products/{confirmed}/compliance/requests',
                           json={**REVIEW_REQUEST, 'product_id': confirmed}, headers=HEADERS)
    assert response.status_code == 201, response.text
    return response.json()['id']


def test_an_approval_on_expired_support_cannot_clear_the_gate(client, confirmed, requested, reviewer):
    """The review's exact reproduction: 2010-2011 support, no code, no requirements."""
    response = approve(client, requested, sources=[EXPIRED_SOURCE], hs_code='', requirements=[])
    assert response.status_code == 422, response.text

    gate = client.get(f'/api/v1/products/{confirmed}/compliance').json()['gate']
    assert gate['resolved'] is False


def test_an_approval_citing_only_expired_sources_is_refused(client, confirmed, requested, reviewer):
    response = approve(client, requested, sources=[EXPIRED_SOURCE])
    assert response.status_code == 422
    assert 'expired or not yet in force' in response.json()['detail']


def test_an_approval_citing_a_future_source_is_refused(client, confirmed, requested, reviewer):
    future = {**EXPIRED_SOURCE, 'effective_from': '2099-01-01', 'effective_to': None}
    response = approve(client, requested, sources=[future])
    assert response.status_code == 422
    assert 'expired or not yet in force' in response.json()['detail']


def test_an_approval_must_name_the_classification_it_reviewed(client, requested, reviewer):
    assert approve(client, requested, hs_code='').status_code == 422


def test_an_approval_with_no_requirements_must_say_so_deliberately(client, requested, reviewer):
    """An empty list is silence; a reviewer has to state that none apply."""
    assert approve(client, requested, requirements=[]).status_code == 422
    assert approve(client, requested, requirements=[], no_additional_requirements=True).status_code == 200


def test_a_source_period_must_be_real_and_ordered(client, requested, reviewer):
    impossible = {**EXPIRED_SOURCE, 'effective_from': '2026-13-45', 'effective_to': None}
    assert approve(client, requested, sources=[impossible]).status_code == 422
    backwards = {**EXPIRED_SOURCE, 'effective_from': '2026-06-01', 'effective_to': '2026-01-01'}
    assert approve(client, requested, sources=[backwards]).status_code == 422


def test_an_approval_never_outlives_the_support_it_cites(client, confirmed, requested, reviewer):
    """A source lapsing in 30 days ends the approval then, not in 180 days."""
    ends = (datetime.now(timezone.utc) + timedelta(days=30)).strftime('%Y-%m-%d')
    body = approve(client, requested, validity_days=DEFAULT_VALIDITY_DAYS,
                   sources=[{**APPROVAL['sources'][0], 'effective_to': ends}]).json()
    assert body['expires_at'][:10] == ends

    gate = client.get(f'/api/v1/products/{confirmed}/compliance').json()['gate']
    assert gate['resolved'] is True, 'it is still in force today'


def test_a_stored_approval_stops_resolving_once_its_support_lapses(client, confirmed, requested, reviewer):
    """Applied on read too, so an approval stored before this rule cannot outlive it."""
    approve(client, requested)
    assert client.get(f'/api/v1/products/{confirmed}/compliance').json()['gate']['resolved'] is True

    with client.app.state.database.session() as db:
        row = db.query(Record).filter_by(kind='compliance_review', id=requested).one()
        payload = dict(row.payload)
        payload['sources'] = [EXPIRED_SOURCE]
        row.payload = payload
        db.commit()

    gate = client.get(f'/api/v1/products/{confirmed}/compliance').json()['gate']
    assert gate['resolved'] is False
    assert gate['status'] == 'support_expired'


# --- R04: a reviewer's rejection decides the assessment ------------------------------
#
# Review finding R04: the gate said "a reviewer rejected this product for import; do not
# proceed" while the saved assessment beside it read WATCH at confidence 60, because the
# rejection reached the screen and never reached the calculation.

def test_a_rejected_review_forces_no_go_without_the_user_restating_it(client, confirmed, requested, reviewer):
    rich_evidence(client, confirmed)
    rejected = client.post(f'/api/v1/compliance/reviews/{requested}/decision',
                           json={'status': 'rejected',
                                 'rationale': 'Prohibited for import into the destination market.'},
                           headers=HEADERS)
    assert rejected.status_code == 200, rejected.text

    # The default dropdown value: the user is not asked to repeat the reviewer.
    saved = client.post('/api/v1/decisions', json={'product_id': confirmed, 'inputs': INPUTS},
                        headers={**HEADERS, 'Idempotency-Key': 'r04'})
    assert saved.status_code == 201, saved.text
    body = saved.json()
    assert body['inputs']['compliance'] == 'unresolved'
    assert body['decision'] == 'NO-GO'
    assert body['blockers'][0] == 'A reviewer rejected this product for import. Do not proceed.'
    assert body['compliance']['status'] == 'rejected'
    assert body['compliance_review_id'] == requested


def test_the_saved_assessment_and_its_gate_never_disagree(client, confirmed, requested, reviewer):
    """The disagreement the review reproduced: gate says stop, decision says WATCH."""
    rich_evidence(client, confirmed)
    client.post(f'/api/v1/compliance/reviews/{requested}/decision',
                json={'status': 'rejected', 'rationale': 'Not permitted for import as specified.'},
                headers=HEADERS)
    body = client.post('/api/v1/decisions', json={'product_id': confirmed, 'inputs': INPUTS},
                       headers={**HEADERS, 'Idempotency-Key': 'r04b'}).json()
    assert not (body['compliance']['status'] == 'rejected' and body['decision'] == 'WATCH')


def test_more_information_is_not_a_rejection(client, confirmed, requested, reviewer):
    rich_evidence(client, confirmed)
    client.post(f'/api/v1/compliance/reviews/{requested}/decision',
                json={'status': 'more_information', 'rationale': 'Send the full specification sheet.'},
                headers=HEADERS)
    body = client.post('/api/v1/decisions', json={'product_id': confirmed, 'inputs': INPUTS},
                       headers={**HEADERS, 'Idempotency-Key': 'r04c'}).json()
    assert body['decision'] != 'NO-GO'
    assert body['compliance']['status'] == 'more_information'


def test_a_saved_assessment_records_the_thresholds_that_decided_it(client, confirmed, requested, reviewer):
    """So a rejection recorded under these gates replays under these gates (R06)."""
    rich_evidence(client, confirmed)
    client.post(f'/api/v1/compliance/reviews/{requested}/decision',
                json={'status': 'rejected', 'rationale': 'Not permitted for import as specified.'},
                headers=HEADERS)
    body = client.post('/api/v1/decisions', json={'product_id': confirmed, 'inputs': INPUTS},
                       headers={**HEADERS, 'Idempotency-Key': 'r04d'}).json()
    assert body['threshold_version'] == 'decision-gates/1.1.0'
    assert body['evidence_quality']['compliance_status'] == 'rejected'
