#!/usr/bin/env python3
"""Reapply durable deletion requests to a restored TrendSell database.

This command is intentionally hard to point at a database by accident: the operator must
repeat the parsed database name with ``--confirm-database``.  It verifies every register
entry before opening the write transaction and is idempotent, so a failed restore drill
can be repeated safely.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app import migrate  # noqa: E402
from app.db import Workspace  # noqa: E402
from app.deletions import DeletionRegister, DeletionRegisterError, replay  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Replay the out-of-band deletion register into a RESTORED database')
    parser.add_argument('--url', required=True,
                        help='database URL for the restored copy (never the live URL)')
    parser.add_argument('--register-dir', required=True,
                        help='verified deletion-register directory')
    parser.add_argument('--confirm-database', required=True,
                        help='repeat the target database name to authorize writes')
    args = parser.parse_args(argv)

    parsed = make_url(args.url)
    database_name = parsed.database or ''
    if not database_name or args.confirm_database != database_name:
        parser.error('--confirm-database must exactly match the database name parsed from --url')

    register = DeletionRegister(args.register_dir)
    try:
        entries = register.entries(prepare=False)
    except DeletionRegisterError as error:
        print(f'FAIL: {error}', file=sys.stderr)
        return 1

    engine = create_engine(args.url)
    try:
        report = migrate.check(args.url)
        if (not report['matches_models'] or not report['up_to_date']
                or report['unexpected_tables'] or report['unexpected_columns']):
            print('FAIL: restored database schema does not match this candidate', file=sys.stderr)
            return 1
        Session = sessionmaker(engine, expire_on_commit=False)
        with Session.begin() as db:
            result = replay(db, entries)
        with Session() as db:
            remaining = [entry['workspace_id'] for entry in entries
                         if db.get(Workspace, entry['workspace_id']) is not None]
        if remaining:
            print(f'FAIL: {len(remaining)} registered workspace deletions remain', file=sys.stderr)
            return 1
        print(f'PASS: verified {result.entries} deletion-register entries; '
              f'removed {result.workspaces_deleted} restored workspaces; none remain')
        return 0
    finally:
        engine.dispose()


if __name__ == '__main__':
    sys.exit(main())
