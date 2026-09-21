"""The restore verifier tells the truth about a database it has not damaged (P06, R06).

Review finding R06: the verifier replayed each saved assessment with `calculate(inputs,
formula_version=...)` and no evidence reading, so confidence and coverage defaulted to
zero. Every assessment saved with manual evidence — that is, every normal one — was
reported as differing on decision, blockers and confidence. No restore was needed to
produce the false alarm: an untouched database failed its own verification, which makes
the check worse than useless, because a real corruption would look identical.

These cases run the verifier against a database built through the API and left alone.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'scripts'))

from app import migrate  # noqa: E402
from app.db import Workspace  # noqa: E402
from app.main import create_app  # noqa: E402
from app.settings import Settings  # noqa: E402
from conftest import HEADERS, PASSWORD  # noqa: E402

import verify_restore  # noqa: E402

AMAZON = 'https://www.amazon.com/dp/B0ABCDEFGH'
INPUTS = {'quantity': 300, 'unit_cost_usd': 8.4, 'fx_ngn': 1500, 'freight_ngn': 900000, 'duty_pct': 5,
          'import_tax_pct': 7.5, 'selling_price_ngn': 32000, 'channel_fee_pct': 5, 'returns_pct': 3,
          'marketing_ngn': 300000, 'fixed_cost_ngn': 150000, 'stress_pct': 10,
          'compliance': 'unresolved', 'channel': 'Direct sales', 'shipping': 'Air'}


def evidence_body(metric, market, source):
    return {'metric': metric, 'value': 68, 'unit': 'index / 100', 'market': market,
            'observed_at': (datetime.now(timezone.utc) - timedelta(days=5)).strftime('%Y-%m-%d'),
            'source_name': source, 'source_url': 'https://example.test/series',
            'method': 'Read the latest weekly point from the exported series.', 'notes': ''}


@pytest.fixture
def file_database(tmp_path):
    """A real file the verifier can open with its own engine, as it would a restore."""
    return f'sqlite:///{tmp_path / "restored.db"}'


@pytest.fixture
def populated(file_database):
    """A workspace with evidence-bearing saved assessments, then left untouched."""
    app = create_app(Settings(environment='test', database_url=file_database,
                              origins=('http://localhost:3000',), allow_registration=True,
                              research_daily_limit=20))
    with TestClient(app) as client:
        client.post('/api/v1/auth/register',
                    json={'email': 'owner@example.com', 'password': PASSWORD, 'name': 'Recovery workspace'},
                    headers=HEADERS)
        job = client.post('/api/v1/xray', json={'input': AMAZON},
                          headers={**HEADERS, 'Idempotency-Key': 'p06'}).json()
        product_id = job['product_id']
        client.post(f'/api/v1/products/{product_id}/confirm', json={'name': 'Steamer'}, headers=HEADERS)
        for metric, market in [('Search interest', 'US'), ('Review velocity', 'US'),
                               ('Marketplace rank', 'US'), ('Local listing price', 'NG')]:
            client.post(f'/api/v1/products/{product_id}/evidence',
                        json=evidence_body(metric, market, f'{metric} source'), headers=HEADERS)
        # Two assessments, as the review's reproduction had.
        for key in ('one', 'two'):
            saved = client.post('/api/v1/decisions', json={'product_id': product_id, 'inputs': INPUTS},
                                headers={**HEADERS, 'Idempotency-Key': key})
            assert saved.status_code == 201, saved.text
        # A real restore carries a migrated schema, so the revision check is meaningful.
        migrate.stamp_engine(app.state.database.engine, migrate.head_revision(file_database))
        app.state.database.engine.dispose()
    return file_database


def test_an_untouched_database_with_evidence_passes_verification(populated):
    """The regression itself: nothing is wrong, so nothing may be reported wrong."""
    report = verify_restore.inspect_database(populated)
    assert report['assessments_checked'] == 2
    assert report['assessment_replay_failures'] == []


def test_the_verifier_exits_zero_on_an_untouched_database(populated, capsys):
    assert verify_restore.main(['--url', populated]) == 0


def test_a_legacy_assessment_without_an_evidence_reading_still_replays(populated):
    """Records saved before evidence existed carry no reading, and must stay valid."""
    from app.db import Database, Record
    database = Database(populated)
    with database.session() as db:
        row = db.query(Record).filter_by(kind='decision').first()
        payload = dict(row.payload)
        payload.pop('evidence_quality', None)
        payload.pop('threshold_version', None)
        # A pre-evidence assessment: no reading, no gates version, zero confidence.
        from app.economics import Inputs, calculate
        legacy = calculate(Inputs(**payload['inputs']),
                           formula_version=payload['formula_version'],
                           threshold_version=verify_restore.LEGACY_THRESHOLD_VERSION)
        payload.update({field: legacy[field] for field in verify_restore.REPLAYED_FIELDS})
        row.payload = payload
        db.commit()
    database.engine.dispose()

    report = verify_restore.inspect_database(populated)
    assert report['assessment_replay_failures'] == []


def test_a_tampered_assessment_is_still_reported(populated):
    """The check must keep failing for the reason it exists."""
    from app.db import Database, Record
    database = Database(populated)
    with database.session() as db:
        row = db.query(Record).filter_by(kind='decision').first()
        row.payload = {**row.payload, 'decision': 'GO'}
        db.commit()
    database.engine.dispose()

    report = verify_restore.inspect_database(populated)
    assert len(report['assessment_replay_failures']) == 1
    assert 'decision' in report['assessment_replay_failures'][0]['fields']
    assert verify_restore.main(['--url', populated]) == 1


def test_workspaces_sharing_a_display_name_are_reconciled_separately(populated):
    """Grouping by name merged two tenants into one row and hid a tenant that lost rows."""
    from app.db import Database
    database = Database(populated)
    with database.session() as db:
        existing = db.query(Workspace).one()
        db.add(Workspace(name=existing.name))   # a second workspace, same display name
        db.commit()
    database.engine.dispose()

    report = verify_restore.inspect_database(populated)
    assert len(report['workspaces']) == 2, 'two workspaces, not one merged row'
    names = {entry['name'] for entry in report['workspaces'].values()}
    assert names == {'Recovery workspace'}
    assert sorted(entry['records'] for entry in report['workspaces'].values())[0] == 0


def test_the_report_counts_the_new_record_kinds(populated):
    report = verify_restore.inspect_database(populated)
    assert report['records_by_kind']['evidence'] == 4
    assert report['records_by_kind']['decision'] == 2
