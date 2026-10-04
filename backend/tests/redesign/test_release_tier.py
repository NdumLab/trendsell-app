"""The selected release tier is enforced, not only described in deployment notes."""
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings
from conftest import HEADERS, PASSWORD


def production_environment(monkeypatch, **changes):
    values = {
        'APP_ENV': 'production',
        'RELEASE_TIER': 'controlled_pilot',
        'DATABASE_URL': 'postgresql+psycopg://user:password@db.example/app',
        'CORS_ORIGINS': 'https://app.example.com',
        'RATE_KEY_SECRET': 'an-independent-production-rate-key-secret',
        'ALLOW_REGISTRATION': 'false',
        'MAIL_TRANSPORT': '',
        'DELETION_REGISTER_DIR': '/var/lib/trendsell/deletions',
    }
    values.update(changes)
    for name, value in values.items():
        monkeypatch.setenv(name, value)


def test_production_accepts_only_the_closed_controlled_pilot(monkeypatch):
    production_environment(monkeypatch)
    settings = Settings.from_env()
    assert settings.release_tier == 'controlled_pilot'
    assert settings.allow_registration is False
    assert settings.import_review_enabled is False

    monkeypatch.setenv('ALLOW_REGISTRATION', 'true')
    with pytest.raises(ValueError, match='invitation-only'):
        Settings.from_env()


@pytest.mark.parametrize('tier', ['public', 'paid'])
def test_public_and_paid_release_tiers_are_not_supported(monkeypatch, tier):
    production_environment(monkeypatch, RELEASE_TIER=tier)
    with pytest.raises(ValueError, match='does not support public or paid'):
        Settings.from_env()


def test_controlled_pilot_config_is_publicly_explicit_and_registration_is_closed(database_url):
    app = create_app(Settings(
        environment='test', release_tier='controlled_pilot', database_url=database_url,
        origins=('http://localhost:3000',), allow_registration=False))
    with TestClient(app) as client:
        policy = client.get('/api/v1/config').json()
        assert policy['release_tier'] == 'controlled_pilot'
        assert policy['invitation_only'] is True
        assert policy['billing_enabled'] is False
        assert policy['features']['billing'] is False
        assert policy['features']['recurring_monitoring'] is False
        assert policy['features']['alert_delivery'] is False
        response = client.post('/api/v1/auth/register', json={
            'email': 'uninvited@example.com', 'password': PASSWORD, 'name': 'Uninvited',
        }, headers=HEADERS)
        assert response.status_code == 403
        assert response.json()['detail'] == 'Registration is closed. Contact your workspace owner.'


def test_disabled_import_review_is_inaccessible_and_cannot_clear_the_gate(database_url, tmp_path):
    app = create_app(Settings(
        environment='test', database_url=database_url,
        origins=('http://localhost:3000',), allow_registration=True,
        import_review_enabled=False,
        deletion_register_dir=str(tmp_path / 'deletions')))
    with TestClient(app) as client:
        owner = client.post('/api/v1/auth/register', json={
            'email': 'owner@example.com', 'password': PASSWORD, 'name': 'Review disabled',
        }, headers=HEADERS)
        assert owner.status_code == 201, owner.text
        job = client.post('/api/v1/xray', json={
            'input': 'https://www.amazon.com/dp/B0ABCDEFGH',
        }, headers={**HEADERS, 'Idempotency-Key': 'disabled-review'}).json()
        product_id = job['product_id']
        client.post(f'/api/v1/products/{product_id}/confirm',
                    json={'name': 'Review subject'}, headers=HEADERS)
        assert client.get('/api/v1/config').json()['features']['import_review'] is False
        assert client.get(f'/api/v1/products/{product_id}/compliance').status_code == 404
        requested = client.post(f'/api/v1/products/{product_id}/compliance/requests', json={
            'product_id': product_id, 'specifications': 'A complete product specification.',
            'intended_use': 'Retail sale in Lagos',
            'question': 'What classification and requirements apply?',
            'destination': 'NG',
        }, headers=HEADERS)
        assert requested.status_code == 404
        detail = client.get(f'/api/v1/products/{product_id}').json()
        assert detail['compliance']['resolved'] is False
