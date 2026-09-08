# TrendSell operations runbook

Covers schema management, release, rollback and recovery for the pilot installation.
Written against the work in [the action plan](ACTION_PLAN.md) item P01; the backup and
restore sections are P06 and are marked where they are not yet demonstrated in production.

Nothing here authorises a deployment. It describes how a deployment is performed once
someone with the authority to do so decides to.

## What holds the schema

`backend/migrations/` is the only sanctioned way to change the database. `create_all()`
still runs outside production because it makes tests and local work fast, but it is not a
migration system and production never calls it.

| Command (run from `backend/`) | What it does |
| --- | --- |
| `python -m app.migrate check` | Prints the recorded revision, the revision the code expects, and whether the physical tables match the models. Exit code 0 only when both agree. Changes nothing. |
| `python -m app.migrate upgrade` | Runs outstanding migrations. |
| `python -m app.migrate stamp` | Adopts an existing, already-correct schema as the baseline. |

All three accept `--url` to target a database other than the one in the environment.

`GET /api/ready` answers the same question over HTTP: 200 when the recorded revision
matches the code, 503 with `schema_mismatch` otherwise. `GET /api/health` is liveness only
and does not touch the database, so a schema problem does not look like a dead process.

## Adopting the existing installation (one time)

The running installation's tables were created once by an untracked
`/opt/trendsell/bootstrap_schema.py`, so its `alembic_version` table does not exist yet.
Adopt it rather than re-creating it:

1. Take a backup and confirm it restores (see *Backup and restore* below).
2. `python -m app.migrate check` — expect `current_revision: None`, `matches_models: True`,
   `missing_tables: []`.
3. If `matches_models` is `False`, **stop**. The schema differs from the code; resolve that
   before anything else.
4. `python -m app.migrate stamp` — writes `0001_pilot_baseline`. It refuses an empty
   database, a database that already records a revision, and any schema that does not
   match, so it cannot be used to skip a migration.
5. `python -m app.migrate check` — expect `up_to_date: True`.
6. `curl -fsS https://<domain>/api/ready` — expect 200 and `"status":"ready"`.

The baseline has no downgrade: dropping it would destroy every customer record. Rolling
back a bad schema change means restoring a backup, not downgrading.

## Releasing

1. Build and test the artifact: backend suite (SQLite and PostgreSQL), frontend unit and
   contract tests, TypeScript, production build, browser suite, dependency and secret
   scans. See `.github/workflows/ci.yml` for the exact commands.
2. Back up the production database and verify the dump is readable.
3. `python -m app.migrate check` against production. Record the revision you are moving
   from — that is the rollback target for the application version, not for the schema.
4. Deploy the application. Install `deploy/trendsell.service.template` and
   `deploy/nginx-trendsell.conf.template`; secrets come from `/etc/trendsell/trendsell.env`,
   whose variables are documented in `deploy/trendsell.env.template` and which is never
   committed.
5. `python -m app.migrate upgrade`.
6. `systemctl restart trendsell` and confirm `/api/ready` returns 200.
7. Smoke: sign in to a designated smoke workspace, open a product, save a scenario,
   download the saved assessment, and confirm the export reconciles with `/api/v1/summary`.

Prefer additive migrations with explicit backfills, so the previous application version can
still run against the new schema for the length of a rollback window.

## Rolling back

* **Application only** (schema unchanged): redeploy the previous artifact. Because
  migrations are additive, the older code runs against the newer schema.
* **Schema change went wrong**: restore the pre-release backup into a *new* database, point
  the service at it, and verify with `python -m app.migrate check` and `/api/ready`. Do not
  downgrade in place.

Rollback criteria should be decided before the release, not during it: error rate, failed
readiness, or any evidence of record loss.

## Backup and restore

`scripts/backup_postgres.sh` takes a compressed custom-format dump and prunes old ones;
`scripts/restore_postgres.sh` restores one into a **separate** database and refuses to
write over an existing one. `scripts/verify_restore.py` then checks the restored copy:
table counts, per-workspace record counts, and that saved assessments still replay to the
values they were stored with.

    scripts/backup_postgres.sh                     # writes to $TRENDSELL_BACKUP_DIR
    scripts/restore_postgres.sh <dump> <new-db>    # never touches the live database
    python scripts/verify_restore.py --url <restored-url> --expect <counts.json>

Status of the operational parts (action plan P06):

| Item | State |
| --- | --- |
| Backup and restore scripts | Present in `scripts/`. Drill run 2026-09-08 against a disposable PostgreSQL 16.4 instance: two workspaces, 30 records, 6 saved assessments. The restored copy reported the same schema revision, identical per-workspace counts, all 6 assessments replaying to their stored values, and cross-workspace reads still returning 404. The script refused to restore over an existing database and rejected a non-alphanumeric database name. |
| Restore drill on production data | **Not performed.** Requires production access and a decision by the owner |
| Scheduled backups, retention, offsite copy | **Not configured.** Needs a storage location and retention decision |
| Recovery point and recovery time objectives | **Not agreed.** Record them here once decided |

Do not treat retained customer research as recoverable until the drill has been run against
a copy of production and the result recorded in this file.

## Deliberate gaps

These are known and tracked, not oversights:

* No scheduled collection runs, so no backup covers collector state — there is none yet.
* Email delivery is unconfigured. Account recovery uses a local sink in development and is
  not available in production until a provider is chosen (action plan P03).
* No alerting is wired to an on-call destination (action plan P07). Counters are exposed at
  `GET /api/v1/ops/metrics` for an owner, and every request is logged as JSON with an id;
  nothing yet forwards either to a paging destination.
* Account and workspace deletion is not implemented — see
  [permissions, privacy and retention](PRIVACY_AND_PERMISSIONS.md).

## Diagnosing a failure

Every response carries `X-Request-ID`, every log line for that request carries the same id,
and so does every audit event the request wrote. Given an id from a user or a proxy log:

    journalctl -u trendsell --since '30 min ago' | grep '"request_id":"<id>"'

then, as the workspace owner, `GET /api/v1/audit` and match `request_id` to see exactly
which records that request changed. `GET /api/v1/ops/metrics` gives per-worker request,
status, server-error, rate-limit and latency counters; they reset on restart, so read a
value as a floor rather than a fleet total.
