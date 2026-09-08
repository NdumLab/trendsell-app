"""Cross-workspace isolation against one shared database (action plan T01).

Every test here signs two owners into the *same* application and database and only
separates their session cookies. Each case follows the same three steps:

1. assert the owner's record really exists and is readable by its owner,
2. assert the stranger's read/write/delete of that record fails,
3. assert the owner's record is byte-for-byte unchanged afterwards.

Step 1 and step 3 are what the previous fixtures could not do: with a second app and
its own in-memory engine a 404 proved only that the row was never there.
"""
import pytest

from conftest import HEADERS

AMAZON = 'https://www.amazon.com/dp/B0ABCDEFGH'
OTHER_AMAZON = 'https://www.amazon.com/dp/B0ZZZZZZZZ'
INPUTS = {'quantity': 300, 'unit_cost_usd': 8.4, 'fx_ngn': 1500, 'freight_ngn': 900000, 'duty_pct': 5,
          'import_tax_pct': 7.5, 'selling_price_ngn': 32000, 'channel_fee_pct': 5, 'returns_pct': 3,
          'marketing_ngn': 300000, 'fixed_cost_ngn': 150000, 'stress_pct': 10,
          'compliance': 'unresolved', 'channel': 'Direct sales', 'shipping': 'Air'}
QUOTE = {'supplier': 'Example Manufacturing Ltd', 'source_url': 'https://example.com/supplier',
         'unit_price_usd': 8.4, 'moq': 300, 'lead_days': 25, 'quote_date': '2026-09-01', 'incoterm': 'FOB'}


@pytest.fixture
def workspace(client, owner):
    """A populated workspace: product, job, confirmed identity, decision, quote and watch."""
    job = client.post('/api/v1/xray', json={'input': AMAZON}, headers={**HEADERS, 'Idempotency-Key': 'owner-job'}).json()
    product_id = job['product_id']
    client.post(f'/api/v1/products/{product_id}/confirm', json={'name': 'Portable garment steamer'}, headers=HEADERS)
    decision = client.post('/api/v1/decisions', json={'product_id': product_id, 'inputs': INPUTS},
                           headers={**HEADERS, 'Idempotency-Key': 'owner-decision'}).json()
    quote = client.post('/api/v1/quotes', json={**QUOTE, 'product_id': product_id}, headers=HEADERS).json()
    watch = client.post('/api/v1/watchlists/default/items', json={'product_id': product_id, 'threshold_pct': 15},
                        headers=HEADERS).json()
    return {'product': product_id, 'job': job['id'], 'decision': decision['id'],
            'quote': quote['id'], 'watch': watch['id']}


@pytest.fixture
def populated_stranger(second_client, stranger):
    """The other workspace has its own records, so both tenants coexist in one database."""
    job = second_client.post('/api/v1/xray', json={'input': OTHER_AMAZON},
                             headers={**HEADERS, 'Idempotency-Key': 'stranger-job'}).json()
    second_client.post(f'/api/v1/products/{job["product_id"]}/confirm', json={'name': 'Sunset lamp'}, headers=HEADERS)
    return job['product_id']


def snapshot(client, workspace):
    """Everything the owner can see, so an unauthorised call can be shown to change nothing."""
    return {
        'product': client.get(f'/api/v1/products/{workspace["product"]}').json(),
        'products': client.get('/api/v1/products').json(),
        'job': client.get(f'/api/v1/research-jobs/{workspace["job"]}').json(),
        'decision': client.get(f'/api/v1/decisions/{workspace["decision"]}').json(),
        'decisions': client.get('/api/v1/decisions').json(),
        'quotes': client.get('/api/v1/quotes').json(),
        'watches': client.get('/api/v1/watchlists/default/items').json(),
    }


def test_both_workspaces_exist_in_one_database(client, workspace, second_client, populated_stranger):
    """The premise of every other test in this module."""
    assert client.get(f'/api/v1/products/{workspace["product"]}').status_code == 200
    assert second_client.get(f'/api/v1/products/{populated_stranger}').status_code == 200
    assert client.app is second_client.app
    assert [p['id'] for p in client.get('/api/v1/products').json()['products']] == [workspace['product']]
    assert [p['id'] for p in second_client.get('/api/v1/products').json()['products']] == [populated_stranger]


def test_a_stranger_cannot_read_any_record_of_another_workspace(client, workspace, second_client, stranger):
    before = snapshot(client, workspace)
    for path in [f'/api/v1/products/{workspace["product"]}',
                 f'/api/v1/products/{workspace["product"]}/evidence',
                 f'/api/v1/products/{workspace["product"]}/timeline',
                 f'/api/v1/research-jobs/{workspace["job"]}',
                 f'/api/v1/research-jobs/{workspace["job"]}/events',
                 f'/api/v1/decisions/{workspace["decision"]}']:
        assert second_client.get(path).status_code == 404, path
    assert second_client.get('/api/v1/products').json()['products'] == []
    assert second_client.get('/api/v1/decisions').json()['decisions'] == []
    assert second_client.get('/api/v1/quotes').json()['quotes'] == []
    assert second_client.get('/api/v1/watchlists/default/items').json()['items'] == []
    assert snapshot(client, workspace) == before


def test_a_stranger_cannot_write_to_another_workspaces_records(client, workspace, second_client, stranger):
    before = snapshot(client, workspace)
    writes = [
        ('post', f'/api/v1/products/{workspace["product"]}/confirm', {'name': 'Renamed by a stranger'}, {}),
        ('post', f'/api/v1/products/{workspace["product"]}/refresh', {}, {'Idempotency-Key': 'stranger-refresh'}),
        ('post', '/api/v1/decisions', {'product_id': workspace['product'], 'inputs': INPUTS},
         {'Idempotency-Key': 'stranger-decision'}),
        ('post', '/api/v1/quotes', {**QUOTE, 'product_id': workspace['product']}, {}),
        ('post', '/api/v1/watchlists/default/items', {'product_id': workspace['product'], 'threshold_pct': 90}, {}),
    ]
    for method, path, body, extra in writes:
        response = getattr(second_client, method)(path, json=body, headers={**HEADERS, **extra})
        assert response.status_code == 404, (path, response.status_code, response.text)
    assert second_client.delete(f'/api/v1/watchlists/default/items/{workspace["watch"]}',
                                headers=HEADERS).status_code == 404
    after = snapshot(client, workspace)
    assert after == before
    assert after['product']['name'] == 'Portable garment steamer'
    assert after['watches']['items'][0]['threshold_pct'] == 15


def test_an_idempotency_key_is_scoped_to_its_workspace(client, workspace, second_client, stranger):
    """Reusing the owner's key must create the stranger's own record, never return the owner's."""
    job = second_client.post('/api/v1/xray', json={'input': OTHER_AMAZON},
                             headers={**HEADERS, 'Idempotency-Key': 'owner-job'})
    assert job.status_code == 202
    assert job.json()['id'] != workspace['job']
    assert job.json()['product_id'] != workspace['product']
    assert client.get(f'/api/v1/research-jobs/{workspace["job"]}').json()['id'] == workspace['job']


def test_a_decision_key_collision_across_workspaces_does_not_leak(client, workspace, second_client, populated_stranger):
    saved = second_client.post('/api/v1/decisions', json={'product_id': populated_stranger, 'inputs': INPUTS},
                               headers={**HEADERS, 'Idempotency-Key': 'owner-decision'})
    assert saved.status_code == 201
    assert saved.json()['id'] != workspace['decision']
    assert saved.json()['product_id'] == populated_stranger
    assert [d['id'] for d in client.get('/api/v1/decisions').json()['decisions']] == [workspace['decision']]


def test_the_audit_log_never_shows_another_workspaces_events(client, workspace, second_client, populated_stranger):
    owner_events = client.get('/api/v1/audit').json()['events']
    stranger_events = second_client.get('/api/v1/audit').json()['events']
    owner_records = {event['record_id'] for event in owner_events}
    stranger_records = {event['record_id'] for event in stranger_events}
    assert workspace['product'] in owner_records
    assert workspace['product'] not in stranger_records
    assert populated_stranger in stranger_records
    assert populated_stranger not in owner_records


def test_a_signed_out_client_reaches_nothing(client, workspace, second_client):
    for path in [f'/api/v1/products/{workspace["product"]}', f'/api/v1/decisions/{workspace["decision"]}',
                 f'/api/v1/research-jobs/{workspace["job"]}', '/api/v1/products', '/api/v1/audit']:
        assert second_client.get(path).status_code == 401, path


def test_rate_limits_are_per_workspace_not_global(client, workspace, second_client, stranger, settings):
    """One workspace exhausting its research quota must not block another."""
    for index in range(settings.research_daily_limit):
        client.post('/api/v1/xray', json={'input': AMAZON}, headers={**HEADERS, 'Idempotency-Key': f'burn-{index}'})
    assert client.post('/api/v1/xray', json={'input': AMAZON},
                       headers={**HEADERS, 'Idempotency-Key': 'burn-over'}).status_code == 429
    assert second_client.post('/api/v1/xray', json={'input': OTHER_AMAZON},
                              headers={**HEADERS, 'Idempotency-Key': 'stranger-ok'}).status_code == 202
