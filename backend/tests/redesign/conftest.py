"""Fixtures for the redesign suite.

Two things matter here (action plan T01):

* **One database, several cookie jars.** Tenant scoping is only exercised if both
  workspaces live in the same store. The earlier fixtures built a second app with its
  own in-memory engine, so a foreign id returned 404 whether or not the query filtered
  by workspace. `second_client` now shares the app under test and only separates the
  session cookie.
* **The same suite runs on PostgreSQL.** Set ``TEST_POSTGRES_URL`` and every test runs
  against a disposable schema in that database instead of SQLite, so unique
  constraints, transaction behaviour and JSONB storage are covered by the real engine.
"""
import os
import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app import passwords  # noqa: E402
from app.db import User  # noqa: E402
from app.main import create_app  # noqa: E402
from app.settings import Settings  # noqa: E402

HEADERS = {'X-Requested-With': 'TrendSell'}
#: Production parameters cost ~380 ms per hash, and most tests register a user. The suite
#: runs at a deliberately weak cost; test_passwords.py exercises the real ones (P02).
FAST_SCRYPT = {'n': 2 ** 12, 'r': 8, 'p': 1}
PASSWORD = 'a-long-enough-password'
#: The operator token for the metrics surface. Not a workspace credential (R07).
METRICS_TOKEN = 'operator-token-for-tests'
OPERATOR = {'X-Metrics-Token': METRICS_TOKEN}
POSTGRES_URL = os.getenv('TEST_POSTGRES_URL')
requires_postgres = pytest.mark.skipif(not POSTGRES_URL, reason='TEST_POSTGRES_URL is not configured')


def postgres_schema_url(base):
    """A disposable schema in the test database, and a callable that drops it."""
    schema = 'trendsell_test_' + uuid.uuid4().hex[:16]
    admin = create_engine(base, isolation_level='AUTOCOMMIT')
    with admin.connect() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))

    def drop():
        with admin.connect() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()

    separator = '&' if '?' in base else '?'
    return f'{base}{separator}options=-csearch_path%3D{schema}', drop


@pytest.fixture(autouse=True)
def fast_password_hashing(monkeypatch):
    monkeypatch.setattr(passwords, 'PARAMETERS', FAST_SCRYPT)


@pytest.fixture
def database_url(tmp_path):
    """An empty database for one test: a PostgreSQL schema when configured, else SQLite."""
    if not POSTGRES_URL:
        yield 'sqlite://'
        return
    url, drop = postgres_schema_url(POSTGRES_URL)
    try:
        yield url
    finally:
        drop()


@pytest.fixture
def settings(database_url):
    return Settings(environment='test', database_url=database_url,
                    origins=('http://localhost:3000',), allow_registration=True, research_daily_limit=20,
                    metrics_token=METRICS_TOKEN)


@pytest.fixture
def app(settings):
    return create_app(settings)


@pytest.fixture
def client(app):
    with TestClient(app) as client:
        yield client


def register(client, email='owner@example.com', name='Test workspace'):
    response = client.post('/api/v1/auth/register', json={'email': email, 'password': PASSWORD, 'name': name}, headers=HEADERS)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def owner(client):
    return register(client)


@pytest.fixture
def second_client(client):
    """A second signed-out client against the *same* app and database.

    Only the cookie jar differs, so a 404 for a foreign record proves workspace
    filtering rather than proving the record was never stored.
    """
    return TestClient(client.app)


@pytest.fixture
def stranger(second_client):
    """A signed-in owner of a different workspace in the same database."""
    return register(second_client, email='stranger@example.com', name='Other workspace')


@pytest.fixture
def workspace_reviewer(client, owner):
    """A separate signed-in reviewer in the owner's workspace.

    Tests that exercise review outcomes must use a different cookie jar from the
    requester. Moving this already-authenticated test account keeps the fixture focused
    on review behavior; invitation acceptance has its own API and browser coverage.
    """
    with TestClient(client.app) as reviewer_client:
        account = register(reviewer_client, email='workspace-reviewer@example.com',
                           name='Temporary reviewer workspace')
        with client.app.state.database.session() as db:
            reviewer = db.query(User).filter_by(id=account['id']).one()
            reviewer.workspace_id = owner['workspace_id']
            reviewer.role = 'reviewer'
            db.commit()
        yield reviewer_client
