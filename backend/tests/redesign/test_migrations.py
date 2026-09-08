"""Tracked migrations against fresh and existing schemas (action plan P01).

Review finding 15: production skips `create_all()` but the repository had no Alembic
configuration or revisions. The host had an untracked `bootstrap_schema.py` that created
the tables once, so the running installation worked but had no upgrade path.

Two adoption paths must both hold, and neither may destroy data:

* an empty database reaches head by *running* the migration;
* a database whose schema already matches is *stamped*, never re-created.
"""
import pytest
from sqlalchemy import create_engine, text

from app import migrate
from app.db import Database, Record, Workspace
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


def seed(url):
    """A workspace and a record, written through the models exactly as the API does."""
    database = Database(url)
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
    assert after['current_revision'] == after['head_revision'] == migrate.BASELINE
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


def test_an_existing_schema_is_adopted_without_touching_its_data(blank_url):
    seed(blank_url)
    assert rows(blank_url, 'records') == 1

    report = migrate.stamp_baseline(blank_url)
    assert report['matches_models'] is True

    state = migrate.check(blank_url)
    assert state['current_revision'] == migrate.BASELINE
    assert state['up_to_date'] is True
    assert rows(blank_url, 'records') == 1
    assert rows(blank_url, 'workspaces') == 1


def test_upgrading_an_adopted_database_is_a_no_op_that_keeps_every_record(blank_url):
    seed(blank_url)
    migrate.stamp_baseline(blank_url)
    migrate.upgrade(blank_url)
    assert rows(blank_url, 'records') == 1
    assert migrate.check(blank_url)['up_to_date'] is True


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
    assert 'does not match the models' in str(refused.value)
    assert 'records' in str(refused.value)


def test_the_baseline_refuses_to_downgrade(blank_url):
    """Dropping the baseline would destroy every customer record; restore a backup instead."""
    migrate.upgrade(blank_url)
    with pytest.raises(Exception) as refused:
        migrate.downgrade(blank_url, 'base')
    assert 'cannot be downgraded' in str(refused.value)
    assert migrate.check(blank_url)['matches_models'] is True


def test_a_url_containing_percent_encoding_is_handled(blank_url):
    """A password or option with '%' must not be read as ConfigParser interpolation."""
    assert migrate.head_revision(blank_url) == migrate.BASELINE
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
    assert body['expected_revision'] == migrate.BASELINE


def test_readiness_reports_ready_once_the_schema_is_stamped(client):
    # Stamp through the app's own engine: the suite's `sqlite://` is in-memory, so a
    # second engine on the same URL would be a different, empty database.
    migrate.stamp_engine(client.app.state.database.engine)
    response = client.get('/api/ready')
    assert response.status_code == 200
    assert response.json() == {'status': 'ready', 'database': 'ok',
                               'schema_revision': migrate.BASELINE, 'expected_revision': migrate.BASELINE}


def test_liveness_stays_independent_of_the_database(client):
    body = client.get('/api/health').json()
    assert body['status'] == 'ok'
    assert body['demo'] is False
