#!/usr/bin/env python3
"""Verify TrendSell runtime and migration PostgreSQL roles without printing secrets."""
import json
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))

from sqlalchemy import create_engine, text  # noqa: E402

from app.db import Base  # noqa: E402


APP_TABLES = sorted({*Base.metadata.tables, 'alembic_version'})


def scalar(connection, statement, **parameters):
    return connection.execute(text(statement), parameters).scalar()


def role_report(url, expected_kind, allow_non_tls=False):
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            identity = connection.execute(text(
                'SELECT current_user, current_database(), '
                "current_setting('server_version_num')::int"
            )).one()
            flags = connection.execute(text(
                'SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls '
                'FROM pg_roles WHERE rolname = current_user')).one()
            ssl = bool(scalar(connection,
                              'SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid()'))
            tables = {row[0] for row in connection.execute(text(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"))}
            missing = sorted(set(APP_TABLES) - tables)
            table_privileges = {}
            for table in sorted(set(APP_TABLES) & tables):
                table_privileges[table] = {
                    privilege: bool(scalar(
                        connection, 'SELECT has_table_privilege(current_user, :table, :privilege)',
                        table=f'public.{table}', privilege=privilege))
                    for privilege in ('SELECT', 'INSERT', 'UPDATE', 'DELETE',
                                      'TRUNCATE', 'REFERENCES', 'TRIGGER')
                }
            database_create = bool(scalar(
                connection,
                "SELECT has_database_privilege(current_user, current_database(), 'CREATE')"))
            database_temp = bool(scalar(
                connection,
                "SELECT has_database_privilege(current_user, current_database(), 'TEMP')"))
            schema_create = bool(scalar(
                connection,
                "SELECT has_schema_privilege(current_user, 'public', 'CREATE')"))
            owned = {row[0] for row in connection.execute(text(
                "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                "WHERE n.nspname='public' AND c.relkind IN ('r','p','S','v') "
                'AND pg_get_userbyid(c.relowner)=current_user'))}

            # Exercise real work inside a transaction that is always rolled back. Catalog
            # grants alone can overlook ownership/membership behavior.
            connection.rollback()
            exercise = 'not-run'
            transaction = connection.begin()
            try:
                if expected_kind == 'runtime':
                    marker = str(uuid.uuid4())
                    connection.execute(text(
                        'INSERT INTO workspaces (id, name) VALUES (:id, :name)'),
                        {'id': marker, 'name': 'role-check'})
                    connection.execute(text(
                        'UPDATE workspaces SET name=:name WHERE id=:id'),
                        {'id': marker, 'name': 'role-check-updated'})
                    connection.execute(text('SELECT name FROM workspaces WHERE id=:id'),
                                       {'id': marker}).one()
                    connection.execute(text('DELETE FROM workspaces WHERE id=:id'),
                                       {'id': marker})
                    exercise = 'runtime CRUD rolled back'
                else:
                    connection.execute(text(
                        'CREATE TABLE public.trendsell_migration_role_check (id integer)'))
                    connection.execute(text(
                        'ALTER TABLE public.trendsell_migration_role_check ADD COLUMN note text'))
                    exercise = 'migration DDL rolled back'
            finally:
                transaction.rollback()

        problems = []
        if any(flags):
            problems.append('role has a superuser/createdb/createrole/replication/bypassrls flag')
        if not ssl and not allow_non_tls:
            problems.append('connection is not protected by PostgreSQL TLS')
        if missing:
            problems.append(f'missing application tables: {missing}')
        if expected_kind == 'runtime':
            required = {'SELECT', 'INSERT', 'UPDATE', 'DELETE'}
            forbidden = {'TRUNCATE', 'REFERENCES', 'TRIGGER'}
            for table, privileges in table_privileges.items():
                table_required = {'SELECT'} if table == 'alembic_version' else required
                absent = sorted(name for name in table_required if not privileges[name])
                broad = sorted(name for name in forbidden if privileges[name])
                if table == 'alembic_version':
                    broad += sorted(name for name in ('INSERT', 'UPDATE', 'DELETE')
                                    if privileges[name])
                if absent:
                    problems.append(f'{table} lacks runtime DML: {absent}')
                if broad:
                    problems.append(f'{table} has broad runtime rights: {broad}')
            if database_create or database_temp or schema_create:
                problems.append('runtime can create database/schema/temporary objects')
            if owned:
                problems.append(f'runtime owns schema objects: {sorted(owned)}')
        else:
            if not schema_create:
                problems.append('migration role cannot create schema objects')
            unowned = sorted((set(APP_TABLES) & tables) - owned)
            if unowned:
                problems.append(f'migration role does not own: {unowned}')

        return {
            'kind': expected_kind,
            'role': identity.current_user,
            'database': identity.current_database,
            'server_version_num': identity[2],
            'tls': ssl,
            'allow_non_tls': allow_non_tls,
            'tables_checked': len(table_privileges),
            'database_create': database_create,
            'database_temp': database_temp,
            'schema_create': schema_create,
            'owned_objects': sorted(owned),
            'exercise': exercise,
            'problems': problems,
        }
    finally:
        engine.dispose()


def main():
    runtime_url = os.getenv('TRENDSELL_RUNTIME_DATABASE_URL', '')
    migration_url = os.getenv('TRENDSELL_MIGRATION_DATABASE_URL', '')
    allow_non_tls = os.getenv('TRENDSELL_ALLOW_NON_TLS_DATABASE_TEST', '') == 'yes'
    if not runtime_url or not migration_url:
        print('TRENDSELL_RUNTIME_DATABASE_URL and TRENDSELL_MIGRATION_DATABASE_URL are required',
              file=sys.stderr)
        return 2
    reports = [role_report(runtime_url, 'runtime', allow_non_tls),
               role_report(migration_url, 'migration', allow_non_tls)]
    if reports[0]['role'] == reports[1]['role']:
        reports[0]['problems'].append('runtime and migration resolve to the same role')
    print(json.dumps({'roles': reports}, indent=2, sort_keys=True))
    problems = [problem for report in reports for problem in report['problems']]
    if problems:
        for problem in problems:
            print(f'FAIL: {problem}', file=sys.stderr)
        return 1
    print('PASS: runtime is DML-only; migration owns schema objects; roles are separate')
    return 0


if __name__ == '__main__':
    sys.exit(main())
