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
| `workspace.admin` — workspace membership and invitations | ✓ | | | |

The separation that matters: an **analyst** does the research and owns the commercial
assumptions but cannot clear a compliance gate. A gate the researcher can clear is not a
gate. Only `compliance.review` resolves import readiness, and it is not reachable from the
Decision Room dropdown. A reviewer also cannot decide a request they submitted themselves,
including an owner who otherwise holds every permission.

The owner can invite an `analyst`, `reviewer` or `viewer`, change a non-owner's role, revoke a
pending invitation, and remove a member. Invitations are email-bound, hashed in storage,
single-use and expire after seven days. Removing a member immediately revokes every session
and suspends the identity so its historical audit attribution remains intact; a later fresh
invitation to the same workspace may reactivate it with a new password.

## What is stored

| Data | Where | Notes |
| --- | --- | --- |
| Account | `users` | Email, display name, password hash (scrypt, self-describing parameters), role, verification time and optional suspension time. No password is ever stored or logged. |
| Session | `sessions` | SHA-256 of the session token, user id, start/expiry times and a truncated browser client hint. The token itself only exists in the cookie. |
| Recovery credential | `recovery_tokens` | SHA-256 of a short-lived reset or email-verification token, its purpose, user id, expiry and use time. The bearer token itself exists outside the database only in a sink/provider message or the operator's one-time handoff. |
| Workspace invitation | `invitations` | Workspace, invited email and role, inviter, timestamps, and SHA-256 of the single-use token. List responses never expose the bearer token. |
| Workspace records | `records` | Products, research jobs, saved assessments, supplier quotes, watch rules — as JSON documents scoped by `workspace_id`. |
| Audit events | `audit_events` | Actor, workspace, action, target record, request id, and small non-secret facts (a verdict, a formula version, an export scope). Never a payload, a body or a credential. |
| Rate windows | `rate_buckets` | A counter and an expiry. Account addresses and network addresses are represented by HMAC-SHA-256 using a deployment-only key, not stored raw or as an enumerable plain hash. These are still pseudonymous identifiers, not anonymous data. |

There is no connected collector, browser analytics or error-reporting SDK in this release.
The interface uses the visitor's system fonts and its production Content Security Policy
permits no third-party browser origin. A production operator may configure an SMTP provider
for account/invitation messages and a private S3 destination for encrypted offsite backups;
those processors, regions and retention terms must be named in the pilot notice before use.

Demo examples are stored separately: they live in the visitor's own browser storage, are
labelled `Demo` in the app and in every download, and are never sent to the API.

## Logs

The application emits structured JSON, one object per line (`backend/app/observability.py`).
A request line carries the time, request id, HTTP method, the router's bounded route template,
status, duration and — when authenticated — the workspace and user ids. Those ids are
pseudonymous identifiers and the journal retention policy must account for them.

An application request line never carries a raw path, request body, query string, network or
email address, cookie, password, session token or record payload. The production systemd
template disables Uvicorn's duplicate raw access log, and nginx uses a reduced access format
for both HTTP redirects and HTTPS, containing only time, method, status, duration and response
size. Exception records include the exception class but omit exception text because that text
can contain user data. Nginx error logs are separate
operational records and can contain connection/request context; restrict access and set their
retention before accepting pilot data. `X-Request-ID` is echoed on the response only when it
is a sane token (8–64 characters of `A-Za-z0-9._-`); anything else is replaced.

`GET /api/v1/ops/metrics` returns per-worker counters — request and status counts, server
errors, rate-limit rejections, latency — and no workspace data. It requires the separate
deployment secret `METRICS_TOKEN`; no workspace role grants service-operator access.

## Retention

| Record | Behaviour today |
| --- | --- |
| Expired sessions | Deleted by `purge_expired()`, which runs at startup. Only rows whose own expiry has passed. |
| Finished rate windows | Same sweep, same rule. An active window keeps counting. |
| Recovery credentials | Same sweep. Used credentials remain only through their original validity window so reuse is distinguishable, then their hashes are deleted. |
| Invitations | Expired invitations are removed by the startup sweep. Accepted/revoked invitations remain until their original expiry; the audit trail retains the action under its own policy. |
| Audit events | Deleted at startup when older than `AUDIT_RETENTION_DAYS` (default 365; production accepts 30–3650). The user-facing notice must state the configured value. |
| Workspace records | Retained indefinitely. Saved assessments are immutable by design; a new input creates a new assessment. |
| Backups | The daily production timer writes a SHA-256 sidecar, keeps local dumps for 14 days and copies both files to an anonymous-inaccessible S3 prefix with AES-256 server-side encryption, versioning and an approximately 31-day lifecycle expiry. The upload identity cannot delete objects. Formal RPO/RTO approval and backup-age alerting remain open; see [the runbook](RUNBOOK.md). |
| Application/proxy logs | Host journal and nginx rotation/retention are deployment policy. They are **not yet recorded for production**. |

## Deletion

Self-service workspace deletion requires the owner password and the exact phrase
`DELETE <workspace name>`. It removes every member identity, invitation, workspace record,
audit event, session, recovery credential and account-scoped rate window from the live
database, then signs the browser out. Active members must be explicitly removed first, so an
owner cannot silently erase their access and shared data. The screen tells the owner to export
first.

Backups are not edited in place. A deleted record remains in a local backup for up to 14 days and
in the current S3 destination for approximately 31 days, until that object expires under the
bucket lifecycle. S3 objects request AES-256 server-side encryption, are versioned and cannot be
deleted by the upload identity. A restore procedure
must preserve deletion requests made after the restored recovery point before the
copy can become the live service. The UI describes this distinction and does not promise that
deletion rewrites historical backups.

## Account recovery

Password reset/change, session listing/revocation, email-verification tokens and all
corresponding browser screens exist and are tested end to end against a local mail sink. A
standard SMTP transport supports STARTTLS or implicit TLS and optional authentication. It is
self-deliverable only after a production operator configures an approved provider and sending
identity:

* With `MAIL_TRANSPORT=smtp`, recovery and verification messages contain browser links whose
  bearer tokens stay in URL fragments, out of proxy access logs. Delivery failures do not
  turn recovery into an account-existence oracle.
* With `MAIL_TRANSPORT` empty, recovery **mints no token and sends nothing**; its
  `delivery_configured: false` response says no mail is coming. A locked-out user follows the
  lock-preserving procedure in [the runbook](RUNBOOK.md#a-locked-out-user-while-no-mail-transport-is-configured).

What is available today without any provider, to a user who is still signed in:

| Action | Endpoint | Behaviour |
| --- | --- | --- |
| Change password | `POST /api/v1/auth/password` | Requires the current password. Revokes every other session and keeps the one making the change. |
| List sessions | `GET /api/v1/auth/sessions` | Start time, expiry, a truncated client hint, and which one is current. Never returns a token or a token hash. |
| Revoke a session | `DELETE /api/v1/auth/sessions/{handle}` | Ends one session. The handle is derived one-way from the token hash, so it can address a session without authenticating one. |

Reset tokens are stored only as hashes, are single-use, expire in 30 minutes, are bound to
their purpose, and are invalidated when a newer one is issued. Requesting a reset is rate
limited per address and per account. Every rejection — expired, spent, wrong purpose,
never existed — returns the same message. A password reset does not by itself mark the email
address verified; only redeeming the purpose-bound email-verification credential does that.

The selected production tier is a free, invitation-only controlled pilot
(`RELEASE_TIER=controlled_pilot`, `ALLOW_REGISTRATION=false`). The existing owner uses
owner-managed, email-bound invitations to add selected pilot members without reopening public
registration. This release refuses to start if controlled-pilot registration is enabled.

Verification and invitations cannot reach a real inbox until SMTP is configured. The operator
reset procedure deliberately does not mark the address
verified, because delivering a reset through another trusted channel proves identity but not
control of that address.

## Before a real pilot

The [incident, breach and data-request runbook](INCIDENT_AND_DATA_REQUEST_RUNBOOK.md) is a
draft procedure only. Its blank owner/contact fields, approval and tabletop must be completed;
the document is not evidence that S11 or P07 has passed.

These must be settled with the product owner, not by engineering alone:

1. A privacy notice that matches this file, given to pilot users before they enter data.
2. The configured audit period and retention periods for logs and backups, plus the
   post-restore handling of deletion requests.
3. Recovery point and recovery time objectives, and a restore drill against production
   data (see [the runbook](RUNBOOK.md)).
4. Either an explicit operator-supported recovery model for the pilot, or an SMTP provider,
   verified sending identity and end-to-end deliverability monitoring.
5. Journal/nginx log retention and access ownership, plus an on-call destination or an
   explicit decision that the pilot is monitored manually.
