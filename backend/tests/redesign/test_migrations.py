"""Tracked migrations against fresh and existing schemas (action plan P01).

Review finding 15: production skips `create_all()` but the repository had no Alembic
configuration or revisions. The host had an untracked `bootstrap_schema.py` that created
the tables once, so the running installation worked but had no upgrade path.

Two adoption paths must both hold, and neither may destroy data:

* an empty database reaches head by *running* the migration;
* a database whose schema already matches is *stamped*, never re-created.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app import migrate
from app.db import Database, Record, Workspace
from app.main import create_app
from app.settings import Settings
from conftest import POSTGRES_URL, postgres_schema_url


@pytest.fixture(params=['sqlite', 'postgres'])
def blank_url(request, tmp_path):
    """An empty database on each supported engine. PostgreSQL is skipped when unconfigured."""
    if request.param == 'sqlite':
        yield f'sqlite:///{tmp_path / "migrate.db"}'
        return
    if not POSTGRES_URL:
        pytest.skip('TEST_POSTGRES_URL is not configured')
    url, drop = postgres_schema_url(POSTGRES_URL)
    try:
        yield url
    finally:
        drop()


def seed(url, revision=None):
    """A workspace and a record in a database at `revision` (default: the current models).

    Passing the baseline reproduces the installation that is about to be adopted: its
    schema is one revision behind the code that will adopt it.
    """
    if revision:
        # Build the schema, then drop the version table: the installation being adopted was
        # created by hand and has never recorded a revision.
        migrate.upgrade(url, revision)
        engine = create_engine(url)
        with engine.connect() as connection:
            connection.execute(text('DROP TABLE alembic_version'))
            connection.commit()
        engine.dispose()
    database = Database(url)
    if not revision:
        database.create()
    with database.session() as db:
        workspace = Workspace(name='Existing workspace')
        db.add(workspace)
        db.flush()
        db.add(Record(workspace_id=workspace.id, kind='product', key='B0PREEXIST',
                      payload={'name': 'Pre-existing product', 'confirmed': True},
                      created_at='2026-01-01T00:00:00+00:00'))
        db.commit()
    database.engine.dispose()


def rows(url, table):
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            return connection.execute(text(f'SELECT COUNT(*) FROM {table}')).scalar()
    finally:
        engine.dispose()


def test_an_empty_database_reaches_head_by_migrating(blank_url):
    before = migrate.check(blank_url)
    assert before['current_revision'] is None
    assert before['is_empty'] is True

    migrate.upgrade(blank_url)

    after = migrate.check(blank_url)
    assert after['current_revision'] == after['head_revision']
    assert after['head_revision'] != migrate.BASELINE, 'the chain should be past the baseline by now'
    assert after['up_to_date'] is True
    assert after['matches_models'] is True
    assert after['missing_tables'] == [] and after['missing_columns'] == {}


def test_a_migrated_database_serves_the_application(blank_url):
    """The migration must produce the schema the models actually use, not an approximation."""
    migrate.upgrade(blank_url)
    database = Database(blank_url)
    with database.session() as db:
        workspace = Workspace(name='After migration')
        db.add(workspace)
        db.flush()
        db.add(Record(workspace_id=workspace.id, kind='product', key='B0AFTER0001',
                      payload={'name': 'Written after migrating'}, created_at='2026-02-01T00:00:00+00:00'))
        db.commit()
    with database.session() as db:
        stored = db.query(Record).one()
        assert stored.payload['name'] == 'Written after migrating'
    database.engine.dispose()


def test_a_baseline_era_schema_is_adopted_without_touching_its_data(blank_url):
    """The installation being adopted matches the baseline, not necessarily the models."""
    seed(blank_url, revision=migrate.BASELINE)
    assert rows(blank_url, 'records') == 1

    report = migrate.stamp_baseline(blank_url)
    assert report['matches_models'] is True   # matches the baseline schema it was checked against

    state = migrate.check(blank_url)
    assert state['current_revision'] == migrate.BASELINE
    assert rows(blank_url, 'records') == 1
    assert rows(blank_url, 'workspaces') == 1


def test_an_adopted_database_then_upgrades_to_head_keeping_every_record(blank_url):
    """Adoption is step one; the later revisions are run, not stamped."""
    seed(blank_url, revision=migrate.BASELINE)
    migrate.stamp_baseline(blank_url)
    assert migrate.check(blank_url)['up_to_date'] is False

    migrate.upgrade(blank_url)

    state = migrate.check(blank_url)
    assert state['up_to_date'] is True
    assert state['matches_models'] is True
    assert rows(blank_url, 'records') == 1
    assert rows(blank_url, 'workspaces') == 1


def test_stamping_an_empty_database_is_refused(blank_url):
    """Stamping an empty database would mark a missing schema as migrated."""
    with pytest.raises(SystemExit) as refused:
        migrate.stamp_baseline(blank_url)
    assert 'empty' in str(refused.value)
    assert migrate.check(blank_url)['current_revision'] is None


def test_stamping_an_already_stamped_database_is_refused(blank_url):
    migrate.upgrade(blank_url)
    with pytest.raises(SystemExit) as refused:
        migrate.stamp_baseline(blank_url)
    assert 'already records revision' in str(refused.value)


def test_stamping_a_partial_schema_is_refused(blank_url):
    engine = create_engine(blank_url)
    with engine.connect() as connection:
        connection.execute(text('CREATE TABLE workspaces (id VARCHAR PRIMARY KEY, name VARCHAR)'))
        connection.commit()
    engine.dispose()
    with pytest.raises(SystemExit) as refused:
        migrate.stamp_baseline(blank_url)
    assert 'does not match revision' in str(refused.value)
    assert 'records' in str(refused.value)


def test_the_baseline_refuses_to_downgrade(blank_url):
    """Dropping the baseline would destroy every customer record; restore a backup instead."""
    migrate.upgrade(blank_url)
    seed(blank_url)
    with pytest.raises(Exception) as refused:
        migrate.downgrade(blank_url, 'base')
    assert 'cannot be downgraded' in str(refused.value)
    # How far the chain unwound before the refusal depends on whether the engine runs DDL
    # transactionally — PostgreSQL rolls the whole attempt back, SQLite keeps 0002's part.
    # What must hold on both: the baseline never came off, so the rows are still there.
    assert migrate.check(blank_url)['current_revision'] in {migrate.BASELINE, migrate.head_revision(blank_url)}
    assert rows(blank_url, 'records') == 1
    migrate.upgrade(blank_url)
    assert migrate.check(blank_url)['matches_models'] is True


def test_a_later_revision_is_reversible_so_a_release_can_roll_back(blank_url):
    """Additive revisions after the baseline must come off again without data loss."""
    migrate.upgrade(blank_url)
    seed(blank_url)
    migrate.downgrade(blank_url, migrate.BASELINE)
    assert migrate.check(blank_url)['current_revision'] == migrate.BASELINE
    assert rows(blank_url, 'records') == 1
    migrate.upgrade(blank_url)
    assert migrate.check(blank_url)['up_to_date'] is True
    assert rows(blank_url, 'records') == 1


def test_a_baseline_era_schema_is_missing_what_later_revisions_add(blank_url):
    """The check that makes adoption safe: the two schemas really are different."""
    baseline = migrate.revision_schema(migrate.BASELINE)
    head = migrate.revision_schema('head')
    assert baseline['rate_buckets'] < head['rate_buckets']
    assert 'expires_at' in head['rate_buckets'] and 'expires_at' not in baseline['rate_buckets']


def test_a_url_containing_percent_encoding_is_handled(blank_url):
    """A password or option with '%' must not be read as ConfigParser interpolation."""
    assert migrate.head_revision(blank_url) == migrate.head_revision('sqlite://')
    if POSTGRES_URL:
        assert '%' in blank_url or blank_url.startswith('sqlite')


# --- Readiness reports schema state, not just connectivity -------------------------

def test_readiness_reports_a_schema_mismatch_rather_than_serving(client):
    """The suite's databases are created with create_all(), so no revision is recorded."""
    response = client.get('/api/ready')
    assert response.status_code == 503
    body = response.json()
    assert body['status'] == 'schema_mismatch'
    assert body['database'] == 'ok'
    assert body['schema_revision'] is None
    assert body['expected_revision'] == migrate.head_revision('sqlite://')


def test_readiness_reports_ready_once_the_schema_is_at_head(client):
    # Stamp through the app's own engine: the suite's `sqlite://` is in-memory, so a
    # second engine on the same URL would be a different, empty database. create_all()
    # produced the head schema, so head is the honest revision to record.
    head = migrate.head_revision('sqlite://')
    migrate.stamp_engine(client.app.state.database.engine, head)
    response = client.get('/api/ready')
    assert response.status_code == 200
    assert response.json() == {'status': 'ready', 'database': 'ok',
                               'schema_revision': head, 'expected_revision': head,
                               'schema_matches_models': True}


def test_liveness_stays_independent_of_the_database(client):
    body = client.get('/api/health').json()
    assert body['status'] == 'ok'
    assert body['demo'] is False


# --- Readiness inspects the physical schema, not only the revision label (R09) ------

@pytest.fixture
def eager_client(database_url):
    """A client whose readiness never reuses a cached schema verdict.

    The production default reuses its verdict for 30 seconds so a liveness-frequency
    probe does not inspect tables on every call. These tests are about *what* the
    inspection concludes, so they set the interval to zero rather than sleeping.
    """
    settings = Settings(environment='test', database_url=database_url,
                        origins=('http://localhost:3000',), schema_recheck_seconds=0)
    with TestClient(create_app(settings)) as client:
        yield client


def break_schema(engine, statement):
    with engine.begin() as connection:
        connection.execute(text(statement))


def set_revision(engine, revision):
    """Rewrite the recorded revision the way a migration would.

    `stamp_engine` deliberately refuses to overwrite an existing revision, so these
    tests write the row directly to stage a database whose *label* says one thing.
    """
    with engine.begin() as connection:
        connection.execute(text('DELETE FROM alembic_version'))
        connection.execute(text('INSERT INTO alembic_version (version_num) VALUES (:v)'),
                           {'v': revision})


def test_readiness_rejects_a_head_revision_whose_tables_are_missing(eager_client):
    """Review finding R09: the revision row is a claim about the schema, not the schema.

    A database migrated to head and then missing `audit_events` answered `SELECT 1`,
    still carried the 0003 row, and reported ready — while every audited write against
    it would have failed.
    """
    head = migrate.head_revision('sqlite://')
    engine = eager_client.app.state.database.engine
    migrate.stamp_engine(engine, head)
    assert eager_client.get('/api/ready').status_code == 200

    break_schema(engine, 'DROP TABLE audit_events')

    response = eager_client.get('/api/ready')
    assert response.status_code == 503
    body = response.json()
    assert body['status'] == 'schema_incomplete'
    # The revision label is untouched: only inspection can catch this.
    assert body['schema_revision'] == head == body['expected_revision']
    assert body['schema_matches_models'] is False
    # Named, so an operator knows what to restore rather than only that it failed.
    assert 'audit_events' in body['missing_tables']


def test_readiness_rejects_a_head_revision_whose_column_is_missing(eager_client):
    """A table can be present and still not be the table the models declare."""
    head = migrate.head_revision('sqlite://')
    engine = eager_client.app.state.database.engine
    migrate.stamp_engine(engine, head)
    assert eager_client.get('/api/ready').status_code == 200

    break_schema(engine, 'ALTER TABLE audit_events DROP COLUMN detail')

    body = eager_client.get('/api/ready').json()
    assert body['status'] == 'schema_incomplete'
    assert body['schema_matches_models'] is False
    assert body['missing_columns']['audit_events'] == ['detail']
    # The table itself is present, so a table-only check would have passed this database.
    assert body['missing_tables'] == []


def test_a_wrong_revision_is_reported_as_a_mismatch_not_an_incomplete_schema(eager_client):
    """The two failures are distinct: a stale label and a broken schema differ in remedy."""
    migrate.stamp_engine(eager_client.app.state.database.engine, migrate.BASELINE)
    body = eager_client.get('/api/ready').json()
    assert body['status'] == 'schema_mismatch'
    assert body['schema_revision'] == migrate.BASELINE
    # The physical schema is fine here; only the recorded revision is behind.
    assert body['schema_matches_models'] is True


def test_readiness_rechecks_the_schema_as_soon_as_the_revision_changes(client):
    """The cache must not outlive a migration: a revision change refreshes immediately.

    Without this, a deploy that migrated between two probes would keep serving the
    previous verdict for the whole recheck interval. This uses the *default* client, so
    the 30-second interval is in force and only the revision change can explain the
    refreshed answer.
    """
    engine = client.app.state.database.engine
    migrate.stamp_engine(engine, migrate.BASELINE)
    assert client.get('/api/ready').json()['status'] == 'schema_mismatch'

    set_revision(engine, migrate.head_revision('sqlite://'))
    # No sleep: the changed revision, not the elapsed interval, forces the re-inspection.
    assert client.get('/api/ready').json()['status'] == 'ready'


def test_readiness_does_not_inspect_the_schema_on_every_probe(client, monkeypatch):
    """R09 asked for this check *without* making a liveness-frequency endpoint do real work."""
    migrate.stamp_engine(client.app.state.database.engine, migrate.head_revision('sqlite://'))
    client.get('/api/ready')

    calls = []
    original = migrate.schema_report
    monkeypatch.setattr(migrate, 'schema_report',
                        lambda engine, *a, **k: (calls.append(1), original(engine, *a, **k))[1])
    for _ in range(5):
        assert client.get('/api/ready').status_code == 200
    assert calls == []
