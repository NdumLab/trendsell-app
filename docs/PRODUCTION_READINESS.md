# Production readiness

Updated 10 September 2026 on branch `impl/evidence-platform-phase0`, after a fresh local
verification and a follow-up review of the deployment, recovery and privacy paths.

**Summary: the application is ready for staging and an internal evaluation. It is not yet
approved for a real-user production pilot, and it is not ready to be sold on its central
promise.** The remaining pilot blockers are concrete below; external decisions and the
engineering work that follows them are kept separate.

## The product distinction

TrendSell can hold, score and export evidence, and it refuses to issue a GO on evidence it
does not have. That refusal works and is tested. But **no collector is connected**, so every
production observation is typed by a user, self-reported evidence is capped at 60 confidence,
and a GO needs 70. A real actionable GO is therefore unreachable today.

That is the safe result for the current evidence, not a scoring bug. It makes an internal
workflow evaluation useful for evidence capture, economics and compliance-review behavior,
but it prevents marketing or selling an evidence-backed import answer. Closing it requires
source/provider and permitted-use decisions followed by source contracts, collector and
snapshot implementation, durable operations and Data Health telemetry.

## Locally verified

| Area | Evidence |
| --- | --- |
| Tenant isolation | Every id-taking route refuses another workspace; route-by-route tests also assert the other workspace's records remain unchanged |
| Authorisation | Every non-public workspace-data route requires a session and `workspace.read`; the declared role matrix is enforced server-side |
| Account security | Reset/change, sessions, verification-token and one-person-workspace deletion flows have browser screens and end-to-end tests; production mail delivery is separate and absent |
| Credential handling | scrypt at an OWASP-listed parameter set; bearer tokens stored only as hashes, single-use and purpose-bound; account-security transitions share a row lock; low-entropy rate identifiers use a deployment-keyed HMAC |
| Concurrency | Reset redemption, review decisions, research jobs, decisions and watches converge on one record under PostgreSQL contention |
| Data integrity | Saved assessments remain immutable as evidence changes, and workspace/saved exports reconcile with stored records |
| Schema and recovery tooling | Readiness inspects physical schema; migrations adopt the existing installation; a fresh disposable PostgreSQL `0005` dump/restore/replay drill passed |
| Deployment templates | systemd hardening, explicit HTTPS CORS, security headers including `/assets/`, Uvicorn raw access logging disabled, and a reduced nginx access-log format |
| Frontend delivery | Route split leaves about 118 kB gzipped of initial JavaScript; TypeScript, unit, production build and browser checks pass |
| Automated checks | 505 applicable SQLite backend tests passed (16 PostgreSQL-only skips), all 521 passed on PostgreSQL, 141 frontend tests and 46 browser tests passed; dependency and current-tree secret scans passed locally |

## Open before a real-user production pilot

| Gap | What remains | Consequence |
| --- | --- | --- |
| **Independent software review and remote CI** | Gate A has no independent sign-off; this branch is not on the remote and the repository has no observed workflow run | Local results are strong but not independent release evidence |
| **Production recovery** | Agree RPO/RTO and backup location/retention/offsite policy; install the included timer; restore and replay a copy of production; measure duration | Scripts and a hardened opt-in schedule exist, but pilot research is not yet demonstrably recoverable |
| **Privacy and retention** | Give users a matching notice; decide audit, journal, nginx and backup retention; define how deletions after a restored recovery point are reapplied | Current behavior is documented, but production policy and user notice are absent; recovery-token hashes now expire with the credential |
| **Installed log verification** | Install the new templates, restrict nginx/journal access, set retention, and prove a disposable raw path/query/address marker is absent from request/access logs | Repository templates are repaired; a live installation has not been checked |
| **Account intake and recovery model** | Decide the controlled registration window and whether the pilot accepts the lock-preserving operator reset procedure | Registration defaults closed and no invitation flow exists |
| **Mail delivery** | Choose provider/sending identity, implement a real transport, configure SPF/DKIM, test deliverability and monitor failures | No self-service reset or email verification in production; `sink`/`log` are rejected there |
| **Qualified compliance review** | Name qualified reviewers and define independence; membership/invitations are not built, so an owner can still self-review | The workflow cannot be represented as independent professional review |
| **Operational ownership** | Name an on-call owner/destination or explicitly operate the small pilot manually | Structured events and counters do not page anyone |
| **No connected collector** | Complete source feasibility/rights work, then collector/snapshot/durable-job implementation | Every observation is self-reported and a real GO is unreachable |
| **Pilot UX/report scope** | Guided onboarding and the planned professional opportunity report remain unbuilt; constrain pilot promises or implement them | Users have JSON exports and screens, not the full Gate E experience |
| **Data Health telemetry and attachments** | Attempt/freshness telemetry follows collection; evidence files await upload/scanning/retention design | Both remain deliberately unavailable rather than fabricated |

## Known limits

* Operational counters are per worker, so a value is a floor rather than a fleet total.
* The demo GO is synthetic and labelled as such.
* The browser suite raises two rate limits to seed hundreds of records; shipped defaults are
  unchanged and covered directly by backend tests.
* Application request logs intentionally contain workspace and user UUIDs for correlation.
  They omit raw paths, query strings, addresses, bodies and credentials; UUIDs still require
  access control and a retention policy. Nginx error logs are a separate operational record.

## Deployment decision

An internal or staging deployment using disposable/non-customer data is defensible now. A
real-user production pilot is pending the recovery, privacy/log-retention, intake/recovery,
remote-CI and independent-review items above. A public or paid launch additionally requires
a connected, permitted evidence source and a qualified review model.

Before deploying to real users:

1. Push a reviewable branch, run the complete remote workflow, and obtain independent Gate A
   sign-off on the exact release commit.
2. Keep `MAIL_TRANSPORT` empty unless a real provider transport has been implemented and
   released; never use `sink` or `log` in production. Decide and rehearse the operator path.
3. Generate an independent `RATE_KEY_SECRET` and install it with the other production secrets.
4. Agree RPO/RTO and retention, schedule/offsite the backups, and restore/replay a production
   copy into a separate database.
5. Publish the pilot privacy notice and record retention/deletion handling, including backups
   and post-restore deletion replay.
6. Install and validate the service/nginx templates and log retention with disposable markers.
7. Set `METRICS_TOKEN` or deliberately leave metrics off; name who watches the service.
8. Confirm the selected intake model and leave `ALLOW_REGISTRATION=false` outside that window.
9. Deploy to staging, migrate, run the complete smoke workflow and record the rollback target.
