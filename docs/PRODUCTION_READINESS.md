# Production readiness

Written 9 September 2026, on branch `impl/evidence-platform-phase0`. This is the honest
answer to "can this go to production", separated into the parts that are ready, the parts
that are not, and the decisions that are not engineering's to make.

**Summary: the software is ready to run in production as a pilot. The product is not
ready to be sold on its central promise, and no amount of engineering closes that gap.**

## The distinction that matters

TrendSell's promise is an evidence-backed import decision. The application can hold,
score and export evidence, and it refuses to issue a GO on evidence it does not have —
that refusal works, and is tested. But **no collector is connected**, so in production
every observation is typed in by the user, self-reported evidence is capped at 60
confidence, and a GO needs 70. A real, actionable GO is therefore not reachable today.

That is a deliberate design position, not a bug: the alternative is relaxing the gate so
typed numbers can clear it, which is the failure the whole system exists to prevent. But
it means a pilot user can do everything except receive the answer they came for.

Deploying is defensible **as a pilot** — for capturing evidence, running the economics,
and exercising the compliance workflow. It is not defensible as a launch.

## Ready

| Area | Evidence |
| --- | --- |
| Tenant isolation | Every id-taking route refuses another workspace; verified route by route, with the victim's records byte-identical afterwards |
| Authorisation | Every non-public route requires a session; the role matrix is enforced exactly as declared, including `workspace.read` |
| Account security | Reset, change, session listing and revocation, email verification and workspace deletion — all with browser screens and end-to-end tests that read tokens out of the message actually sent |
| Credential handling | scrypt at OWASP parameters, tokens stored only as hashes, single-use and purpose-bound, claimed atomically under a row lock |
| Concurrency | Reset redemption, review decisions, research jobs, decisions and watches all converge on one record under real PostgreSQL contention |
| Data integrity | A saved assessment is immutable — withdrawing every evidence record leaves it byte-identical — and the export reconciles with the database |
| Logging | No credential, body, address, identifier or query string reaches a log line |
| Schema | Readiness inspects the physical schema, not the revision label; migrations adopt the existing installation without data loss |
| Deployment | systemd hardening, explicit CORS allowlist, HTTPS-only production settings, CSP and the rest of the security headers — including on `/assets/`, where nginx's `add_header` replacement had been dropping them |
| Delivery | Route-split bundle: ~118 kB gzipped on first load |
| CI | Backend on SQLite and PostgreSQL, frontend, browser, clean-clone, secret scan, dependency scan |

## Not ready, and why

| Gap | Blocked on | Consequence |
| --- | --- | --- |
| **No connected collector** | Provider access and permitted-use decisions | Every observation is self-reported; a real GO is unreachable |
| **Mail delivery** | Choosing a provider and sending identity | A locked-out user needs an operator; the manual procedure is in `docs/RUNBOOK.md`. Everything except delivery is built and tested |
| **Qualified independent review** | Naming who the reviewers are | One workspace is one person, so an owner can approve their own compliance review. The separation the gates assume does not yet exist in practice |
| **Membership and invitations** | Product | No team can share a workspace |
| **Production backup schedule, RPO/RTO, restore drill** | Product decision on objectives | Scripts and a disposable drill exist; nothing runs on a schedule against production |
| **Alert forwarding** | Naming an on-call destination | Structured logs and counters exist; nothing pages anyone |
| **Data Health telemetry** | Follows the collector | The screen honestly reports "unconfigured" and nothing more |
| **Evidence attachments** | Upload, scanning and retention design | Deferred deliberately |

## Known limits that are not going away

* **Counters are per worker**, so a metric is a floor, not a fleet total. The response says so.
* **The demo GO is synthetic** and labelled as such on screen.
* **The browser suite raises two rate limits** so it can seed several hundred records;
  the shipped defaults are unchanged and covered directly by `test_request_limits.py`.
* **CI has not been observed running remotely.** Every result recorded here is local.

## Before deploying

1. Set `MAIL_TRANSPORT` or accept the operator procedure for lockouts, and tell pilot
   users which it is.
2. Set `METRICS_TOKEN`, or leave the metrics surface off deliberately.
3. Confirm `ALLOW_REGISTRATION=false` unless an open intake is intended.
4. Run the restore drill against a copy of the production database, not only a disposable one.
5. Take an independent review. Gate A has never been signed off, and this document does
   not sign it off either.
