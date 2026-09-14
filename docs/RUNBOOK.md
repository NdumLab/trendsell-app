# TrendSell operations runbook

Covers schema management, release, rollback and recovery for the pilot installation.
Written against the work in [the action plan](ACTION_PLAN.md) item P01; the backup and
restore sections are P06 and are marked where they are not yet demonstrated in production.
Incident, breach and data-request response is defined separately in the
[draft incident and data-request runbook](INCIDENT_AND_DATA_REQUEST_RUNBOOK.md); its pending
contacts, approvals and tabletop remain release blockers.

Nothing here authorises a deployment. It describes how a deployment is performed once
someone with the authority to do so decides to.

## What holds the schema

`backend/migrations/` is the only sanctioned way to change the database. `create_all()`
still runs outside production because it makes tests and local work fast, but it is not a
migration system and production never calls it.

| Command (run from `backend/`) | What it does |
| --- | --- |
| `python -m app.migrate check` | Prints the recorded revision, the revision the code expects, and whether the physical tables match the models. Exit code 0 only when both agree. Changes nothing. |
| `python -m app.migrate check --against <revision>` | Same, but compares the tables to that revision's schema instead of to the models, and does not treat being behind head as a failure. This is the adoption question, not the readiness question. |
| `python -m app.migrate upgrade` | Runs outstanding migrations. |
| `python -m app.migrate stamp` | Adopts an existing, already-correct schema as the baseline. It does **not** apply later revisions. |

All accept `--url` to target a database other than the one in the environment.

Two different questions are easy to confuse, and confusing them is what made the previous
version of the next section wrong:

* *Does this schema match revision X?* — asked while adopting an installation that is
  deliberately behind. Use `check --against X`.
* *Is this database ready to serve today's code?* — asked before and after a release. Use
  plain `check`, or `/api/ready`.

`GET /api/ready` answers the second over HTTP: 200 only when the recorded revision matches
the code **and** the tables and columns the models declare are physically present. A wrong
revision returns 503 `schema_mismatch`; a right revision over a broken schema returns 503
`schema_incomplete` and names the missing tables and columns. That inspection is cached for
`SCHEMA_RECHECK_SECONDS` (default 30) so probing stays cheap, and a revision change
refreshes it immediately. `GET /api/health` is liveness only and does not touch the
database, so a schema problem does not look like a dead process.

## Adopting the existing installation (one time)

The running installation's tables were created once by an untracked
`/opt/trendsell/bootstrap_schema.py`, so its `alembic_version` table does not exist yet.
Adopt it rather than re-creating it:

The installation predates every revision, so it matches `0001_pilot_baseline` and
correctly **lacks** what `0002` onwards add. Check it against the baseline, not against
today's models — a plain `check` reports `matches_models: False` on a perfectly healthy
pre-migration database.

1. Take a backup and confirm it restores (see *Backup and restore* below).
2. `python -m app.migrate check --against 0001_pilot_baseline` — expect
   `current_revision: None`, `matches_models: True`, `missing_tables: []`.
3. If `matches_models` is `False` **in that command**, stop. The schema differs from the
   baseline; resolve that before anything else.
4. `python -m app.migrate stamp` — writes `0001_pilot_baseline`. It refuses an empty
   database, a database that already records a revision, and any schema that does not
   match, so it cannot be used to skip a migration.
5. `python -m app.migrate check --against 0001_pilot_baseline` — expect
   `current_revision: 0001_pilot_baseline`. `up_to_date` is still `False`, which is
   correct: stamping adopts the baseline and deliberately applies nothing after it.
6. `python -m app.migrate upgrade` — applies `0002` through the current head
   (`0006_workspace_invitations` at the time of writing).
7. `python -m app.migrate check` — now against the models, expect `up_to_date: True` and
   `matches_models: True`.
8. `curl -fsS https://<domain>/api/ready` — expect 200 and `"status":"ready"`.

`backend/tests/redesign/test_migrations.py` runs this sequence against a disposable clone
of the pre-migration schema, so the steps above cannot drift from the tool without the
suite failing.

The baseline has no downgrade: dropping it would destroy every customer record. Rolling
back a bad schema change means restoring a backup, not downgrading.

## Turning on account recovery

The application includes a standards-based SMTP transport. `sink` and `log` remain
development diagnostics and production settings reject both. Turning on SMTP is still an
operational release decision: the provider, sending identity, data-processing terms and
delivery monitoring must be approved before real addresses are sent to it.

1. Choose a provider and sending identity; configure SPF, DKIM and DMARC and verify the
   provider's TLS and authentication requirements.
2. Set `MAIL_TRANSPORT=smtp`, `SMTP_HOST`, `SMTP_PORT`, `MAIL_FROM` and, when required,
   `SMTP_USERNAME`/`SMTP_PASSWORD` in `/etc/trendsell/trendsell.env`. Use STARTTLS (default)
   or implicit TLS, never both. Production refuses plaintext SMTP.
3. Set `PUBLIC_APP_URL` to the canonical HTTPS browser origin used by recovery,
   verification and invitation links, then restart the service.
4. Verify against a disposable account: request a reset, confirm the message arrives,
   redeem it, and confirm every session for that account ended.
5. Verify ownership end to end on the same account: register, confirm the verification
   message arrives, redeem it, and confirm `email_verified` becomes true.
6. Invite a disposable reviewer, accept through the browser link, then revoke that member
   and confirm its session immediately receives 401.
7. Send a deliberately undeliverable message and verify the failure reaches the named
   operator. Check delivery/bounce telemetry before relying on self-service recovery.

`MAIL_TRANSPORT=sink` writes messages to `MAIL_SINK_DIR` instead of sending them. It is
for development and tests: a reset token is a bearer credential, and the sink can write it
to disk in the clear. `MAIL_TRANSPORT=log` records an attempted message without its address
or body; it reports delivery as unavailable and mints no token. Both values are rejected
when `APP_ENV=production`.

## A locked-out user, while no mail transport is configured

With `MAIL_TRANSPORT` empty the reset endpoint answers normally but delivers nothing, so
a person who has lost their password cannot recover unaided. Until a provider is chosen,
this is the procedure — and it is deliberately manual, because handing out a credential
is not something the application should do without a delivery channel it trusts.

**Confirm who is asking before you do any of this.** A reset token is a bearer credential:
whoever holds it controls the account until it is redeemed or expires. Verify the request
through a channel you already trust, not through the address in the request.

1. Confirm the account exists and note its id:

   ```bash
   sudo -u trendsell /opt/trendsell/venv/bin/python - <<'EOF'
   from app.db import Database, User
   from app.settings import Settings
   with Database(Settings.from_env().database_url).session() as db:
       user = db.query(User).filter_by(email='person@example.com').one_or_none()
       print(user and (user.id, user.workspace_id, user.email_verified_at))
   EOF
   ```

2. Issue a single-use token, valid 30 minutes, and read it once:

   ```bash
   sudo -u trendsell /opt/trendsell/venv/bin/python - <<'EOF'
   import secrets
   from datetime import datetime, timedelta, timezone
   from sqlalchemy import select
   from app.db import Database, RecoveryToken, User, now
   from app.security import token_hash
   from app.settings import Settings
   token = secrets.token_urlsafe(32)
   with Database(Settings.from_env().database_url).session() as db:
       # Take the same account lock as issuance, redemption and password change in the API.
       # Without it, an operator-issued token can race a password change and survive it.
       user = db.execute(
           select(User).where(User.email == 'person@example.com').with_for_update()
       ).scalar_one()
       # Spend any outstanding token first, exactly as the API does.
       db.query(RecoveryToken).filter_by(user_id=user.id, purpose='password_reset',
                                         used_at=None).update({'used_at': now()})
       db.add(RecoveryToken(
           token_hash=token_hash(token), user_id=user.id, purpose='password_reset',
           expires_at=(datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(),
           created_at=now()))
       db.commit()
   print(token)   # the only time this value exists in the clear
   EOF
   ```

3. Give the token to the person over the trusted channel. They enter it under **Forgot
   your password?** in the sign-in dialog. Redeeming it ends every session on the
   account, which is the point. It does **not** mark the account's email verified: control
   of a different trusted channel is not proof of control of that address.

4. Record what you did: who asked, how you verified them, when, and that the token was
   issued. The application audits the redemption (`auth.password_reset`) but cannot audit
   your decision to trust the request.

Never read, copy or set `password_hash` directly, and never send a reset token to the
address in the request before you have verified the requester by another route. Do not use
this procedure to mark an email address verified: verification requires delivering the
purpose-bound verification credential to that address, which waits on a real provider.

## Releasing

1. Freeze one clean commit and let its remote workflow build the release artifact: backend
   suite (SQLite and PostgreSQL), frontend unit and contract tests, TypeScript, production
   build, browser suite, dependency/vulnerability and locked-license scans, a redacting
   tracked/history secret scan and a clean runtime import. The clean-clone job runs
   `scripts/build_release_artifact.sh` twice, requires
   byte-identical archives, scans the unpacked result and publishes the archive plus SHA-256.
   Refuse an artifact whose embedded `RELEASE.json` commit is not the approved release commit.
   A local candidate can be exercised with `scripts/build_release_artifact.sh`, but local output
   is not a substitute for the remote workflow attached to that commit.
2. Confirm pilot users received the current privacy notice and record retention for the
   journal, nginx logs, audit events and backups. Set `AUDIT_RETENTION_DAYS` to the stated
   period; recovery-credential and invitation hashes are swept after their expiry.
3. Back up the production database and verify the dump restores and replays against a
   separate database.
4. `python -m app.migrate check` against production. Record the revision you are moving
   from — that is the rollback target for the application version, not for the schema.
5. Deploy the application. Install `deploy/trendsell.service.template` and
   `deploy/nginx-trendsell.conf.template`; secrets come from `/etc/trendsell/trendsell.env`,
   whose variables are documented in `deploy/trendsell.env.template` and which is never
   committed. Generate `RATE_KEY_SECRET` independently from every database, metrics or
   provider credential; production refuses values shorter than 32 characters.
6. `python -m app.migrate upgrade`.
7. `systemctl restart trendsell` and confirm `/api/ready` returns 200.
8. Verify the installed Uvicorn command includes `--no-access-log` and nginx uses
   `trendsell_safe`; make a request containing a disposable marker and confirm the marker,
   raw path, query and client address do not enter the application or access logs.
9. Smoke: sign in to a designated smoke workspace, open a product, save a scenario,
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

`scripts/backup_postgres.sh` takes a compressed custom-format dump, publishes it atomically
with a SHA-256 sidecar and prunes old local copies;
`scripts/restore_postgres.sh` restores one into a **separate** database and refuses to
write over an existing one or proceed without a matching checksum. When
`TRENDSELL_BACKUP_S3_URI` is configured, the backup job copies the dump and checksum to that
private prefix with `AES256` or `aws:kms` server-side encryption; either upload failing makes
the job fail while retaining the verified local copy. `scripts/verify_restore.py` then checks
the restored copy:
table counts, per-workspace record counts, and that saved assessments still replay to the
values they were stored with. A failed/interrupted dump stays under a hidden `.partial`
name and is removed; only a dump that `pg_restore --list` can read is atomically published.

    scripts/backup_postgres.sh                     # writes to $TRENDSELL_BACKUP_DIR
    scripts/restore_postgres.sh <dump> <new-db>    # never touches the live database
    python scripts/verify_restore.py --url <restored-url> --expect <counts.json>

The repository includes an opt-in daily systemd one-shot and timer. Do not enable them
until the backup location, retention, access owner and acceptable recovery point are
approved. Once they are, install and validate them:

    install -d -o trendsell -g trendsell -m 0700 /var/backups/trendsell
    install -o root -g root -m 0644 deploy/trendsell-backup.service.template /etc/systemd/system/trendsell-backup.service
    install -o root -g root -m 0644 deploy/trendsell-backup.timer.template /etc/systemd/system/trendsell-backup.timer
    systemd-analyze verify /etc/systemd/system/trendsell-backup.service /etc/systemd/system/trendsell-backup.timer
    systemctl daemon-reload
    systemctl enable --now trendsell-backup.timer
    systemctl start trendsell-backup.service
    systemctl status trendsell-backup.service trendsell-backup.timer

Keep AWS credentials out of `/etc/trendsell/trendsell.env`, because that file is also loaded
by the long-running web service. The backup unit optionally loads root-only
`/etc/trendsell/backup-s3.env`; put `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`,
`AWS_DEFAULT_REGION`, `TRENDSELL_BACKUP_S3_URI` and `TRENDSELL_BACKUP_S3_SSE` there and set
its mode to `0600`. The system manager reads the file and passes it only to the one-shot.

Confirm the first dump and checksum exist at mode `0600`, `sha256sum --check` passes,
`pg_restore --list` passes, and both objects reached the approved private off-host prefix.
Confirm bucket TLS/encryption enforcement, restricted IAM and lifecycle expiry separately;
the CLI flag alone does not prove those controls. Record the observed completion time and
test a separate restore before treating the schedule as recovery capability.

Status of the operational parts (action plan P06):

| Item | State |
| --- | --- |
| Backup and restore scripts | Present in `scripts/`. Drill run 2026-09-08 against a disposable PostgreSQL 16.4 instance: two workspaces, 30 records, 6 saved assessments. The restored copy reported the same schema revision, identical per-workspace counts, all 6 assessments replaying to their stored values, and cross-workspace reads still returning 404. The script refused to restore over an existing database and rejected a non-alphanumeric database name. |
| Restore drill on production data | **Passed 2026-09-14.** The freshly uploaded S3 dump and checksum were downloaded, SHA-256 and `pg_restore --list` passed, and the dump restored into a separate database. Schema revision `0006_workspace_invitations`, per-workspace counts and record kinds matched the live baseline; the current pilot database contained one workspace and no records/assessments. The disposable database was removed after verification. This proves the path, not representative-scale recovery time. |
| Scheduled backups, retention, offsite copy | **Active.** `trendsell-backup.timer` runs daily at 02:15 UTC with up to 30 minutes randomized delay. Local dumps retain 14 days. S3 destination is `s3://yerika-siteforge-prod-backups-739951718503-us-east-1/siteforge/trendsell/postgresql/`; objects use AES-256 server-side encryption, are versioned and receive the bucket's approximately 31-day lifecycle expiry. The scoped IAM credential can put/list/get but cannot delete objects, the object is anonymous-inaccessible (HTTP 403), and credentials are loaded only by the one-shot. Bucket-level Public Access Block and explicit TLS-policy reads remain unavailable to this scoped IAM identity. |
| Recovery point and recovery time objectives | **Not formally agreed.** The installed schedule provides one recovery point per day when healthy (about a 24-hour interval plus randomized delay); the 2026-09-14 empty-pilot recovery path completed in seconds, which is evidence rather than an RTO commitment. |

Do not extrapolate the empty-pilot drill to a populated or representative-scale database;
repeat and time it once the pilot contains realistic data.

## Optional Amazon Creators API connection

The server contains a GetItems adapter; it is off by default. **Do not enable it under the
standard Associates terms alone.** Amazon's published guidance describes Creators API apps
as applications that refer sales to Amazon and gives cached Offers and BrowseNodeInfo a
one-hour TTL and other product content a one-day TTL. TrendSell is an internal research tool
that preserves historical evidence, so its use and durable snapshots require explicit terms
from Amazon covering both purposes. A locally written policy or a value in
`AMAZON_CREATORS_USAGE_RIGHTS` is not provider approval.

Only after that approval exists, the operator also needs an Amazon Associates account with
final acceptance and Creators API access, a credential issued to the primary account owner,
and a valid US partner tag. Record a reference to the specific provider approval and the
approved snapshot purpose/retention wording in `AMAZON_CREATORS_USAGE_RIGHTS`.

Install the credential directly into `/etc/trendsell/trendsell.env` using the established
root-owned secret process—never in chat, Git, `VITE_*`, browser storage, a support ticket, or
a command whose output is captured. Configure:

```text
AMAZON_CREATORS_ENABLED=true
AMAZON_CREATORS_CREDENTIAL_ID=...
AMAZON_CREATORS_CREDENTIAL_SECRET=...
AMAZON_CREATORS_CREDENTIAL_VERSION=3.1
AMAZON_CREATORS_PARTNER_TAG=...
AMAZON_CREATORS_MARKETPLACE=www.amazon.com
AMAZON_CREATORS_USAGE_RIGHTS=reviewed purpose and retention policy
```

Credential version 3.1 uses the North America Login with Amazon token endpoint; use 3.2
or 3.3 only for credentials issued with those versions. A configured source remains
`configured` until a workspace requests a product check. Success changes that workspace's
status to `connected`; authorization, throttling, response, or network failures change it
to `degraded` with a safe retry reason. A failure does not add a zero observation.

The pilot accepts only `www.amazon.com`; supporting another locale also requires widening
the product-input and evidence-market contracts so its records are not mislabeled as US.
GetItems may supply current identity, images, featured offer and sales-rank fields. It does
not establish sales history, review velocity, seller count, revenue, ad spend, ROAS, or
causal attribution; the adapter does not infer them. A rank change requires at least two
separate dated observations. Validate account terms before retaining real snapshots, run a
single supported-ASIN check, inspect Data Health and the evidence drawer, and then run the
workspace export/restore check. Enabling the source is a production configuration change
and follows the normal preflight, backup and rollback process.

## Deliberate gaps

These are known and tracked, not oversights:

* No scheduled collection runs. User-requested Amazon catalog snapshots and source status are
  workspace records and therefore enter the normal database backup, but a watch does not trigger
  refresh or notification.
* The SMTP transport ships, but delivery remains unconfigured (`MAIL_TRANSPORT=`) until a
  provider and sending identity are approved. With no transport the recovery endpoint mints
  no token and sends nothing; `delivery_configured: false` says no mail is coming. **A
  locked-out user therefore has no self-service path and needs an operator**, using the
  procedure above. Existing accounts remain unverified rather than grandfathered (P03).
* Metrics are behind `METRICS_TOKEN` and are per worker, so a value is a floor rather
  than a fleet total. Owning a workspace does not grant access (review finding R07).
* No alerting is wired to an on-call destination (action plan P07). Counters are exposed at
  `GET /api/v1/ops/metrics` only to the separate operator token, and every request is logged
  as JSON with an id; nothing yet forwards either to a paging destination.
* Owner-managed membership is implemented, but reviewer qualifications and independence are
  operational facts the software cannot establish. Workspace deletion requires active members
  to be removed first and then removes all live identities and rows; backups retain older
  copies until they age out, so retention and post-restore deletion handling must be agreed.
  See
  [permissions, privacy and retention](PRIVACY_AND_PERMISSIONS.md).

## Diagnosing a failure

Every response carries `X-Request-ID`, every log line for that request carries the same id,
and so does every audit event the request wrote. Given an id from a user or a proxy log:

    journalctl -u trendsell --since '30 min ago' | grep '"request_id":"<id>"'

then, as the workspace owner, `GET /api/v1/audit` and match `request_id` to see exactly
which records that request changed. `GET /api/v1/ops/metrics` gives per-worker request,
status, server-error, rate-limit and latency counters; they reset on restart, so read a
value as a floor rather than a fleet total.
