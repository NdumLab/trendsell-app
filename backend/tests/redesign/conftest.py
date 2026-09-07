"""Fixtures for the redesign suite. Every test gets an isolated in-memory evidence store."""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.main import create_app  # noqa: E402
from app.settings import Settings  # noqa: E402

HEADERS = {'X-Requested-With': 'TrendSell'}
PASSWORD = 'a-long-enough-password'


@pytest.fixture
def settings():
    return Settings(environment='test', database_url='sqlite://',
                    origins=('http://localhost:3000',), allow_registration=True, research_daily_limit=20)


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as client:
        yield client


def register(client, email='owner@example.com', name='Test workspace'):
    response = client.post('/api/v1/auth/register', json={'email': email, 'password': PASSWORD, 'name': name}, headers=HEADERS)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def owner(client):
    return register(client)


def second_workspace(settings):
    """A second client against the same app, so tenant scoping is exercised end to end."""
    return TestClient(create_app(settings))
