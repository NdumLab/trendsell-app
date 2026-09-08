"""Check that a restored TrendSell database is actually usable (action plan P06).

A dump that loads is not proof of recovery. This walks the restored copy and reports:

* table counts and the recorded schema revision;
* record counts per workspace, so a tenant that lost rows is visible rather than averaged
  away in a total;
* whether every saved assessment still replays to the values it was stored with, under the
  formula version it recorded.

The last check is the one that matters for this product: a restore that returns rows but
whose assessments no longer reproduce is not a recovery of the decisions people made.

    python scripts/verify_restore.py --url postgresql+psycopg://.../restored
    python scripts/verify_restore.py --url ... --expect counts.json   # compare to a baseline
    python scripts/verify_restore.py --url ... --write-expect counts.json

Exit code 0 when every check passes.
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))

from sqlalchemy import create_engine, func, select  # noqa: E402

from app import migrate  # noqa: E402
from app.db import Record, Workspace  # noqa: E402
from app.economics import Inputs, calculate  # noqa: E402

REPLAYED_FIELDS = ('decision', 'scenarios', 'blockers', 'confidence', 'currency', 'market')


def inspect_database(url):
    engine = create_engine(url)
    try:
        report = migrate.schema_report(engine)
        report['schema_revision'] = migrate.current_revision(engine)
        report['expected_revision'] = migrate.head_revision(url)
        with engine.connect() as connection:
            report['workspaces'] = {
                name: count for name, count in connection.execute(
                    select(Workspace.name, func.count(Record.id))
                    .select_from(Workspace).outerjoin(Record, Record.workspace_id == Workspace.id)
                    .group_by(Workspace.name)).all()
            }
            kinds = Counter()
            replay_failures = []
            checked = 0
            for record in connection.execute(select(Record.id, Record.kind, Record.payload)).mappings():
                kinds[record['kind']] += 1
                if record['kind'] != 'decision':
                    continue
                payload = record['payload']
                checked += 1
                try:
                    replayed = calculate(Inputs(**payload['inputs']),
                                         formula_version=payload['formula_version'])
                except Exception as error:  # noqa: BLE001 - report, do not abort the sweep
                    replay_failures.append({'id': record['id'], 'error': repr(error)})
                    continue
                differing = [field for field in REPLAYED_FIELDS if replayed[field] != payload[field]]
                if differing:
                    replay_failures.append({'id': record['id'], 'fields': differing,
                                            'formula_version': payload['formula_version']})
            report['records_by_kind'] = dict(sorted(kinds.items()))
            report['assessments_checked'] = checked
            report['assessment_replay_failures'] = replay_failures
        return report
    finally:
        engine.dispose()


def comparable(report):
    """The parts of a report that a restore must reproduce exactly."""
    return {'workspaces': report['workspaces'], 'records_by_kind': report['records_by_kind']}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Verify a restored TrendSell database')
    parser.add_argument('--url', required=True, help='URL of the RESTORED database, not the live one')
    parser.add_argument('--expect', help='JSON baseline produced by --write-expect on the source')
    parser.add_argument('--write-expect', help='Write this database\'s counts as a baseline and exit')
    args = parser.parse_args(argv)

    report = inspect_database(args.url)
    if args.write_expect:
        Path(args.write_expect).write_text(json.dumps(comparable(report), indent=2, sort_keys=True) + '\n')
        print(f'wrote baseline to {args.write_expect}')
        return 0

    print(json.dumps(report, indent=2, sort_keys=True, default=str))
    problems = []
    if not report['matches_models']:
        problems.append(f'schema does not match the models: missing {report["missing_tables"]}')
    if report['schema_revision'] != report['expected_revision']:
        problems.append(f'schema revision {report["schema_revision"]} != expected {report["expected_revision"]}')
    if report['assessment_replay_failures']:
        problems.append(f'{len(report["assessment_replay_failures"])} saved assessments did not replay')
    if args.expect:
        expected = json.loads(Path(args.expect).read_text())
        if comparable(report) != expected:
            problems.append(f'counts differ from the baseline: expected {expected}, found {comparable(report)}')

    for problem in problems:
        print(f'FAIL: {problem}', file=sys.stderr)
    if problems:
        return 1
    print(f'OK: schema at {report["schema_revision"]}, '
          f'{sum(report["records_by_kind"].values())} records across {len(report["workspaces"])} workspaces, '
          f'{report["assessments_checked"]} assessments replayed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
