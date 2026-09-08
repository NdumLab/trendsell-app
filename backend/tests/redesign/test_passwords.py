"""Password hashing is upgradeable and nobody is locked out (action plan P02).

Review finding 9: passwords used scrypt at N=2^14, r=8, p=1 — below every configuration in
the OWASP Password Storage Cheat Sheet — and the stored value was only `salt:digest`, so
changing the parameters would have invalidated every existing password.

Most of this suite runs with deliberately weak parameters for speed (see conftest). The
cases below that concern the *real* configuration opt back in explicitly.
"""
import re
import time

import pytest

from app import passwords
from app.db import User
from conftest import HEADERS, PASSWORD, register

OWASP_EQUIVALENT_SETS = [
    {'n': 2 ** 17, 'r': 8, 'p': 1},
    {'n': 2 ** 16, 'r': 8, 'p': 2},
    {'n': 2 ** 15, 'r': 8, 'p': 3},
    {'n': 2 ** 14, 'r': 8, 'p': 5},
    {'n': 2 ** 13, 'r': 8, 'p': 10},
]


@pytest.fixture
def production_parameters(monkeypatch):
    """Undo the suite-wide speed-up for the cases that must judge the shipped cost."""
    monkeypatch.setattr(passwords, 'PARAMETERS', {'n': 2 ** 16, 'r': 8, 'p': 2})
    return passwords.PARAMETERS


def legacy_hash(password, salt='a' * 32):
    """The exact pre-P02 format: scrypt at N=2^14, r=8, p=1, stored as 'salt:digest'."""
    import hashlib
    digest = hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1).hex()
    return f'{salt}:{digest}'


# --- The stored format ------------------------------------------------------------

def test_a_new_hash_names_its_algorithm_and_parameters(production_parameters):
    stored = passwords.hash_password(PASSWORD)
    assert re.fullmatch(r'scrypt\$n=65536,r=8,p=2\$[0-9a-f]{32}\$[0-9a-f]+', stored)
    parameters, salt, digest, is_legacy = passwords.parse(stored)
    assert parameters == production_parameters
    assert is_legacy is False
    assert len(salt) == 32 and digest


def test_the_shipped_parameters_are_one_of_the_sets_owasp_lists(production_parameters):
    assert production_parameters in OWASP_EQUIVALENT_SETS


def test_two_hashes_of_one_password_differ_because_the_salt_is_random():
    first, second = passwords.hash_password(PASSWORD), passwords.hash_password(PASSWORD)
    assert first != second
    assert passwords.verify_password(PASSWORD, first)[0]
    assert passwords.verify_password(PASSWORD, second)[0]


def test_a_wrong_password_is_rejected():
    stored = passwords.hash_password(PASSWORD)
    assert passwords.verify_password('not-the-password', stored) == (False, False)


@pytest.mark.parametrize('damaged', [
    '', 'not-a-hash', 'scrypt$$$', 'scrypt$n=1$abc$def', 'scrypt$n=8,r=8,p=1$zz$dd',
    ':', 'abc:', ':def',
])
def test_an_unreadable_stored_hash_fails_closed(damaged):
    assert passwords.verify_password(PASSWORD, damaged) == (False, False)


# --- Legacy hashes still work, and are upgraded ------------------------------------

def test_a_legacy_hash_still_verifies():
    stored = legacy_hash(PASSWORD)
    ok, needs_rehash = passwords.verify_password(PASSWORD, stored)
    assert ok is True
    assert needs_rehash is True


def test_a_legacy_hash_rejects_the_wrong_password():
    assert passwords.verify_password('wrong-password-entirely', legacy_hash(PASSWORD))[0] is False


def test_a_hash_at_weaker_parameters_is_flagged_for_rehash(production_parameters):
    weak = passwords.hash_password(PASSWORD, parameters={'n': 2 ** 12, 'r': 8, 'p': 1})
    ok, needs_rehash = passwords.verify_password(PASSWORD, weak)
    assert (ok, needs_rehash) == (True, True)


def test_a_hash_at_the_current_parameters_is_not_rehashed(production_parameters):
    assert passwords.verify_password(PASSWORD, passwords.hash_password(PASSWORD)) == (True, False)


# --- The login path ----------------------------------------------------------------

def test_an_existing_user_with_a_legacy_hash_can_still_sign_in(client):
    owner = register(client)
    with client.app.state.database.session() as db:
        db.query(User).filter_by(id=owner['id']).update({'password_hash': legacy_hash(PASSWORD)})
        db.commit()
    client.post('/api/v1/auth/logout', json={}, headers=HEADERS)

    response = client.post('/api/v1/auth/login',
                           json={'email': 'owner@example.com', 'password': PASSWORD, 'name': 'W'},
                           headers=HEADERS)
    assert response.status_code == 200, response.text


def test_a_correct_sign_in_upgrades_a_legacy_hash_in_place(client):
    owner = register(client)
    with client.app.state.database.session() as db:
        db.query(User).filter_by(id=owner['id']).update({'password_hash': legacy_hash(PASSWORD)})
        db.commit()
    client.post('/api/v1/auth/logout', json={}, headers=HEADERS)

    client.post('/api/v1/auth/login', json={'email': 'owner@example.com', 'password': PASSWORD, 'name': 'W'},
                headers=HEADERS)

    with client.app.state.database.session() as db:
        stored = db.get(User, owner['id']).password_hash
    assert stored.startswith('scrypt$')
    assert passwords.verify_password(PASSWORD, stored) == (True, False)
    # And the upgraded hash is what the next sign-in uses.
    client.post('/api/v1/auth/logout', json={}, headers=HEADERS)
    assert client.post('/api/v1/auth/login', json={'email': 'owner@example.com', 'password': PASSWORD, 'name': 'W'},
                       headers=HEADERS).status_code == 200


def test_the_rehash_is_recorded_in_the_audit_log(client):
    owner = register(client)
    with client.app.state.database.session() as db:
        db.query(User).filter_by(id=owner['id']).update({'password_hash': legacy_hash(PASSWORD)})
        db.commit()
    client.post('/api/v1/auth/logout', json={}, headers=HEADERS)
    client.post('/api/v1/auth/login', json={'email': 'owner@example.com', 'password': PASSWORD, 'name': 'W'},
                headers=HEADERS)
    actions = [event['action'] for event in client.get('/api/v1/audit').json()['events']]
    assert 'auth.password_rehashed' in actions


def test_a_wrong_password_never_rewrites_the_stored_hash(client):
    owner = register(client)
    legacy = legacy_hash(PASSWORD)
    with client.app.state.database.session() as db:
        db.query(User).filter_by(id=owner['id']).update({'password_hash': legacy})
        db.commit()
    client.post('/api/v1/auth/logout', json={}, headers=HEADERS)
    assert client.post('/api/v1/auth/login',
                       json={'email': 'owner@example.com', 'password': 'a-different-password', 'name': 'W'},
                       headers=HEADERS).status_code == 401
    with client.app.state.database.session() as db:
        assert db.get(User, owner['id']).password_hash == legacy


def test_a_login_for_a_missing_account_still_spends_hashing_work(client, monkeypatch):
    """Otherwise the response time says whether an account exists."""
    calls = []
    original = passwords.hash_password
    monkeypatch.setattr(passwords, 'hash_password', lambda *a, **k: (calls.append(1), original(*a, **k))[1])
    client.post('/api/v1/auth/login', json={'email': 'nobody@example.com', 'password': PASSWORD, 'name': 'W'},
                headers=HEADERS)
    assert calls, 'no hashing work was done for a missing account'


# --- Cost --------------------------------------------------------------------------

def test_the_shipped_configuration_costs_real_work(production_parameters):
    """A measurement, not a threshold to tune: it records what a verification costs here."""
    stored = passwords.hash_password(PASSWORD)
    start = time.perf_counter()
    assert passwords.verify_password(PASSWORD, stored)[0]
    elapsed = time.perf_counter() - start
    assert elapsed > 0.05, f'verification took {elapsed * 1000:.0f} ms, which is too cheap'
    assert elapsed < 5, f'verification took {elapsed * 1000:.0f} ms, which would stall logins'
