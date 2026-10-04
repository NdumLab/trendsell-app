"""Out-of-band workspace deletion intent and restore replay (readiness D04/A04)."""
import importlib.util
import json
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

from app.db import Record, User, Workspace
from app.deletions import DeletionRegister, DeletionRegisterError
from app import migrate
from app.main import create_app
from app.settings import Settings
from conftest import HEADERS, PASSWORD, register

REPOSITORY = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    'replay_deletions_tool', REPOSITORY / 'scripts/replay_deletions.py')
replay_tool = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = replay_tool
SPEC.loader.exec_module(replay_tool)


def delete(client, name='Test workspace'):
    return client.request('DELETE', '/api/v1/auth/account', headers=HEADERS, json={
        'password': PASSWORD, 'confirmation': f'DELETE {name}',
    })


def test_deletion_intent_is_verified_and_contains_no_direct_identity(client, owner, app):
    response = delete(client)
    assert response.status_code == 200, response.text
    entries = app.state.deletion_register.entries()
    assert len(entries) == 1
    entry = entries[0]
    assert entry['workspace_id'] == owner['workspace_id']
    assert entry['member_ids'] == [owner['id']]
    register_text = ''.join(path.read_text() for path in
                            app.state.deletion_register.directory.iterdir())
    assert 'owner@example.com' not in register_text
    assert PASSWORD not in register_text
    assert entry['request_id'] != '-'


def test_deletion_is_refused_when_intent_cannot_be_durably_recorded(client, owner,
                                                                    app, monkeypatch):
    def fail(**_):
        raise DeletionRegisterError('isolated register failure')
    monkeypatch.setattr(app.state.deletion_register, 'record', fail)
    response = delete(client)
    assert response.status_code == 503
    assert response.json()['detail'] == 'isolated register failure'
    with app.state.database.session() as db:
        assert db.get(Workspace, owner['workspace_id']) is not None
        assert db.get(User, owner['id']) is not None


def test_a_tampered_entry_stops_replay(tmp_path):
    register_store = DeletionRegister(tmp_path / 'register')
    entry = register_store.record(workspace_id='workspace', member_ids=['member'],
                                  rate_fragments=['a' * 64],
                                  requested_at='2026-09-16T00:00:00+00:00',
                                  request_id='request-1234')
    path = register_store.directory / f'{entry["event_id"]}.json'
    payload = json.loads(path.read_text())
    payload['workspace_id'] = 'different-workspace'
    path.write_text(json.dumps(payload))
    with pytest.raises(DeletionRegisterError, match='SHA-256'):
        register_store.entries()


def test_read_only_verification_refuses_a_missing_register(tmp_path):
    path = tmp_path / 'not-provisioned'
    with pytest.raises(DeletionRegisterError, match='does not exist'):
        DeletionRegister(path).entries(prepare=False)
    assert not path.exists()


def test_orphaned_checksum_stops_replay(tmp_path):
    register_dir = tmp_path / 'register'
    register_dir.mkdir()
    (register_dir / f'{"a" * 32}.json.sha256').write_text('0' * 64)
    with pytest.raises(DeletionRegisterError, match='checksum has no entry'):
        DeletionRegister(register_dir).entries(prepare=False)


def test_register_refuses_links_even_when_the_target_is_a_file(tmp_path):
    register_dir = tmp_path / 'register'
    register_dir.mkdir()
    target = tmp_path / 'outside.json'
    target.write_text('{}')
    (register_dir / f'{"a" * 32}.json').symlink_to(target)
    with pytest.raises(DeletionRegisterError, match='Unexpected file'):
        DeletionRegister(register_dir).entries(prepare=False)


def test_register_directory_must_not_be_a_link(tmp_path):
    target = tmp_path / 'target'
    target.mkdir()
    register_dir = tmp_path / 'register'
    register_dir.symlink_to(target, target_is_directory=True)
    with pytest.raises(DeletionRegisterError, match='must not be a symbolic link'):
        DeletionRegister(register_dir).entries(prepare=False)


def test_startup_replays_a_deletion_against_rows_resurrected_by_restore(tmp_path):
    database_url = f'sqlite:///{tmp_path / "restored.db"}'
    register_dir = tmp_path / 'register'
    settings = Settings(environment='test', database_url=database_url,
                        origins=('http://localhost:3000',), allow_registration=True,
                        deletion_register_dir=str(register_dir))
    first = create_app(settings)
    with TestClient(first) as client:
        owner = register(client)
        assert delete(client).status_code == 200

    # Simulate restoring an older recovery point that still contains the workspace.
    with first.state.database.session() as db:
        db.add(Workspace(id=owner['workspace_id'], name='Test workspace'))
        db.flush()
        db.add(User(id=owner['id'], workspace_id=owner['workspace_id'],
                    email=owner['email'], name='Owner', password_hash='restored', role='owner'))
        db.flush()
        db.add(Record(id='restored-record', workspace_id=owner['workspace_id'],
                      kind='product', key='restored', payload={'restored': True}))
        db.commit()

    restored = create_app(settings)
    with TestClient(restored):
        with restored.state.database.session() as db:
            assert db.get(Workspace, owner['workspace_id']) is None
            assert db.get(User, owner['id']) is None
            assert db.get(Record, 'restored-record') is None


def test_restore_replay_requires_the_exact_candidate_revision(tmp_path):
    url = f'sqlite:///{tmp_path / "restored.db"}'
    migrate.upgrade(url, migrate.BASELINE)
    register_dir = tmp_path / 'register'
    register_dir.mkdir()
    database_name = str(tmp_path / 'restored.db')

    result = replay_tool.main([
        '--url', url, '--register-dir', str(register_dir),
        '--confirm-database', database_name,
    ])
    assert result == 1


def test_restore_replay_accepts_a_verified_head_schema(tmp_path):
    url = f'sqlite:///{tmp_path / "restored.db"}'
    migrate.upgrade(url)
    register_dir = tmp_path / 'register'
    register_dir.mkdir()
    database_name = str(tmp_path / 'restored.db')

    result = replay_tool.main([
        '--url', url, '--register-dir', str(register_dir),
        '--confirm-database', database_name,
    ])
    assert result == 0


def test_production_requires_an_absolute_deletion_register(monkeypatch):
    values = {
        'APP_ENV': 'production', 'RELEASE_TIER': 'controlled_pilot',
        'DATABASE_URL': 'postgresql+psycopg://user:password@db.example/app',
        'CORS_ORIGINS': 'https://app.example.com', 'ALLOW_REGISTRATION': 'false',
        'RATE_KEY_SECRET': 'an-independent-production-rate-key-secret',
        'DELETION_REGISTER_DIR': 'relative/deletions',
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    with pytest.raises(ValueError, match='absolute path'):
        Settings.from_env()


def test_production_refuses_the_filesystem_root_as_a_deletion_register(monkeypatch):
    values = {
        'APP_ENV': 'production', 'RELEASE_TIER': 'controlled_pilot',
        'DATABASE_URL': 'postgresql+psycopg://user:password@db.example/app',
        'CORS_ORIGINS': 'https://app.example.com', 'ALLOW_REGISTRATION': 'false',
        'RATE_KEY_SECRET': 'an-independent-production-rate-key-secret',
        'DELETION_REGISTER_DIR': '/',
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    with pytest.raises(ValueError, match='dedicated absolute path'):
        Settings.from_env()
