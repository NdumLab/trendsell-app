"""Schema state and migrations (action plan P01).

Production deliberately does not call ``create_all()``. Until now that meant the running
installation had a schema created once by an untracked script and no upgrade path at all.
This module supplies the missing pieces:

``check``    report the database's current revision, the revision the code expects, and
             whether the physical tables match — without changing anything.
``upgrade``  run outstanding migrations.
``stamp``    adopt an existing, already-correct schema by writing the baseline revision.
             It refuses unless the schema really matches, so it can never be used to skip
             a migration or to mark an empty database as migrated.

Run it as ``python -m app.migrate <command>`` from ``backend/``.
"""
import argparse
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from tempfile import NamedTemporaryFile

from sqlalchemy import create_engine, inspect

from .db import Base
from .settings import Settings

BACKEND = Path(__file__).resolve().parents[1]
BASELINE = '0001_pilot_baseline'
#:  adopts the baseline only; anything after it must be run, not stamped.


def alembic_config(url):
    config = Config(str(BACKEND / 'alembic.ini'))
    config.set_main_option('script_location', str(BACKEND / 'migrations'))
    # Via attributes, not set_main_option: alembic.ini is a ConfigParser file, and a URL
    # containing '%' — a percent-encoded option, or an escaped character in a password —
    # would be read as interpolation syntax and raise.
    config.attributes['database_url'] = url
    return config


def head_revision(url):
    return ScriptDirectory.from_config(alembic_config(url)).get_current_head()


def current_revision(engine):
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def model_schema():
    """Table and column names the ORM models declare, i.e. what head must produce."""
    return {name: set(table.columns.keys()) for name, table in Base.metadata.tables.items()}


def revision_schema(revision):
    """Table and column names a given revision produces.

    Built by migrating a scratch in-memory database to that revision, so it stays correct
    without a second hand-written description to drift. `stamp` needs this: the installation
    being adopted matches the *baseline*, not necessarily the current models.
    """
    with NamedTemporaryFile(suffix='.db') as scratch:
        url = f'sqlite:///{scratch.name}'
        upgrade(url, revision)
        engine = create_engine(url)
        try:
            inspector = inspect(engine)
            return {name: {column['name'] for column in inspector.get_columns(name)}
                    for name in inspector.get_table_names() if name != 'alembic_version'}
        finally:
            engine.dispose()


def schema_report(engine, expected_schema=None):
    """What the database physically has, against what is expected of it.

    `expected_schema` defaults to the ORM models — the right comparison for readiness.
    `stamp` passes the baseline revision's schema instead.
    """
    inspector = inspect(engine)
    present = set(inspector.get_table_names())
    expectation = expected_schema or model_schema()
    expected = set(expectation)
    missing_columns = {}
    for name in sorted(expected & present):
        declared = expectation[name]
        actual = {column['name'] for column in inspector.get_columns(name)}
        if declared - actual:
            missing_columns[name] = sorted(declared - actual)
    return {
        'tables_present': sorted(present),
        'missing_tables': sorted(expected - present),
        'unexpected_tables': sorted(present - expected - {'alembic_version'}),
        'missing_columns': missing_columns,
        'matches_models': not (expected - present) and not missing_columns,
        'is_empty': not (present - {'alembic_version'}),
    }


def check(url):
    engine = create_engine(url)
    try:
        report = schema_report(engine)
        report['current_revision'] = current_revision(engine)
        report['head_revision'] = head_revision(url)
        report['up_to_date'] = report['current_revision'] == report['head_revision']
        return report
    finally:
        engine.dispose()


def stamp_engine(engine, revision=BASELINE):
    """Adopt an existing schema on an open engine. Refuses anything but a match.

    An empty database must be migrated, not stamped; a database with a revision already
    recorded is left alone; a schema missing what `revision` produces is a problem to fix,
    not to paper over. Extra columns are tolerated, because a database further ahead than
    the baseline still contains everything the baseline describes — the later revisions are
    then run normally.
    """
    report = schema_report(engine, revision_schema(revision))
    existing = current_revision(engine)
    if existing is not None:
        raise SystemExit(f'Database already records revision {existing}. Run `upgrade` instead of `stamp`.')
    if report['is_empty']:
        raise SystemExit('Database is empty. Run `upgrade` to create the schema; stamping would skip it.')
    if not report['matches_models']:
        raise SystemExit(f'Schema does not match revision {revision}, so it cannot be adopted.\n'
                         f'  missing tables: {report["missing_tables"] or "none"}\n'
                         f'  missing columns: {report["missing_columns"] or "none"}')
    config = alembic_config(str(engine.url))
    with engine.begin() as connection:
        config.attributes['connection'] = connection
        command.stamp(config, revision)
    return report


def stamp_baseline(url, revision=BASELINE):
    engine = create_engine(url)
    try:
        return stamp_engine(engine, revision)
    finally:
        engine.dispose()


def upgrade(url, revision='head'):
    command.upgrade(alembic_config(url), revision)


def downgrade(url, revision):
    command.downgrade(alembic_config(url), revision)


def main(argv=None):
    parser = argparse.ArgumentParser(description='TrendSell schema management')
    parser.add_argument('action', choices=['check', 'upgrade', 'stamp'])
    parser.add_argument('--url', help='Database URL. Defaults to the application settings.')
    parser.add_argument('--revision', default=None,
                        help='upgrade target (default head), or the revision to stamp (default the baseline)')
    args = parser.parse_args(argv)
    url = args.url or Settings.from_env().database_url

    if args.action == 'check':
        report = check(url)
        for key in ('current_revision', 'head_revision', 'up_to_date', 'matches_models',
                    'missing_tables', 'missing_columns', 'unexpected_tables'):
            print(f'{key}: {report[key]}')
        return 0 if report['up_to_date'] and report['matches_models'] else 1
    if args.action == 'upgrade':
        upgrade(url, args.revision or 'head')
        print(f'upgraded to {current_revision(create_engine(url))}')
        return 0
    revision = args.revision or BASELINE
    stamp_baseline(url, revision)
    print(f'stamped existing schema as {revision}. Run `upgrade` to apply any later revisions.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
