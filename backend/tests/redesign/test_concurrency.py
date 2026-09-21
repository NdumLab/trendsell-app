"""Concurrent submissions converge on one record (action plan T06).

Review finding 4: six simultaneous X-Ray submissions carrying the same input and the
same idempotency key produced one HTTP 500 and five 202s. `insert()` flushed — and so
raised IntegrityError — before the `try/except` around `queue_job()`'s commit ever ran.

These tests fire genuinely parallel requests through a thread pool against one app and
one database. They run on SQLite by default and on PostgreSQL when TEST_POSTGRES_URL is
configured, because the two engines report unique-constraint races differently.
"""
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from conftest import HEADERS, POSTGRES_URL, postgres_schema_url, register

AMAZON = 'https://www.amazon.com/dp/B0ABCDEFGH'
INPUTS = {'quantity': 300, 'unit_cost_usd': 8.4, 'fx_ngn': 1500, 'freight_ngn': 900000, 'duty_pct': 5,
          'import_tax_pct': 7.5, 'selling_price_ngn': 32000, 'channel_fee_pct': 5, 'returns_pct': 3,
          'marketing_ngn': 300000, 'fixed_cost_ngn': 150000, 'stress_pct': 10,
          'compliance': 'unresolved', 'channel': 'Direct sales', 'shipping': 'Air'}
PARALLEL = 6


@pytest.fixture
def database_url(tmp_path):
    """A database that genuinely supports concurrent connections.

    The rest of the suite uses `sqlite://` on a StaticPool, which is one connection
    shared by every thread — that cannot express a race between two requests. Here the
    fallback is a file-backed SQLite database so each thread opens its own connection.
    """
    if not POSTGRES_URL:
        yield f'sqlite:///{tmp_path / "concurrency.db"}'
        return
    url, drop = postgres_schema_url(POSTGRES_URL)
    try:
        yield url
    finally:
        drop()


def burst(call, times=PARALLEL):
    """Fire `times` requests at once and return every response, exceptions included."""
    with ThreadPoolExecutor(max_workers=times) as pool:
        return [future.result() for future in [pool.submit(call, index) for index in range(times)]]


@pytest.fixture
def clients(app):
    """Several clients sharing one signed-in session, so requests really run in parallel."""
    with TestClient(app) as first:
        register(first)
        others = []
        for _ in range(PARALLEL - 1):
            other = TestClient(app)
            other.cookies.update(first.cookies)
            others.append(other)
        yield [first, *others]


def test_parallel_identical_xray_submissions_never_return_500(clients):
    responses = burst(lambda i: clients[i].post('/api/v1/xray', json={'input': AMAZON},
                                                headers={**HEADERS, 'Idempotency-Key': 'one-logical-submission'}))
    codes = sorted(r.status_code for r in responses)
    assert all(code == 202 for code in codes), [(r.status_code, r.text) for r in responses]
    assert len({r.json()['id'] for r in responses}) == 1
    assert len(clients[0].get('/api/v1/products').json()['products']) == 1


def test_parallel_submissions_of_the_same_product_share_one_canonical_product(clients):
    responses = burst(lambda i: clients[i].post('/api/v1/xray', json={'input': AMAZON},
                                                headers={**HEADERS, 'Idempotency-Key': f'distinct-{i}'}))
    assert [r.status_code for r in responses] == [202] * PARALLEL
    assert len({r.json()['product_id'] for r in responses}) == 1
    assert len(clients[0].get('/api/v1/products').json()['products']) == 1


def test_one_logical_submission_charges_the_research_quota_once(clients, settings):
    """Losing the insert race must not consume a second research entitlement."""
    burst(lambda i: clients[i].post('/api/v1/xray', json={'input': AMAZON},
                                    headers={**HEADERS, 'Idempotency-Key': 'charged-once'}))
    remaining = []
    for index in range(settings.research_daily_limit):
        response = clients[0].post('/api/v1/xray', json={'input': AMAZON},
                                   headers={**HEADERS, 'Idempotency-Key': f'after-{index}'})
        remaining.append(response.status_code)
    assert remaining.count(202) == settings.research_daily_limit - 1
    assert remaining[-1] == 429


def test_a_reused_key_with_a_different_request_still_returns_409(clients):
    assert clients[0].post('/api/v1/xray', json={'input': AMAZON},
                           headers={**HEADERS, 'Idempotency-Key': 'taken'}).status_code == 202
    conflict = clients[1].post('/api/v1/xray', json={'input': 'B0ZZZZZZZZ'},
                               headers={**HEADERS, 'Idempotency-Key': 'taken'})
    assert conflict.status_code == 409


def test_parallel_decisions_with_one_key_save_a_single_assessment(clients):
    job = clients[0].post('/api/v1/xray', json={'input': AMAZON}, headers={**HEADERS, 'Idempotency-Key': 'p'}).json()
    clients[0].post(f'/api/v1/products/{job["product_id"]}/confirm', json={'name': 'Steamer'}, headers=HEADERS)
    responses = burst(lambda i: clients[i].post('/api/v1/decisions',
                                                json={'product_id': job['product_id'], 'inputs': INPUTS},
                                                headers={**HEADERS, 'Idempotency-Key': 'one-decision'}))
    assert all(r.status_code in {200, 201} for r in responses), [(r.status_code, r.text) for r in responses]
    assert len({r.json()['id'] for r in responses}) == 1
    assert len(clients[0].get('/api/v1/decisions').json()['decisions']) == 1


def test_an_ambiguous_timeout_retry_does_not_duplicate_a_decision(clients):
    """The client must keep one key across retries; the server must then save once."""
    job = clients[0].post('/api/v1/xray', json={'input': AMAZON}, headers={**HEADERS, 'Idempotency-Key': 'p'}).json()
    clients[0].post(f'/api/v1/products/{job["product_id"]}/confirm', json={'name': 'Steamer'}, headers=HEADERS)
    body = {'product_id': job['product_id'], 'inputs': INPUTS}
    first = clients[0].post('/api/v1/decisions', json=body, headers={**HEADERS, 'Idempotency-Key': 'retried'})
    retry = clients[0].post('/api/v1/decisions', json=body, headers={**HEADERS, 'Idempotency-Key': 'retried'})
    assert first.status_code == 201
    assert retry.json()['id'] == first.json()['id']
    assert len(clients[0].get('/api/v1/decisions').json()['decisions']) == 1


def test_a_reused_decision_key_with_different_inputs_returns_409(clients):
    job = clients[0].post('/api/v1/xray', json={'input': AMAZON}, headers={**HEADERS, 'Idempotency-Key': 'p'}).json()
    clients[0].post(f'/api/v1/products/{job["product_id"]}/confirm', json={'name': 'Steamer'}, headers=HEADERS)
    clients[0].post('/api/v1/decisions', json={'product_id': job['product_id'], 'inputs': INPUTS},
                    headers={**HEADERS, 'Idempotency-Key': 'shared'})
    conflict = clients[0].post('/api/v1/decisions',
                               json={'product_id': job['product_id'], 'inputs': {**INPUTS, 'quantity': 999}},
                               headers={**HEADERS, 'Idempotency-Key': 'shared'})
    assert conflict.status_code == 409


def test_parallel_watches_on_one_product_create_one_rule(clients):
    job = clients[0].post('/api/v1/xray', json={'input': AMAZON}, headers={**HEADERS, 'Idempotency-Key': 'p'}).json()
    responses = burst(lambda i: clients[i].post('/api/v1/watchlists/default/items',
                                                json={'product_id': job['product_id'], 'threshold_pct': 15},
                                                headers=HEADERS))
    assert all(r.status_code == 200 for r in responses), [(r.status_code, r.text) for r in responses]
    items = clients[0].get('/api/v1/watchlists/default/items').json()['items']
    assert len(items) == 1
    assert len({r.json()['id'] for r in responses}) == 1
