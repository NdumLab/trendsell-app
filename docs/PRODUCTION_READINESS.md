# Definitive production readiness checklist

Updated 16 September 2026 on branch `impl/evidence-platform-phase0`.

This is TrendSell's release contract for the current architecture: a React static frontend,
FastAPI service, PostgreSQL database, nginx reverse proxy, systemd-managed application and backup
jobs, SMTP account mail and, when enabled, external evidence providers. It is intentionally stricter
than a list of work completed in the repository.

## Decision now

**Selected scope:** free, invitation-only controlled pilot. Production registration remains closed;
an existing owner admits only the approved cohort through email-bound invitations. No billing,
payment, public sign-up or general-availability claim is in scope. This scope decision does not turn
any blocked readiness gate into a pass.

The current [decision sheet](releases/2026-09-16-decision-sheet.md) contains recommended values,
cost/resource impact and the exact named approvals still needed. They remain proposals. The
[blocker register](releases/2026-09-16-blocker-register.md) accounts for all 60 blocked gate IDs and
separates implementation capability from environment evidence and human decisions.

| Release tier | Decision | Reason |
| --- | --- | --- |
| Local/internal evaluation with disposable data | **GO** | The locally verified software checks below pass; no customer data or product promise is involved |
| Controlled real-user production pilot | **NO-GO** | The exact release is not independently verified; production recovery, policy, installed logging, mail/recovery and operational ownership are not proven |
| Public or paid production | **NO-GO** | The pilot gates are open, no permitted collector can produce a real actionable GO, the qualified-review model is unsettled, and public/commercial gates are unproven |

## How this checklist is used

The status vocabulary is deliberately go/no-go:

* **PASS** — the acceptance condition is demonstrated for the exact release candidate and, where
  applicable, the target production environment. Evidence is dated and linked in the release record.
* **BLOCKED** — failed, partial, untested, unknown, awaiting a decision, or supported only by evidence
  from a different commit/environment. All of these mean the gate has not passed.
* **N/A** — the capability is explicitly excluded from the release, inaccessible to users, absent
  from sales/marketing/support promises, and the exclusion is recorded. Merely unfinished is not N/A.

A real-user release is authorised only when:

1. a release record identifies one immutable commit and artifact;
2. every gate required for that tier is **PASS**, or is validly **N/A** under the rule above;
3. no unresolved critical/high security, tenant-isolation, data-loss or materially misleading-product
   defect exists;
4. every accepted lower-severity risk has an owner, mitigation and review/expiry date;
5. the named Product, Engineering/Platform, Security/Privacy and Operations approvers sign the same
   release record; one person may hold several roles for a small pilot, but the independent reviewer
   cannot approve their own code review; and
6. post-deployment verification passes before users are admitted.

A waiver never turns a required release gate into **PASS**. The release must either satisfy the gate
or reduce its scope until the gate is validly **N/A**. Approvers may accept a lower-severity residual
defect only when the relevant gate still passes and the risk has an owner, mitigation and expiry.
No acceptance may permit a known cross-tenant disclosure, credential exposure, silent data
corruption/loss, unlawful data use, or a product claim the release cannot perform.

`Pilot` below means a controlled real-user pilot. `Public` includes any open-registration, advertised,
paid or otherwise generally available release. Public inherits every Pilot gate.

## 1. Release identity and independent evidence

| ID | Acceptance condition | Required evidence | Pilot | Public | Current |
| --- | --- | --- | --- | --- | --- |
| R01 | One clean, reviewable commit is the release candidate; all application, migration, contract, lock and deployment files it needs are tracked | Commit SHA, clean `git status`, reviewed diff and release notes | Required | Required | **PASS** — candidate `ddde69af2a48ec017f87b57274c0fd150322755d` is clean, pushed and identified in its [closure record](releases/2026-09-14-ddde69a-blocker-closure.md) |
| R02 | A versioned, reproducible artifact is built from R01 without relying on workstation state | Artifact identifier and SHA-256; clean-clone build log | Required | Required | **PASS** — exact-candidate artifact `10362387379` was built twice byte-identically in a clean clone; its published checksum and embedded manifest passed |
| R03 | Remote CI passes on R01: SQLite and PostgreSQL backend suites, frontend unit/type/build, browser suite, clean-clone build, dependency scan and secret/history scan | Links to all successful workflow jobs for the SHA | Required | Required | **PASS** — all seven jobs in [run 34880189151](https://github.com/NdumLab/trendsell-app/actions/runs/34880189151) passed for the exact candidate SHA |
| R04 | An independent reviewer approves the exact diff and checks tenancy, authorization, credentials, migrations, recovery, concurrency, lineage and truthful product behavior | Named, dated review with findings and dispositions | Required | Required | **BLOCKED** |
| R05 | Every known defect has severity, user impact, owner and disposition; none violates the non-waivable conditions above | Release issue/risk register | Required | Required | **BLOCKED** |
| R06 | The production topology, dependencies and configuration variables are inventoried; repository templates match the intended installation | Reviewed architecture/configuration record with secrets redacted | Required | Required | **BLOCKED** — installed fingerprints, listeners and redacted settings were observed, but database/host privilege disposition and named ownership remain open |

## 2. Functional correctness and data integrity

| ID | Acceptance condition | Required evidence | Pilot | Public | Current |
| --- | --- | --- | --- | --- | --- |
| F01 | Registration/intake, sign-in/out, sessions, recovery, verification, invitations, member suspension and workspace deletion behave as the release policy states | PostgreSQL integration and browser results plus target-environment smoke | Required | Required | **BLOCKED** — [production smoke](operations/2026-09-14-production-smoke.md) passed sign-in, role denial, SMTP-backed invitation, suspension/reactivation and recovery/session revocation; mailbox-driven token use, email verification and workspace deletion remain unproven |
| F02 | Every workspace-data read, write, export and audit route enforces tenant and role boundaries; denial leaves the other tenant's state unchanged | Route inventory and shared-database isolation tests on R01 | Required | Required | **PASS** — exact `ddde69a` candidate passes the route inventory and shared-database isolation regressions locally and in remote CI |
| F03 | Retried and concurrent account, job, review, decision and watch operations converge without duplicate effects, lost updates or unexpected 500s | PostgreSQL contention/idempotency results on R01 | Required | Required | **PASS** — exact `ddde69a` candidate passes the PostgreSQL contention and idempotency cases locally and in remote CI |
| F04 | Saved decisions, evidence snapshots, formula/threshold versions and exports remain immutable, internally consistent and replayable | Contract, replay and historical-lineage tests on R01 | Required | Required | **PASS** — exact `ddde69a` candidate passes contract, replay and historical-lineage tests locally and in remote CI |
| F05 | Fresh databases and a sanitized representative pre-release schema both migrate to head; physical-schema readiness succeeds afterward | Migration logs, row/backfill counts and `/api/ready` result | Required | Required | **PASS** — the exact `ddde69a` artifact migrated a fresh PostgreSQL 16.4 database, populated and preserved 900 representative synthetic records, completed a no-op candidate upgrade and became ready after two production-mode two-worker process starts; see the [closure record](releases/2026-09-14-ddde69a-blocker-closure.md#f05-migration-restart-and-readiness--pass-for-ddde69a) |
| F06 | Invalid, oversized, unauthorized, timed-out and unavailable-dependency cases fail safely without private-data leakage or false success | Negative API/browser tests and staged fault exercise | Required | Required | **PASS** — exact-candidate automated cases pass and a production-mode PostgreSQL/SMTP fault exercise returned safe 422/401/413/202 outcomes through a real 15-second SMTP timeout without identity, password or token markers in captured logs; see the [closure record](releases/2026-09-14-ddde69a-blocker-closure.md#f06-staged-negative-and-dependency-fault-exercise--pass-for-ddde69a) |
| F07 | Supported browsers/devices complete the critical flow with no release-blocking defect | Named support matrix and results from current browser versions | Required | Required | **BLOCKED** |
| F08 | Critical journeys are usable by keyboard and assistive technology; public release meets a declared accessibility target | Automated scan, keyboard/screen-reader evidence; declared conformance target for Public | Required | Required | **BLOCKED** |

## 3. Security, privacy and access control

| ID | Acceptance condition | Required evidence | Pilot | Public | Current |
| --- | --- | --- | --- | --- | --- |
| S01 | Production uses unique high-entropy secrets and least-privilege service identities; no default/sample value remains; storage, access, rotation and emergency revocation owners are documented | Redacted configuration audit and secret/access register | Required | Required | **BLOCKED** |
| S02 | Only nginx is internet-facing; API and PostgreSQL are private; firewall/security-group and database privileges allow only required traffic/actions | Port scan/configuration evidence and privilege review | Required | Required | **BLOCKED** |
| S03 | DNS and HTTPS are correct; modern TLS, HSTS and security headers are present on HTML, API and assets; certificate renewal is installed, tested and monitored | External TLS/header results and renewal dry run/alert | Required | Required | **BLOCKED** — endpoint TLS/headers and renewal dry run pass; no expiry alert has reached a named owner |
| S04 | Host, OS, nginx, PostgreSQL, Python and Node/runtime patch ownership and cadence are defined; unsupported components are absent | Version inventory, update evidence and next review date | Required | Required | **BLOCKED** |
| S05 | Session cookies, password hashing, token hashing/expiry/single use, session revocation and anti-enumeration controls pass; production proxy trust cannot spoof rate identities | Automated results plus installed proxy test | Required | Required | **BLOCKED** — software controls pass locally; installed path is unproven |
| S06 | Rate limits and request-size limits work through the real proxy and tolerate expected legitimate traffic while bounding login, registration, invitation and write abuse | Target-environment abuse tests and chosen thresholds | Required | Required | **BLOCKED** |
| S07 | Application, nginx and journal logs omit credentials, tokens, addresses, raw paths/queries and record payloads; UUID-bearing logs have restricted access and approved retention | Disposable-marker test, file/journal permissions and retention configuration | Required | Required | **BLOCKED** |
| S08 | Runtime and development dependencies contain no unaccepted known high/critical vulnerability; reachable history and release artifacts contain no credential; licenses are compatible | CI scan links, artifact/history scan and dependency/license inventory | Required | Required | **PASS** — local and exact-`ddde69a` remote vulnerability, redacting current/history/artifact, and 181-package license-policy checks pass; exact inventory and dispositions are in [DEPENDENCY_LICENSES.md](DEPENDENCY_LICENSES.md) |
| S09 | A security review exercises the internet-facing authenticated application, including tenant access, authorization, CSRF/origin behavior, injection, SSRF where applicable, abuse and sensitive-data leakage | Independent threat-model review and vulnerability/penetration report with remediation | Required | Required | **BLOCKED** |
| S10 | Production and support access is named, least-privilege, auditable, protected by strong authentication, reviewed periodically and removed promptly on role change | Access list, access logs and review/offboarding procedure | Required | Required | **BLOCKED** |
| S11 | An incident and personal-data-breach process identifies detection, containment, credential rotation, evidence preservation, notification decision-makers and contact paths | Approved incident runbook and completed tabletop | Required | Required | **BLOCKED** — a [draft procedure](INCIDENT_AND_DATA_REQUEST_RUNBOOK.md) now exists; named contacts, approval and independent tabletop evidence remain absent |

## 4. Production configuration and infrastructure

| ID | Acceptance condition | Required evidence | Pilot | Public | Current |
| --- | --- | --- | --- | --- | --- |
| I01 | `APP_ENV`, PostgreSQL URL, HTTPS CORS/public URL, registration policy, limits, schema cache, retention, metrics, mail and backup settings are deliberately chosen and validated; filled secrets are not in source control | Redacted environment review and successful production settings check | Required | Required | **BLOCKED** |
| I02 | PostgreSQL version/support, encryption in transit/at rest, least-privilege role, connection ceiling/pooling, disk capacity and maintenance/upgrade ownership are established | Provider/server configuration, privilege and capacity evidence | Required | Required | **BLOCKED** |
| I03 | systemd and nginx templates are installed with intended ownership/modes and hardening; service restarts cleanly and survives host reboot | Installed-unit/config diff, validation and reboot/recovery test | Required | Required | **BLOCKED** |
| I04 | Staging mirrors production topology and feature configuration except credentials, scale and synthetic/sanitized data; no raw production customer data enters unrestricted test systems | Environment comparison and data-handling attestation | Required | Required | **BLOCKED** |
| I05 | Expected normal and peak users/requests/jobs/data volume are stated; a representative load test stays within agreed latency/error/resource limits with documented headroom | Filled capacity targets, load report and bottleneck/cost analysis | Required | Required | **BLOCKED** — targets are not agreed |
| I06 | External services have approved accounts, permissions, regions, terms, quotas/budgets, timeout/retry behavior, credential-expiry handling and operational contacts | Dependency register and staged failure results | Required where used | Required where used | **BLOCKED** for SMTP; evidence providers are not connected |
| I07 | Deployment is repeatable, limits privileged manual changes, records configuration drift and supports a maintenance window or safe compatible rollout | Deployment log/procedure and drift comparison | Required | Required | **BLOCKED** |

## 5. Backup, recovery and release rollback

| ID | Acceptance condition | Required evidence | Pilot | Public | Current |
| --- | --- | --- | --- | --- | --- |
| D01 | The owner approves numeric RPO and RTO, backup scope, local/offsite retention and the maximum acceptable data-loss window | Values in the release record and policy approval | Required | Required | **BLOCKED** — not agreed |
| D02 | Scheduled backups run under a restricted identity, publish checksums, copy to a private encrypted offsite destination, expire under policy and alert on absence/failure | Timer/job status, object/IAM/TLS/encryption/lifecycle evidence and backup-age alert | Required | Required | **BLOCKED** — daily local/S3 copies, checksum, AES-256, versioning, lifecycle, anonymous denial, non-delete IAM and a six-hour local/offsite age/integrity check were proven 2026-09-14; a named alert destination, bucket-level TLS/Public Access Block evidence and TrendSell-only IAM scope remain open |
| D03 | A recent production-data copy—or, before first launch, a representative production-scale synthetic/sanitized database—restores into an isolated database within RTO; checksum, schema, record/tenant counts and saved-assessment replay pass; access to restored data is controlled | Dated drill record, timings and verification output | Required | Required | **BLOCKED** — the 2026-09-14 S3-to-isolated-database production drill passed, but production held only one empty workspace and does not prove representative-scale RTO |
| D04 | Post-recovery-point deletions and other legally/operationally required changes can be identified and reapplied after restore | Tested deletion-replay procedure and audit evidence | Required | Required | **BLOCKED** |
| D05 | The previous application artifact runs against the migrated schema for the rollback window, or a tested new-database restore/switch procedure exists; no destructive in-place downgrade is assumed | Staging rollback drill and recorded rollback artifact/database target | Required | Required | **BLOCKED** |
| D06 | Migration duration, locking, disk requirement, backfill counts and interruption behavior are measured on representative scale; abort/rollback criteria are stated | Staging migration rehearsal and thresholds | Required | Required | **BLOCKED** |

## 6. Observability and operations

| ID | Acceptance condition | Required evidence | Pilot | Public | Current |
| --- | --- | --- | --- | --- | --- |
| O01 | Availability, latency and error objectives plus rollback/stop thresholds are numeric and approved; Pilot may use explicitly limited support hours, while Public requires continuous ownership appropriate to its promise | SLO/threshold fields in release record | Required | Required | **BLOCKED** |
| O02 | A named operator can see fleet-level health/readiness, request/error/latency/rate-limit signals and PostgreSQL/service/host saturation; data is retained for an approved period | Dashboard/queries, access controls and retention | Required | Required | **BLOCKED** — current counters are per-worker floors |
| O03 | Alerts cover readiness failure, error/latency threshold, service restart loop, database exhaustion, low disk, missed/failed/old backup, TLS expiry, SMTP when enabled and every enabled collector/queue/freshness/cost limit | Alert inventory with thresholds and destinations | Required | Required | **BLOCKED** |
| O04 | Each critical alert is injected end to end and reaches the named operator; acknowledgement, escalation and recovery are timed | Dated alert drill/page evidence | Required | Required | **BLOCKED** |
| O05 | Runbooks cover deploy, rollback, restore, user lockout, suspected credential/data exposure, provider outage and database/service saturation; an operator other than the author can execute them | Runbook review and tabletop/drill notes | Required | Required | **BLOCKED** — a release/recovery runbook exists but live execution is incomplete |
| O06 | User support has an owner, contact path, operating hours, response target and escalation route; users can report an incorrect decision or privacy/security concern | Published support process and test request | Required | Required | **BLOCKED** |
| O07 | Operational and vendor costs have limits/alerts; the release cannot silently create unbounded mail, provider, storage or compute spend | Approved budget, quotas and alert evidence | Required | Required | **BLOCKED** |

## 7. Account mail and controlled intake

| ID | Acceptance condition | Required evidence | Pilot | Public | Current |
| --- | --- | --- | --- | --- | --- |
| A01 | Initial ownership is verified, public registration matches policy, members enter through owner-managed invitations, and removal immediately terminates access | Target-environment intake/revocation smoke and owner record | Required | Required | **BLOCKED** — registration is closed and the [production invitation/revocation smoke](operations/2026-09-14-production-smoke.md) passed; the real pilot owner/cohort and mailbox ownership remain unapproved |
| A02 | Public releases use an approved SMTP provider/sending identity with TLS, SPF, DKIM and DMARC; reset, verification and invitation links work end to end; bounces/failures are monitored | DNS/provider results, disposable-account flows and failure alert | Required unless A03 passes | Required | **BLOCKED** — Resend SMTP, TLS, sending-domain DNS and provider-test-recipient acceptance pass; the send-only API key prevented mailbox-body retrieval, and bounce/failure monitoring has no recipient |
| A03 | If Pilot omits SMTP, registration remains closed and a named operator uses a tested trusted-channel recovery procedure within a stated support window; every pilot user is told self-service recovery is unavailable | Signed pilot constraint, operator/recovery drill and participant notice | Required if A02 is N/A | Not permitted | **BLOCKED** |
| A04 | Account/workspace deletion and export are tested in production-like conditions; active data disappears as documented and backup expiry/replay follows the approved policy | Test record, audit events and policy link | Required | Required | **BLOCKED** — production owner export and disposable record cleanup passed; self-service workspace deletion and post-restore deletion replay remain unproven |

## 8. Data rights, privacy and legal policy

| ID | Acceptance condition | Required evidence | Pilot | Public | Current |
| --- | --- | --- | --- | --- | --- |
| P01 | A data inventory identifies customer data, pseudonymous identifiers, evidence/source data, logs, mail/provider data, backups, location, purpose, access and retention | Approved data map matching the deployed system | Required | Required | **BLOCKED** — repository documentation exists; production choices are unapproved |
| P02 | Users receive a privacy notice matching actual collection, subprocessors, purposes, retention, export/deletion and contact process before entering data | Published/versioned notice and acceptance/delivery record | Required | Required | **BLOCKED** |
| P03 | Audit, application, nginx/journal, mail/provider, database and backup retention rules are explicit (numeric or retain-until-deletion where justified), configured and tested; deletion behavior is truthful | Retention schedule, configs and expiry evidence | Required | Required | **BLOCKED** |
| P04 | Each evidence source has a current permitted-use decision covering access method, fields, storage, display/derived use, attribution, deletion and commercial use; credentials or customer-authorized connections are obtained lawfully | Source-rights register, terms/contracts and reviewer approval | Required where used | Required | **BLOCKED** — no production source is approved/connected |
| P05 | Terms/acceptable-use language, decision limitations, user responsibilities, prohibited use and complaint/appeal route match the product; qualified counsel or accountable policy owner reviews jurisdiction-specific obligations | Versioned terms/policy approval | Required | Required | **BLOCKED** |
| P06 | Subprocessors/providers have approved security/privacy terms, data locations and contacts; any required data-processing agreement is in place | Vendor register and executed approvals | Required where used | Required | **BLOCKED** |
| P07 | A lawful incident-notification and data-subject/request handling process has accountable owners and response records | Procedure/tabletop and request log template | Required | Required | **BLOCKED** — the [draft procedure and empty log template](INCIDENT_AND_DATA_REQUEST_RUNBOOK.md#data-access-export-and-deletion-requests) exist; accountable owners, approval and tabletop/response evidence remain absent |

## 9. TrendSell product truth and domain safety

| ID | Acceptance condition | Required evidence | Pilot | Public | Current |
| --- | --- | --- | --- | --- | --- |
| T01 | Every screen, export, report, demo, landing page and sales/support statement distinguishes self-reported, observed, derived, reviewed, stale, unavailable and synthetic information | Claim inventory and cross-screen/export review | Required | Required | **BLOCKED** pending review of exact release/marketing |
| T02 | A controlled manual-evidence pilot states that no connected collector exists, confidence is capped at 60, real GO is unreachable, monitoring is unavailable, outputs are not forecasts and users must not treat them as professional approval | Pilot agreement, in-product copy and participant comprehension check | Required if collector is absent | Not sufficient | **BLOCKED** |
| T03 | Before advertising or selling the central evidence-backed decision promise, at least one permitted collector produces real dated observations with lineage, snapshots, durable retries and Data Health attempt/freshness/outage telemetry; a representative end-to-end result is independently reconciled | Source approval, collector/failure tests and real sample reconciliation | N/A only for constrained T02 pilot | Required | **BLOCKED** |
| T04 | Compliance decisions are made by named qualified reviewers within declared category/jurisdiction scope, independently of the requester, against current sources; expiry, rejection, correction and appeal are defined | Qualification/scope record and sampled decision audit | Required for actionable review; otherwise disable and disclose | Required | **BLOCKED** |
| T05 | Supported corridor, fields, formulas, units, rounding, assumptions, evidence thresholds, source coverage and known blind spots are documented and agree across server, browser and exports | Versioned methodology and contract/replay results | Required | Required | **BLOCKED** pending exact-release sign-off |
| T06 | Five representative pilot users complete the scoped real workflow without engineering intervention, can explain evidence versus assumptions and obtain a correct export/report; release-blocking usability failures are fixed | Usability protocol, results and dispositions | Required before expanding beyond initial supervised cohort | Required | **BLOCKED** |
| T07 | Evidence files/attachments, recurring monitoring, alerts, additional markets and any other unfinished capability are inaccessible and unadvertised, or each passes its own security, retention, rights, reliability and support gates | Feature inventory and entitlement/UI/API verification | Required | Required | **BLOCKED** pending scope audit |
| T08 | A designated owner verifies current regulatory, duty/tax and source claims immediately before release and sets an expiry/review cadence; software never presents uncited generated guidance as current law | Dated domain review and expiry schedule | Required where surfaced | Required | **BLOCKED** |

## 10. Commercial and public-launch gates

These gates may be **N/A** only for a free, invitation-only pilot whose agreement and UI make that
scope explicit. They are mandatory before payment or general availability.

| ID | Acceptance condition | Required evidence | Pilot | Public | Current |
| --- | --- | --- | --- | --- | --- |
| C01 | The initial customer/use case and promised outcome are supported by pilot evidence; messaging contains no unsupported integration, sales, demand, savings, compliance or monitoring claim | Pilot findings and approved claim-to-evidence matrix | N/A | Required | **BLOCKED** |
| C02 | Per-investigation/provider/review/storage/mail/support cost and peak budget are measured; price, quotas, failed-job credits and human-review fees cover the approved service model | Cost model and approved pricing/entitlement policy | N/A | Required | **BLOCKED** |
| C03 | If payment is accepted, billing/webhooks and entitlements are idempotent and tenant-safe; cancellation, renewal, refund, tax/invoice, failed-payment, export and deletion behavior are tested and disclosed | Payment test evidence and published commercial policy | N/A | Required if paid | **BLOCKED** |
| C04 | Public onboarding, account recovery, support, accessibility, privacy/terms and operational capacity work without engineering intervention | End-to-end public-launch rehearsal | N/A | Required | **BLOCKED** |
| C05 | Launch and incident communications have named owners; status/support channels exist and have been tested | Communication plan and test | N/A | Required | **BLOCKED** |

## 11. Final deployment gate

The release owner completes these in order. Deployment stops immediately on any failed step.

1. Freeze R01; record the commit, artifact digest, database revision and configuration version.
2. Attach the R03 CI evidence, R04 independent approval, risk register and all policy/operational
   approvals. Re-evaluate every **BLOCKED** and **N/A** row.
3. Confirm all required rows are **PASS** or validly **N/A** for the selected tier.
4. Confirm a recent verified backup, its offsite object, the measured restore result and the exact
   application/database rollback targets.
5. Rehearse the migration and complete critical-path, failure-path, capacity, alert and rollback tests
   in production-like staging.
6. Record the change window, operator, support/on-call contacts, stop thresholds and communication
   route. Prevent new-user intake during the change if the rollback plan requires it.
7. Deploy the immutable artifact; apply migrations once; confirm systemd/nginx configuration and
   `/api/health` plus `/api/ready`.
8. In the designated smoke workspace, test sign-in/session behavior, role denial, a representative
   product/evidence/decision/export reconciliation and the selected recovery path. Test every enabled
   external provider without using a real customer record.
9. Verify HTTPS/security headers, sensitive-log markers, metrics/dashboards, alert delivery, backup
   age and error/latency/resource levels. If any stop threshold fires, rollback.
10. Product, Engineering/Platform, Security/Privacy and Operations record the final **GO**. Admit only
    the cohort authorised for the chosen tier and monitor for the declared observation window.

## Release record — must be filled for every real-user release

Blank or `TBD` required values are **BLOCKED**, never implied approval.

Candidate-specific records: [`150d118` approval package](releases/2026-09-14-150d118-approval.md)
and successor [`ddde69a` blocker-closure record](releases/2026-09-14-ddde69a-blocker-closure.md).

| Field | Required value |
| --- | --- |
| Release tier and approved cohort | Free, invitation-only controlled pilot; exact named cohort remains approval-blocking and is admitted only by owner-issued email invitations |
| Commit SHA / tag | |
| Artifact ID and SHA-256 | |
| Build and remote CI links | |
| Independent review link / reviewer | |
| Known-risk register | |
| Previous application / database revision | |
| Migration and rollback drill link | |
| Backup object / checksum / restore-drill link | |
| RPO / RTO | |
| Backup, audit, app, nginx/journal and provider retention | |
| Expected and peak load / data volume | |
| Availability, latency and error objectives | |
| Rollback/stop thresholds | |
| Monitoring dashboards / alert destinations | |
| Product scope and explicitly disabled features | |
| Evidence sources and rights approvals | |
| Privacy notice / terms / vendor approvals | |
| Support hours, contact and response target | |
| Change window / post-release observation window | |
| Product approver / date | |
| Engineering or Platform approver / date | |
| Security or Privacy approver / date | |
| Operations approver / date | |
| Final decision and time | |

## Current software evidence — not a production approval

The tagged release candidate has the following local and remote automated evidence. This closes the
automated release gates, but it is not independent review or approval of the remaining production
and operational gates:

| Area | Current local evidence |
| --- | --- |
| Tenant isolation | Every id-taking route refuses another workspace; tests assert the other workspace's records remain unchanged |
| Authorization | Workspace-data routes require a session and `workspace.read`; the server-enforced role matrix, invitations and immediate suspension are covered end to end |
| Account security | Reset/change, sessions, verification and invitation flows have browser coverage; tokens are hashed, purpose-bound and single-use |
| Credential handling | scrypt parameters, HMAC rate identifiers and production setting validation are implemented and tested |
| Concurrency | Reset redemption, review decisions, research jobs, decisions and watches converge under PostgreSQL contention |
| Data integrity | Saved assessments remain immutable as evidence changes; workspace/saved exports reconcile with stored records |
| Schema/recovery tooling | Migrations through `0006`, physical-schema readiness, checksummed backups, encrypted offsite-copy support and a disposable PostgreSQL restore/replay drill exist |
| Deployment templates | Hardened systemd, explicit HTTPS CORS, security headers, disabled Uvicorn raw access logs and reduced nginx access logs are tracked |
| Frontend delivery | Initial JavaScript is about 118 kB gzipped; type, unit, production-build and browser checks pass locally |
| Automated checks | 532 applicable SQLite backend tests passed with 16 PostgreSQL-only skips; all 548 passed on PostgreSQL; 141 frontend and 47 browser tests passed; the three release-tool tests are included in both backend runs; local dependency, 181-package license-policy and redacting current/history/artifact secret scans pass |

## Known current product limits

* No collector is connected. All production observations are user-entered and capped at 60 confidence;
  GO requires 70, so a real actionable GO is unreachable.
* Operational counters are per worker and therefore only a floor, not fleet totals.
* The demo GO is synthetic and labelled as such.
* Application request logs intentionally retain pseudonymous workspace/user UUIDs for correlation;
  they still require access control and retention. Installed nginx error-log behavior is separate.
* Account mail transport exists but no provider/sending identity/deliverability monitoring is proven.
* Daily checksummed local/S3 backup and an S3-to-isolated-database production restore are proven,
  but missed-backup alerting, bucket-level TLS/Public Access Block evidence, formal RPO/RTO and a
  representative-scale timed restore remain open.
* Qualified reviewer ownership, on-call/support ownership and final privacy/retention choices are open.

The operational procedure supporting these gates is in [the runbook](RUNBOOK.md). Product sequencing
and feature-specific acceptance criteria remain in [the action plan](ACTION_PLAN.md).
