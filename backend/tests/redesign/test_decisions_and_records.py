"""Saved decisions, supplier quotes and watches: reproducible, immutable, workspace-scoped."""
import pytest

from app.economics import FORMULA_VERSION, THRESHOLD_VERSION, Inputs, calculate
from conftest import HEADERS

AMAZON = 'https://www.amazon.com/dp/B0ABCDEFGH'
INPUTS = {'quantity': 300, 'unit_cost_usd': 8.4, 'fx_ngn': 1500, 'freight_ngn': 900000, 'duty_pct': 5,
          'import_tax_pct': 7.5, 'selling_price_ngn': 32000, 'channel_fee_pct': 5, 'returns_pct': 3,
          'marketing_ngn': 300000, 'fixed_cost_ngn': 150000, 'stress_pct': 10,
          'compliance': 'unresolved', 'channel': 'Direct sales', 'shipping': 'Air'}


@pytest.fixture
def product(client, owner):
    job = client.post('/api/v1/xray', json={'input': AMAZON}, headers={**HEADERS, 'Idempotency-Key': 'x'}).json()
    return job['product_id']


@pytest.fixture
def confirmed(client, product):
    client.post(f'/api/v1/products/{product}/confirm', json={'name': 'Portable garment steamer'}, headers=HEADERS)
    return product


def save(client, product_id, key='decision-1', inputs=None):
    return client.post('/api/v1/decisions', json={'product_id': product_id, 'inputs': inputs or INPUTS},
                       headers={**HEADERS, 'Idempotency-Key': key})


def test_a_decision_needs_a_confirmed_product(client, product):
    response = save(client, product)
    assert response.status_code == 409
    assert 'Confirm product identity' in response.json()['detail']


def test_a_saved_decision_keeps_its_inputs_and_versions(client, confirmed):
    saved = save(client, confirmed).json()
    assert saved['inputs'] == INPUTS
    assert saved['formula_version'] == FORMULA_VERSION
    assert saved['threshold_version'] == THRESHOLD_VERSION
    assert saved['input_truth_state'] == 'User input'
    assert saved['truth_state'] == 'Calculated'
    assert saved['created_at'] and saved['id']


def test_a_saved_decision_is_reproducible_from_its_stored_payload(client, confirmed):
    saved = client.get(f'/api/v1/decisions/{save(client, confirmed).json()["id"]}').json()
    replayed = calculate(Inputs(**saved['inputs']), formula_version=saved['formula_version'])
    for field in ('decision', 'scenarios', 'blockers', 'confidence', 'currency', 'market', 'formula_version'):
        assert replayed[field] == saved[field], field


def test_a_saved_decision_records_the_version_it_must_be_replayed_under(client, confirmed):
    """A stored assessment is replayed with its own formula version, never the current one."""
    saved = client.get(f'/api/v1/decisions/{save(client, confirmed).json()["id"]}').json()
    assert saved['formula_version'] in {'unit-economics/1.0.0', 'unit-economics/1.1.0'}
    under_legacy = calculate(Inputs(**saved['inputs']), formula_version='unit-economics/1.0.0')
    assert under_legacy['formula_version'] == 'unit-economics/1.0.0'
    assert under_legacy['formula_version'] != saved['formula_version']


def test_a_decision_without_observations_cannot_be_a_go(client, confirmed):
    saved = save(client, confirmed).json()
    assert saved['decision'] == 'INSUFFICIENT EVIDENCE'
    assert saved['confidence'] == 0
    assert saved['observation_ids'] == []
    assert saved['blockers']


def test_a_prohibited_status_is_refused_regardless_of_margin(client, confirmed):
    saved = save(client, confirmed, key='prohibited', inputs={**INPUTS, 'compliance': 'prohibited'}).json()
    assert saved['decision'] == 'NO-GO'


def test_saving_twice_with_one_key_returns_the_same_assessment(client, confirmed):
    first, second = save(client, confirmed).json(), save(client, confirmed).json()
    assert first['id'] == second['id']
    assert len(client.get('/api/v1/decisions').json()['decisions']) == 1


def test_a_reused_key_with_different_inputs_is_refused(client, confirmed):
    save(client, confirmed)
    conflict = save(client, confirmed, inputs={**INPUTS, 'quantity': 500})
    assert conflict.status_code == 409


def test_changing_inputs_creates_a_new_assessment_and_keeps_the_old_one(client, confirmed):
    first = save(client, confirmed, key='one').json()
    second = save(client, confirmed, key='two', inputs={**INPUTS, 'selling_price_ngn': 40000}).json()
    assert first['id'] != second['id']
    assert client.get(f'/api/v1/decisions/{first["id"]}').json()['inputs'] == INPUTS
    assert len(client.get('/api/v1/decisions').json()['decisions']) == 2


def test_out_of_range_and_unknown_inputs_are_rejected(client, confirmed):
    for bad in [{'quantity': 0}, {'selling_price_ngn': 0}, {'duty_pct': 140}, {'stress_pct': 90},
                {'fx_ngn': -1}, {'compliance': 'resolved'}, {'shipping': 'Rail'}, {'unexpected': 1}]:
        response = save(client, confirmed, key=f'bad-{list(bad)[0]}', inputs={**INPUTS, **bad})
        assert response.status_code == 422, bad


def test_an_idempotency_key_is_required_for_a_decision(client, confirmed):
    assert client.post('/api/v1/decisions', json={'product_id': confirmed, 'inputs': INPUTS}, headers=HEADERS).status_code == 422


def test_a_quote_is_stored_as_unverified_user_input(client, confirmed):
    quote = client.post('/api/v1/quotes', headers=HEADERS, json={
        'product_id': confirmed, 'supplier': 'Example Manufacturing Ltd', 'source_url': 'https://example.com/supplier',
        'unit_price_usd': 8.4, 'moq': 300, 'lead_days': 25, 'quote_date': '2026-09-01', 'incoterm': 'FOB', 'notes': 'Valid 30 days'}).json()
    assert quote['truth_state'] == 'User input'
    assert quote['verification'] == 'Unverified'
    assert quote['input_author']


def test_a_quote_needs_an_https_source_and_a_real_date(client, confirmed):
    base = {'product_id': confirmed, 'supplier': 'Example Manufacturing Ltd', 'source_url': 'https://example.com/s',
            'unit_price_usd': 8.4, 'moq': 300, 'lead_days': 25, 'quote_date': '2026-09-01', 'incoterm': 'FOB'}
    assert client.post('/api/v1/quotes', json={**base, 'source_url': 'http://example.com'}, headers=HEADERS).status_code == 422
    assert client.post('/api/v1/quotes', json={**base, 'quote_date': '2026-02-31'}, headers=HEADERS).status_code == 422
    assert client.post('/api/v1/quotes', json={**base, 'unit_price_usd': 0}, headers=HEADERS).status_code == 422


def test_a_quote_must_belong_to_a_product_in_the_workspace(client, owner):
    response = client.post('/api/v1/quotes', headers=HEADERS, json={
        'product_id': 'not-a-product', 'supplier': 'Example Ltd', 'source_url': 'https://example.com/s',
        'unit_price_usd': 8.4, 'moq': 300, 'lead_days': 25, 'quote_date': '2026-09-01'})
    assert response.status_code == 404


def test_watching_a_product_twice_updates_one_rule(client, confirmed):
    first = client.post('/api/v1/watchlists/default/items', json={'product_id': confirmed, 'threshold_pct': 15}, headers=HEADERS).json()
    second = client.post('/api/v1/watchlists/default/items', json={'product_id': confirmed, 'threshold_pct': 25}, headers=HEADERS).json()
    items = client.get('/api/v1/watchlists/default/items').json()['items']
    assert first['id'] == second['id']
    assert len(items) == 1
    assert items[0]['threshold_pct'] == 25
    assert items[0]['scheduled'] is False


def test_a_watch_declares_that_collection_is_not_scheduled(client, confirmed):
    watch = client.post('/api/v1/watchlists/default/items', json={'product_id': confirmed}, headers=HEADERS).json()
    assert watch['scheduled'] is False
    assert watch['status'] == 'Awaiting evidence'


def test_a_watch_threshold_is_validated(client, confirmed):
    for bad in (0, 101):
        assert client.post('/api/v1/watchlists/default/items', json={'product_id': confirmed, 'threshold_pct': bad}, headers=HEADERS).status_code == 422


def test_removing_a_watch_is_scoped_to_the_workspace(client, confirmed):
    watch = client.post('/api/v1/watchlists/default/items', json={'product_id': confirmed}, headers=HEADERS).json()
    assert client.delete(f'/api/v1/watchlists/default/items/{watch["id"]}', headers=HEADERS).status_code == 200
    assert client.delete(f'/api/v1/watchlists/default/items/{watch["id"]}', headers=HEADERS).status_code == 404
