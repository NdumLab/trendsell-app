"""Identity, session handling, CSRF and workspace scoping. Zero cross-workspace disclosure."""
from app.db import User

from conftest import HEADERS, PASSWORD, register

AMAZON = 'https://www.amazon.com/dp/B0ABCDEFGH'


def test_register_returns_the_workspace_owner(client):
    user = register(client)
    assert user['role'] == 'owner'
    assert user['workspace_id']
    assert 'password' not in user


def test_session_cookie_is_httponly_and_scoped_to_the_api(client):
    client.post('/api/v1/auth/register', json={'email': 'a@example.com', 'password': PASSWORD, 'name': 'W'}, headers=HEADERS)
    cookie = next(c for c in client.cookies.jar if c.name == 'trendsell_session')
    assert cookie.path == '/api'
    assert cookie.has_nonstandard_attr('HttpOnly')


def test_reads_require_a_session(client):
    for path in ['/api/v1/auth/me', '/api/v1/products', '/api/v1/decisions', '/api/v1/quotes', '/api/v1/watchlists/default/items', '/api/v1/alerts']:
        assert client.get(path).status_code == 401, path


def test_login_rejects_a_wrong_password_without_revealing_the_account(client, owner):
    missing = client.post('/api/v1/auth/login', json={'email': 'nobody@example.com', 'password': PASSWORD, 'name': 'W'}, headers=HEADERS)
    wrong = client.post('/api/v1/auth/login', json={'email': 'owner@example.com', 'password': 'wrong-password-here', 'name': 'W'}, headers=HEADERS)
    assert missing.status_code == wrong.status_code == 401
    assert missing.json()['detail'] == wrong.json()['detail']


def test_logout_invalidates_the_session(client, owner):
    assert client.post('/api/v1/auth/logout', json={}, headers=HEADERS).status_code == 200
    assert client.get('/api/v1/auth/me').status_code == 401


def test_state_changing_requests_need_the_csrf_header(client, owner):
    assert client.post('/api/v1/xray', json={'input': AMAZON}).status_code == 403


def test_state_changing_requests_reject_a_foreign_origin(client, owner):
    response = client.post('/api/v1/xray', json={'input': AMAZON}, headers={**HEADERS, 'Origin': 'https://evil.example'})
    assert response.status_code == 403


def test_a_viewer_cannot_write(client, owner):
    app = client.app
    with app.state.database.session() as db:
        db.query(User).filter_by(id=owner['id']).update({'role': 'viewer'})
        db.commit()
    response = client.post('/api/v1/xray', json={'input': AMAZON}, headers={**HEADERS, 'Idempotency-Key': 'k'})
    assert response.status_code == 403
    assert client.get('/api/v1/products').status_code == 200


def test_products_are_invisible_to_another_workspace(client, owner, second_client, stranger):
    """Both workspaces share one database; see test_tenant_isolation.py for full coverage."""
    created = client.post('/api/v1/xray', json={'input': AMAZON}, headers={**HEADERS, 'Idempotency-Key': 'k1'}).json()
    product_id = created['product_id']
    assert client.get(f'/api/v1/products/{product_id}').status_code == 200
    assert second_client.get('/api/v1/products').json()['products'] == []
    assert second_client.get(f'/api/v1/products/{product_id}').status_code == 404
    assert second_client.get(f'/api/v1/research-jobs/{created["id"]}').status_code == 404
    assert second_client.post(f'/api/v1/products/{product_id}/confirm', json={'name': 'Stolen'}, headers=HEADERS).status_code == 404
    assert client.get(f'/api/v1/products/{product_id}').json()['name'].startswith('Amazon product')


def test_audit_log_is_owner_only_and_records_the_login(client, owner):
    actions = [event['action'] for event in client.get('/api/v1/audit').json()['events']]
    assert 'auth.login' in actions
    app = client.app
    with app.state.database.session() as db:
        db.query(User).filter_by(id=owner['id']).update({'role': 'analyst'})
        db.commit()
    assert client.get('/api/v1/audit').status_code == 403


def test_the_synthetic_prototype_api_is_retired(client):
    for path in ['/api/research/refresh', '/api/products', '/api/niches', '/api/store-spy']:
        assert client.get(path).status_code == 410, path
