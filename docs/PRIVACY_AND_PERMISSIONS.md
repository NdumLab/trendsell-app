# Permissions, privacy and retention

What the pilot actually enforces and actually stores, as of the work in
[the action plan](ACTION_PLAN.md) items P04, P05 and P07. Where something is not
implemented, this file says so rather than describing an intention.

## Permission matrix

Defined and enforced in `backend/app/permissions.py`. Routes ask for a **permission**,
never for a role, and the check is always server-side — a client cannot assert that it
holds one. `GET /api/v1/permissions` returns the table and the caller's place in it.

| Permission | owner | analyst | reviewer | viewer |
| --- | :-: | :-: | :-: | :-: |
| `workspace.read` — products, evidence, assessments, quotes, watches | ✓ | ✓ | ✓ | ✓ |
| `workspace.write` — investigations, decisions, quotes, watches | ✓ | ✓ | | |
| `evidence.submit` — record dated manual evidence | ✓ | ✓ | ✓ | |
| `compliance.review` — approve, reject or supersede an import-readiness review | ✓ | | ✓ | |
| `workspace.export` — download the complete workspace export | ✓ | ✓ | | |
| `audit.read` — read the workspace audit log | ✓ | | | |
| `workspace.admin` — workspace settings, membership, operational metrics | ✓ | | | |

The separation that matters: an **analyst** does the research and owns the commercial
assumptions but cannot clear a compliance gate. A gate the researcher can clear is not a
gate. Only `compliance.review` resolves import readiness, and today that is by design not
reachable from the Decision Room dropdown.

Membership management is **not implemented**: every registered user is the `owner` of a new
workspace, and there is no invitation flow. The `analyst`, `reviewer` and `viewer` roles are
enforced but can currently only be set directly in the database. Team access is action plan
item C03.

## What is stored

| Data | Where | Notes |
| --- | --- | --- |
| Account | `users` | Email, display name, password hash (scrypt, self-describing parameters), role. No password is ever stored or logged. |
| Session | `sessions` | SHA-256 of the session token, user id, expiry. The token itself only exists in the cookie. |
| Workspace records | `records` | Products, research jobs, saved assessments, supplier quotes, watch rules — as JSON documents scoped by `workspace_id`. |
| Audit events | `audit_events` | Actor, workspace, action, target record, request id, and small non-secret facts (a verdict, a formula version, an export scope). Never a payload, a body or a credential. |
| Rate windows | `rate_buckets` | A counter and an expiry. No identifying content: the per-account sign-in key is a hash of the address, not the address. |

There are **no third parties**. No collector is connected, nothing is sent to an external
service, and no analytics or error-reporting SDK runs in the browser. The only external
host the deployed page contacts is Google Fonts, via the stylesheet — noted in the nginx
Content-Security-Policy, and removable by self-hosting the font.

Demo examples are stored separately: they live in the visitor's own browser storage, are
labelled `Demo` in the app and in every download, and are never sent to the API.

## Logs

Structured JSON, one object per line (`backend/app/observability.py`). A line carries the
time, level, request id, HTTP method, a route label with record ids collapsed to `:id`, the
status, the duration and — when authenticated — the workspace and user ids.

A log line never carries a request body, a query string, a cookie, a password, a session
token or a record payload. `X-Request-ID` is echoed on the response only when it is a sane
token (8–64 characters of `A-Za-z0-9._-`); anything else is replaced with a generated id.

`GET /api/v1/ops/metrics` returns per-worker counters — request and status counts, server
errors, rate-limit rejections, latency — and no workspace data. It requires
`workspace.admin`.

## Retention

| Record | Behaviour today |
| --- | --- |
| Expired sessions | Deleted by `purge_expired()`, which runs at startup. Only rows whose own expiry has passed. |
| Finished rate windows | Same sweep, same rule. An active window keeps counting. |
| Audit events | Retained indefinitely. No retention limit is set. |
| Workspace records | Retained indefinitely. Saved assessments are immutable by design; a new input creates a new assessment. |
| Backups | `scripts/backup_postgres.sh` prunes on `TRENDSELL_BACKUP_KEEP` days (default 14). Scheduling is **not configured** — see [the runbook](RUNBOOK.md). |

## Deletion

**Not implemented.** There is no self-service account or workspace deletion, and no export-
then-delete flow. Action plan item P03 covers it. Until it exists, a deletion request has to
be handled by an operator against the database, and that has no tested procedure yet — this
is a gap to close before a pilot takes real customer data.

## Account recovery

**Implemented, but not deliverable.** The reset flow, password change, and session listing
and revocation exist and are tested end to end against a local mail sink. What does not
exist is a mail provider, so in production `MAIL_TRANSPORT` is empty and:

* `POST /api/v1/auth/recovery/request` answers exactly as it always does — the response
  cannot reveal whether an account exists — but **mints no token and sends nothing**, and
  logs a warning so an operator can see recovery being asked for while delivery is off.
  Its `delivery_configured: false` field says plainly that no mail is coming.
* A user who loses their password still has no self-service path. An operator has to
  intervene, and that procedure is not yet written down.

What is available today without any provider, to a user who is still signed in:

| Action | Endpoint | Behaviour |
| --- | --- | --- |
| Change password | `POST /api/v1/auth/password` | Requires the current password. Revokes every other session and keeps the one making the change. |
| List sessions | `GET /api/v1/auth/sessions` | Start time, expiry, a truncated client hint, and which one is current. Never returns a token or a token hash. |
| Revoke a session | `DELETE /api/v1/auth/sessions/{handle}` | Ends one session. The handle is derived one-way from the token hash, so it can address a session without authenticating one. |

Reset tokens are stored only as hashes, are single-use, expire in 30 minutes, are bound to
their purpose, and are invalidated when a newer one is issued. Requesting a reset is rate
limited per address and per account. Every rejection — expired, spent, wrong purpose,
never existed — returns the same message.

Registration is closed in production (`ALLOW_REGISTRATION=false`), so accounts are created
deliberately.

**Still not implemented:** verified email ownership. Until a provider exists there is no
way to prove an address belongs to the person who typed it, so recovery would deliver to
an address nobody has confirmed. That is the main reason this is not merely a
configuration switch.

## Before a real pilot

These must be settled with the product owner, not by engineering alone:

1. A privacy notice that matches this file, given to pilot users before they enter data.
2. A deletion procedure, and the retention period for audit events and backups.
3. Recovery point and recovery time objectives, and a restore drill against production
   data (see [the runbook](RUNBOOK.md)).
4. An email provider, which gates account recovery delivery *and* verified email
   ownership. The application side of recovery is implemented and tested; nothing is
   waiting on engineering except the verification flow that a provider makes meaningful.
