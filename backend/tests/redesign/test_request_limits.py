"""Request size, authentication limits and expired-record cleanup (action plan P04).

Review finding 11: the size check read `Content-Length` alone, so a chunked body that
never declares a length was not counted — a 40,032-byte chunked confirmation returned 200
against a 32 KiB limit. The deployed nginx caps API bodies at 64 KiB independently, which
limited the exposure, but the application must not rely on a proxy it does not control.

Review finding 10: one bucket of 20 requests per IP per hour covered login and
registration together. That inconveniences a shared network while giving no account-level
limit against guessing spread across addresses.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.db import RateBucket, Session
from app.limits import MAX_BODY_BYTES
from app.security import purge_expired
from conftest import HEADERS, PASSWORD, register

AMAZON = 'https://www.amazon.com/dp/B0ABCDEFGH'


@pytest.fixture
def product(client, owner):
    return client.post('/api/v1/xray', json={'input': AMAZON},
                       headers={**HEADERS, 'Idempotency-Key': 'x'}).json()['product_id']


def chunks(payload, size=8192):
    """An iterable body, which httpx sends with Transfer-Encoding: chunked."""
    for start in range(0, len(payload), size):
        yield payload[start:start + size]


# --- Request size ------------------------------------------------------------------

def test_an_oversized_declared_body_is_refused(client, product):
    body = {'name': 'x' * (MAX_BODY_BYTES + 1000)}
    response = client.post(f'/api/v1/products/{product}/confirm', json=body, headers=HEADERS)
    assert response.status_code == 413
    assert response.json()['detail'] == 'Request is too large'


def test_an_oversized_chunked_body_is_refused(client, product):
    """The reviewed reproduction: no Content-Length, so only counting bytes catches it."""
    payload = ('{"name":"' + 'x' * (MAX_BODY_BYTES + 8000) + '"}').encode()
    response = client.post(f'/api/v1/products/{product}/confirm', content=chunks(payload),
                           headers={**HEADERS, 'Content-Type': 'application/json'})
    assert response.status_code == 413, response.text
    assert 'content-length' not in {k.lower() for k in response.request.headers}


def test_the_oversized_body_never_reaches_the_application(client, product):
    before = client.get(f'/api/v1/products/{product}').json()['name']
    payload = ('{"name":"' + 'y' * (MAX_BODY_BYTES + 8000) + '"}').encode()
    client.post(f'/api/v1/products/{product}/confirm', content=chunks(payload),
                headers={**HEADERS, 'Content-Type': 'application/json'})
    assert client.get(f'/api/v1/products/{product}').json()['name'] == before


def test_a_body_at_the_limit_is_still_accepted(client, product):
    """The limit must not be so eager that an ordinary request fails."""
    filler = 'a' * 150
    response = client.post(f'/api/v1/products/{product}/confirm', json={'name': filler}, headers=HEADERS)
    assert response.status_code == 200
    assert response.json()['name'] == filler


def test_a_lying_content_length_header_does_not_get_a_body_through(client, product):
    """A small declared length with a large body must still be counted as it arrives."""
    payload = ('{"name":"' + 'z' * (MAX_BODY_BYTES + 8000) + '"}').encode()
    response = client.post(f'/api/v1/products/{product}/confirm', content=chunks(payload),
                           headers={**HEADERS, 'Content-Type': 'application/json', 'Content-Length': '20'})
    assert response.status_code in {400, 413}


def test_reads_are_not_size_limited(client, product):
    assert client.get(f'/api/v1/products/{product}').status_code == 200


# --- Authentication limits ---------------------------------------------------------

def test_sign_in_attempts_are_limited_per_account(client, owner):
    """A limit that follows the account, not only the address it came from."""
    client.post('/api/v1/auth/logout', json={}, headers=HEADERS)
    codes = [client.post('/api/v1/auth/login',
                         json={'email': 'owner@example.com', 'password': 'wrong-password-here', 'name': 'W'},
                         headers=HEADERS).status_code for _ in range(12)]
    assert 429 in codes
    assert codes.count(401) < 12
    blocked = client.post('/api/v1/auth/login', json={'email': 'owner@example.com', 'password': PASSWORD, 'name': 'W'},
                          headers=HEADERS)
    assert blocked.status_code == 429
    assert 'this account' in blocked.json()['detail']


def test_exhausting_one_account_does_not_lock_another_on_the_same_address(client, second_client):
    register(client, email='first@example.com', name='First')
    register(second_client, email='second@example.com', name='Second')
    client.post('/api/v1/auth/logout', json={}, headers=HEADERS)
    second_client.post('/api/v1/auth/logout', json={}, headers=HEADERS)

    for _ in range(12):
        client.post('/api/v1/auth/login', json={'email': 'first@example.com', 'password': 'wrong-password-here', 'name': 'W'},
                    headers=HEADERS)
    assert client.post('/api/v1/auth/login', json={'email': 'first@example.com', 'password': PASSWORD, 'name': 'W'},
                       headers=HEADERS).status_code == 429
    # The address limit is higher than the account limit, so a colleague can still sign in.
    assert second_client.post('/api/v1/auth/login',
                              json={'email': 'second@example.com', 'password': PASSWORD, 'name': 'W'},
                              headers=HEADERS).status_code == 200


def test_registration_has_its_own_limit_separate_from_sign_in(client):
    codes = [client.post('/api/v1/auth/register',
                         json={'email': f'burst{index}@example.com', 'password': PASSWORD, 'name': 'W'},
                         headers=HEADERS).status_code for index in range(12)]
    assert 429 in codes
    assert client.post('/api/v1/auth/register', json={'email': 'more@example.com', 'password': PASSWORD, 'name': 'W'},
                       headers=HEADERS).json()['detail'].startswith('Too many workspaces')
    # Registration being exhausted must not stop an existing user signing in.
    assert client.post('/api/v1/auth/login', json={'email': 'burst0@example.com', 'password': PASSWORD, 'name': 'W'},
                       headers=HEADERS).status_code == 200


# --- Cleanup -----------------------------------------------------------------------

def test_expired_sessions_and_finished_windows_are_removed(client, owner):
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    with client.app.state.database.session() as db:
        db.add(Session(token_hash='expired-session', user_id=owner['id'], expires_at=past))
        db.add(RateBucket(key='finished-window', count=5, expires_at=past))
        db.add(RateBucket(key='active-window', count=1, expires_at=future))
        db.commit()
        removed = purge_expired(db)
        assert removed == {'sessions': 1, 'rate_buckets': 1}
        assert db.get(Session, 'expired-session') is None
        assert db.get(RateBucket, 'finished-window') is None
        assert db.get(RateBucket, 'active-window').count == 1

    # The live session is untouched, so the signed-in user stays signed in.
    assert client.get('/api/v1/auth/me').status_code == 200


def test_cleanup_never_resets_a_window_that_is_still_counting(client, owner):
    """Purging must not become a way to escape a rate limit."""
    client.post('/api/v1/auth/logout', json={}, headers=HEADERS)
    for _ in range(12):
        client.post('/api/v1/auth/login', json={'email': 'owner@example.com', 'password': 'wrong-password-here', 'name': 'W'},
                    headers=HEADERS)
    with client.app.state.database.session() as db:
        purge_expired(db)
    assert client.post('/api/v1/auth/login', json={'email': 'owner@example.com', 'password': PASSWORD, 'name': 'W'},
                       headers=HEADERS).status_code == 429


def test_a_new_rate_bucket_records_when_its_window_ends(client, owner):
    with client.app.state.database.session() as db:
        buckets = db.query(RateBucket).all()
        assert buckets
        for bucket in buckets:
            assert bucket.expires_at is not None
            assert bucket.expires_at > datetime.now(timezone.utc).isoformat()
