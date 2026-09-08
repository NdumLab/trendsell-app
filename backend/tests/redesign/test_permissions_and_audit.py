"""The permission matrix, the audit trail and request identity (action plan P05, P07).

Roles used to be one inline check, `role in {'owner','analyst'}`, and the audit log was the
only owner-only surface. Every permission is now named and granted in one table, routes ask
for a permission rather than a role, and the check is always server-side.

Audit entries used to carry only an action, a record id and a time. They now carry the
actor, the workspace, the request that caused them and small non-secret facts about the
target — never a payload, a body or a credential.
"""
import json
import logging

import pytest

from app.db import Audit, User
from app.observability import JsonFormatter, route_label
from app.permissions import PERMISSIONS, ROLES, granted
from conftest import HEADERS

AMAZON = 'https://www.amazon.com/dp/B0ABCDEFGH'
INPUTS = {'quantity': 300, 'unit_cost_usd': 8.4, 'fx_ngn': 1500, 'freight_ngn': 900000, 'duty_pct': 5,
          'import_tax_pct': 7.5, 'selling_price_ngn': 32000, 'channel_fee_pct': 5, 'returns_pct': 3,
          'marketing_ngn': 300000, 'fixed_cost_ngn': 150000, 'stress_pct': 10,
          'compliance': 'unresolved', 'channel': 'Direct sales', 'shipping': 'Air'}


def set_role(client, user_id, role):
    with client.app.state.database.session() as db:
        db.query(User).filter_by(id=user_id).update({'role': role})
        db.commit()


@pytest.fixture
def product(client, owner):
    return client.post('/api/v1/xray', json={'input': AMAZON},
                       headers={**HEADERS, 'Idempotency-Key': 'x'}).json()['product_id']


# --- The matrix -------------------------------------------------------------------

def test_every_granted_permission_is_a_defined_one():
    for role, held in ROLES.items():
        assert held <= set(PERMISSIONS), f'{role} grants an undefined permission'


def test_the_matrix_separates_research_from_review():
    """A compliance gate that the person doing the research can clear is not a gate."""
    assert granted('analyst', 'workspace.write') is True
    assert granted('analyst', 'compliance.review') is False
    assert granted('reviewer', 'compliance.review') is True
    assert granted('reviewer', 'workspace.write') is False
    assert granted('viewer', 'workspace.write') is False
    assert ROLES['owner'] == set(PERMISSIONS)


def test_the_matrix_is_readable_from_the_api(client, owner):
    body = client.get('/api/v1/permissions').json()
    assert body['role'] == 'owner'
    assert set(body['granted']) == set(PERMISSIONS)
    assert set(body['roles']) == set(ROLES)
    assert body['permissions']['compliance.review']


# --- Enforcement ------------------------------------------------------------------

@pytest.mark.parametrize('role,expected', [('owner', 202), ('analyst', 202), ('reviewer', 403), ('viewer', 403)])
def test_writing_requires_the_write_permission(client, owner, role, expected):
    set_role(client, owner['id'], role)
    response = client.post('/api/v1/xray', json={'input': AMAZON}, headers={**HEADERS, 'Idempotency-Key': f'k-{role}'})
    assert response.status_code == expected
    assert client.get('/api/v1/products').status_code == 200, 'every role can still read'


@pytest.mark.parametrize('role,expected', [('owner', 200), ('analyst', 200), ('reviewer', 403), ('viewer', 403)])
def test_exporting_requires_the_export_permission(client, owner, role, expected):
    set_role(client, owner['id'], role)
    assert client.get('/api/v1/export').status_code == expected


@pytest.mark.parametrize('role,expected', [('owner', 200), ('analyst', 403), ('reviewer', 403), ('viewer', 403)])
def test_the_audit_log_and_metrics_are_owner_only(client, owner, role, expected):
    set_role(client, owner['id'], role)
    assert client.get('/api/v1/audit').status_code == expected
    assert client.get('/api/v1/ops/metrics').status_code == expected


def test_a_client_cannot_assert_a_permission_it_does_not_hold(client, owner):
    set_role(client, owner['id'], 'viewer')
    response = client.post('/api/v1/xray', json={'input': AMAZON},
                           headers={**HEADERS, 'Idempotency-Key': 'k', 'X-Role': 'owner',
                                    'X-Permissions': 'workspace.write'})
    assert response.status_code == 403
    assert client.get('/api/v1/permissions').json()['role'] == 'viewer'


# --- The audit trail ---------------------------------------------------------------

def test_an_audit_entry_names_the_actor_workspace_request_and_target(client, owner, product):
    client.post(f'/api/v1/products/{product}/confirm', json={'name': 'Steamer'}, headers=HEADERS)
    events = client.get('/api/v1/audit').json()['events']
    confirmed = next(event for event in events if event['action'] == 'product.confirmed')
    assert confirmed['actor'] == owner['id']
    assert confirmed['workspace_id'] == owner['workspace_id']
    assert confirmed['record_id'] == product
    assert confirmed['request_id']
    assert confirmed['created_at']


def test_a_saved_decision_records_its_verdict_and_versions(client, owner, product):
    client.post(f'/api/v1/products/{product}/confirm', json={'name': 'Steamer'}, headers=HEADERS)
    saved = client.post('/api/v1/decisions', json={'product_id': product, 'inputs': INPUTS},
                        headers={**HEADERS, 'Idempotency-Key': 'd'}).json()
    entry = next(e for e in client.get('/api/v1/audit').json()['events'] if e['action'] == 'decision.saved')
    assert entry['record_id'] == saved['id']
    assert entry['detail']['decision'] == saved['decision']
    assert entry['detail']['formula_version'] == saved['formula_version']
    assert entry['detail']['threshold_version'] == saved['threshold_version']


def test_downloading_the_workspace_is_audited(client, owner, product):
    client.get('/api/v1/export')
    entry = next(e for e in client.get('/api/v1/audit').json()['events'] if e['action'] == 'workspace.exported')
    assert entry['actor'] == owner['id']
    assert entry['detail'] == {'scope': 'all-records', 'schema': 'trendsell-workspace-export/1'}


def test_an_audit_entry_never_contains_a_credential_or_a_payload(client, owner, product):
    client.post(f'/api/v1/products/{product}/confirm', json={'name': 'Steamer'}, headers=HEADERS)
    client.post('/api/v1/quotes', headers=HEADERS, json={
        'product_id': product, 'supplier': 'Example Manufacturing Ltd',
        'source_url': 'https://supplier.example.com/quote', 'unit_price_usd': 8.4, 'moq': 300,
        'lead_days': 25, 'quote_date': '2026-09-01'})
    serialised = json.dumps(client.get('/api/v1/audit').json())
    for secret in ('a-long-enough-password', 'scrypt$', 'trendsell_session', 'supplier.example.com'):
        assert secret not in serialised, secret


def test_the_audit_log_is_scoped_and_paginated(client, owner, product, second_client, stranger):
    body = client.get('/api/v1/audit', params={'limit': 2}).json()
    assert len(body['events']) == 2
    assert body['total'] > 2
    assert {event['workspace_id'] for event in body['events']} == {owner['workspace_id']}
    assert client.get('/api/v1/audit', params={'limit': 0}).status_code == 422
    assert second_client.get('/api/v1/audit').json()['total'] < body['total']


def test_a_request_id_ties_the_response_to_the_audit_entry(client, owner, product):
    response = client.post(f'/api/v1/products/{product}/confirm', json={'name': 'Steamer'},
                           headers={**HEADERS, 'X-Request-ID': 'traced-request-0001'})
    assert response.headers['X-Request-ID'] == 'traced-request-0001'
    entry = next(e for e in client.get('/api/v1/audit').json()['events'] if e['action'] == 'product.confirmed')
    assert entry['request_id'] == 'traced-request-0001'


def test_a_hostile_request_id_is_replaced_rather_than_echoed(client, owner):
    response = client.get('/api/health', headers={'X-Request-ID': '<script>alert(1)</script>' * 20})
    assert response.headers['X-Request-ID'] != '<script>alert(1)</script>' * 20
    assert len(response.headers['X-Request-ID']) <= 64


def test_every_response_carries_a_request_id(client):
    for path in ('/api/health', '/api/v1/config', '/api/v1/products'):
        assert client.get(path).headers.get('X-Request-ID'), path


# --- Logs and counters --------------------------------------------------------------

def test_a_log_line_is_json_and_carries_the_request_id():
    record = logging.LogRecord('trendsell', logging.INFO, __file__, 1, 'request', None, None)
    record.request_id = 'abc123'
    record.context = {'route': '/api/v1/products', 'status': 200}
    line = json.loads(JsonFormatter().format(record))
    assert line['request_id'] == 'abc123'
    assert line['route'] == '/api/v1/products'
    assert line['level'] == 'info'


def test_route_labels_collapse_record_ids():
    assert route_label('/api/v1/products/2f1c9a4e-1b2c-4d5e-8a9b-0c1d2e3f4a5b/evidence') == \
        '/api/v1/products/:id/evidence'
    assert route_label('/api/v1/products') == '/api/v1/products'


def test_metrics_count_requests_errors_and_rate_limits_without_workspace_data(client, owner):
    client.get('/api/v1/products')
    body = client.get('/api/v1/ops/metrics').json()
    assert body['requests']['GET /api/v1/products'] >= 1
    assert body['responses_by_status']['200'] >= 1
    assert 'rate_limited' in body and 'latency_ms' in body
    assert body['note'].startswith('Counters are per worker')
    serialised = json.dumps(body)
    assert owner['workspace_id'] not in serialised
    assert owner['email'] not in serialised


def test_metrics_count_a_rejected_quota(client, owner, settings):
    for index in range(settings.research_daily_limit + 1):
        client.post('/api/v1/xray', json={'input': AMAZON}, headers={**HEADERS, 'Idempotency-Key': f'q{index}'})
    assert client.get('/api/v1/ops/metrics').json()['rate_limited'] >= 1


def test_audit_entries_are_append_only_through_the_api(client, owner, product):
    """Nothing in the API writes an audit row twice or edits one."""
    before = client.get('/api/v1/audit').json()['total']
    client.post(f'/api/v1/products/{product}/confirm', json={'name': 'Steamer'}, headers=HEADERS)
    client.post(f'/api/v1/products/{product}/confirm', json={'name': 'Steamer renamed'}, headers=HEADERS)
    after = client.get('/api/v1/audit').json()
    assert after['total'] == before + 2
    with client.app.state.database.session() as db:
        ids = [row.id for row in db.query(Audit).all()]
    assert len(ids) == len(set(ids))
