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
from app.main import EXPORT_SCHEMA
from conftest import HEADERS, OPERATOR, PASSWORD

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
def test_the_audit_log_is_owner_only(client, owner, role, expected):
    set_role(client, owner['id'], role)
    assert client.get('/api/v1/audit').status_code == expected


@pytest.mark.parametrize('role', ['owner', 'analyst', 'reviewer', 'viewer'])
def test_no_workspace_role_can_read_operational_metrics(client, owner, role):
    """Review finding R07: counters span every workspace this worker served, so owning a
    workspace is not a claim on them. Administering a workspace is not operating the
    service, and the counters are reached with an operator token instead."""
    set_role(client, owner['id'], role)
    assert client.get('/api/v1/ops/metrics').status_code == 403


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
    assert entry['detail'] == {'scope': 'all-records', 'schema': EXPORT_SCHEMA}


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
    body = client.get('/api/v1/ops/metrics', headers=OPERATOR).json()
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
    assert client.get('/api/v1/ops/metrics', headers=OPERATOR).json()['rate_limited'] >= 1


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


# --- R07: metric labels are a bounded vocabulary --------------------------------------
#
# Review finding R07: labels were built by collapsing path segments that looked like long
# hex ids, so any other client-controlled segment became a permanent dictionary key.
# Twenty unknown paths produced twenty retained labels, and the paths needed no session.

def test_an_unknown_path_does_not_mint_a_metric_label(client, owner):
    for index in range(20):
        client.get(f'/api/v1/definitely-not-a-route/marker-{index}')
    labels = client.get('/api/v1/ops/metrics', headers=OPERATOR).json()['requests']
    assert not [label for label in labels if 'marker-' in label], labels


def test_labels_come_from_the_matched_route_template(client, owner, product):
    client.get(f'/api/v1/products/{product}')
    labels = client.get('/api/v1/ops/metrics', headers=OPERATOR).json()['requests']
    assert 'GET /api/v1/products/{product_id}' in labels
    assert product not in json.dumps(labels), 'no record id may reach a metric label'


def test_the_label_set_is_bounded(client, owner):
    """Even a route that legitimately varies cannot grow the set without limit."""
    from app.observability import MAX_LABELS, OVERFLOW_LABEL, Counters
    counters = Counters()
    for index in range(MAX_LABELS + 50):
        counters.record('GET', f'/synthetic/{index}', 200, 1.0)
    assert len(counters.requests) <= MAX_LABELS + 1
    assert counters.requests[OVERFLOW_LABEL] >= 50


def test_an_unauthenticated_caller_cannot_reach_the_metrics(second_client):
    assert second_client.get('/api/v1/ops/metrics').status_code == 403


def test_the_operator_token_is_required_and_compared_whole(client, owner):
    from conftest import METRICS_TOKEN
    assert client.get('/api/v1/ops/metrics', headers={'X-Metrics-Token': ''}).status_code == 403
    assert client.get('/api/v1/ops/metrics',
                      headers={'X-Metrics-Token': METRICS_TOKEN[:-1]}).status_code == 403
    assert client.get('/api/v1/ops/metrics', headers=OPERATOR).status_code == 200


def test_the_metrics_surface_is_absent_unless_it_is_configured():
    """Off by default: a deployment that has not enabled it does not have it."""
    from fastapi.testclient import TestClient
    from app.main import create_app
    from app.settings import Settings
    app = create_app(Settings(environment='test', database_url='sqlite://',
                              origins=('http://localhost:3000',), allow_registration=True))
    with TestClient(app) as unconfigured:
        assert unconfigured.get('/api/v1/ops/metrics').status_code == 404


def test_one_workspace_cannot_see_another_workspaces_request_labels(client, owner, second_client, stranger):
    """The review's reproduction: a marker requested by one workspace appeared in the
    other's metrics response. Neither may read the counters at all now."""
    client.get('/api/v1/products?search=marker-from-workspace-one')
    assert second_client.get('/api/v1/ops/metrics').status_code == 403
    operator_view = json.dumps(client.get('/api/v1/ops/metrics', headers=OPERATOR).json())
    assert 'marker-from-workspace-one' not in operator_view, 'a query string is not a label'


# --- R11: an authenticated request logs who it was ------------------------------------
#
# Review finding R11: `current_user` runs in a worker thread with its own context, so the
# context variables it set were invisible to the logging middleware and every
# authenticated request logged `workspace_id: "-"`.

@pytest.fixture
def request_logs(caplog):
    """The structured request logs actually emitted.

    `configure_logging` sets `propagate = False` on purpose, so application logs do not
    also reach the root logger — which is where caplog listens by default. Attaching
    caplog's handler to the `trendsell` logger captures exactly what is emitted, and
    nothing that merely would have been. Asserting on an empty capture would pass every
    "the logs contain no secrets" test for the wrong reason.
    """
    import logging
    from app.observability import logger as trendsell_logger
    caplog.set_level(logging.INFO, logger='trendsell')
    trendsell_logger.addHandler(caplog.handler)
    try:
        yield caplog
    finally:
        trendsell_logger.removeHandler(caplog.handler)


def request_lines(logs, route=None):
    return [record for record in logs.records if record.getMessage() == 'request'
            and (route is None or record.context.get('route') == route)]


def test_an_authenticated_request_logs_its_workspace_and_user(client, owner, request_logs):
    client.get('/api/v1/products')
    lines = request_lines(request_logs, '/api/v1/products')
    assert lines, 'the request was not logged'
    context = lines[-1].context
    assert context['workspace_id'] == owner['workspace_id']
    assert context['user_id'] == owner['id']


def test_every_authenticated_route_logs_an_identity(client, owner, product, request_logs):
    """The review saw product, evidence, quote and decision requests all logging "-"."""
    client.get('/api/v1/products')
    client.get(f'/api/v1/products/{product}')
    client.get(f'/api/v1/products/{product}/evidence')
    client.get('/api/v1/quotes')
    client.get('/api/v1/decisions')
    logged = request_lines(request_logs)
    assert len(logged) >= 5
    anonymous = [record.context['route'] for record in logged
                 if record.context['workspace_id'] == '-']
    assert not anonymous, anonymous


def test_an_anonymous_request_logs_no_identity(client, request_logs):
    client.get('/api/health')
    lines = request_lines(request_logs, '/api/health')
    assert lines
    assert lines[-1].context['workspace_id'] == '-'
    assert lines[-1].context['user_id'] == '-'


def test_request_logs_carry_no_secrets_or_payloads(client, owner, request_logs):
    client.post('/api/v1/auth/login',
                json={'email': 'owner@example.com', 'password': PASSWORD}, headers=HEADERS)
    lines = request_lines(request_logs)
    assert lines, 'nothing was captured, so this proves nothing'
    serialised = json.dumps([record.context for record in lines])
    assert PASSWORD not in serialised
    assert 'owner@example.com' not in serialised


def test_the_log_line_correlates_with_the_audit_row_it_produced(client, owner, request_logs):
    """Request id, workspace and actor on the same request, so a report is traceable."""
    response = client.post('/api/v1/xray', json={'input': AMAZON},
                           headers={**HEADERS, 'Idempotency-Key': 'r11', 'X-Request-ID': 'r11-traced-id'})
    assert response.status_code == 202
    lines = [record for record in request_lines(request_logs) if record.request_id == 'r11-traced-id']
    assert lines and lines[-1].context['workspace_id'] == owner['workspace_id']
    events = client.get('/api/v1/audit').json()['events']
    assert any(event['request_id'] == 'r11-traced-id' for event in events)
