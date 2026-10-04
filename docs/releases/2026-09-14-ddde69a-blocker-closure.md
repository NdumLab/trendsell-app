# Release blocker closure record — `ddde69a`

Prepared: 14 September 2026 UTC

Target: `https://trendsell.yerikasystems.com`

Release tier: free, invitation-only controlled pilot

Current decision: **NO-GO — 60 mandatory gates remain blocked**

This record follows the [`150d118` approval package](2026-09-14-150d118-approval.md).
It classifies every one of that package's 62 blocked gates, records the technical work
completed without changing production, and identifies the successor candidate created by
the CI maintenance fix. Missing evidence is not described as a defect unless an exercised
check actually demonstrated a failed acceptance condition.

## 1. Successor candidate identity

| Field | Exact evidence |
| --- | --- |
| Candidate commit | `ddde69af2a48ec017f87b57274c0fd150322755d` |
| Change after `150d118` | Documentation-only approval package, followed by a CI-only change from all seven `actions/checkout@v4` uses to `actions/checkout@v7`; backend, frontend, contracts, migrations, deployment templates and release scripts are unchanged |
| Remote CI | [Run 34880189151](https://github.com/NdumLab/trendsell-app/actions/runs/34880189151); all seven jobs passed |
| GitHub artifact | ID `10362387379`, `trendsell-release-ddde69af2a48ec017f87b57274c0fd150322755d` |
| Release archive | `trendsell-ddde69af2a48.tar.gz` |
| Archive SHA-256 | `de73c98cdd8208f48a78e31919ddc327f11efda8d2f6237a47f8c55b31dfb858` |
| GitHub wrapper digest | `sha256:55b4984a7f3daaaf07af1dd6e1169286f48d30600acbe00311f9f6a05bda1373` |
| Embedded manifest | `trendsell-release/1`; commit exactly `ddde69af2a48ec017f87b57274c0fd150322755d` |

The downloaded archive passed its published `sha256sum --check`, and its embedded
manifest was read from the archive. The old `150d118` artifact is not represented as the
artifact for this candidate. The checkout update closes risk K13's deprecated-runtime
maintenance item; it does not itself close a mandatory gate or approve the release.

## 2. Classification of the original 62 blocked gates

Each gate has one **primary** class below so the accounting is exact. A row can still have
secondary dependencies; for example, a missing alert implementation also needs a human to
name its destination. “Verification missing” means the required exercise or record is
absent or incomplete, not that the underlying behavior is known to be defective.

| Primary class | Count |
| --- | ---: |
| 1. Technical work required | 4 |
| 2. Verification or evidence missing | 19 |
| 3. Human decision or approval required | 32 |
| 4. Proposed N/A awaiting an authorized applicability decision | 7 |
| **Total** | **62** |

### 2.1 Technical work required — 4

| Gate | Concrete blocker |
| --- | --- |
| `S11` | At classification time, the repository had release/recovery guidance but no complete incident and personal-data-breach runbook covering detection, containment, credential rotation, evidence preservation and notification decision-making. Section 3 records the draft added in this pass; named contacts, approval and a tabletop are still required. |
| `D04` | Self-service deletion removes the live workspace and its in-database audit rows, but no durable out-of-band tombstone or deletion-request register exists to identify changes made after a restored recovery point. A transactional, access-controlled replay mechanism must be designed and tested; the existing prose warning is not a mechanism. |
| `O02` | Metrics remain process-local and reset on restart. There is no fleet aggregation/view combining both workers with PostgreSQL/service/host saturation, access control and retention. Manual journal queries are evidence of available raw signals, not an implemented fleet view. |
| `O03` | The required alert delivery paths do not exist for readiness, error/latency, restart loop, database exhaustion, disk, backup age/failure, TLS expiry and SMTP. Threshold and destination choices are human inputs, but wiring and bounded delivery behavior are technical work. |

### 2.2 Verification or evidence missing — 19

| Gate | Concrete blocker |
| --- | --- |
| `R06` | The installed service/nginx fingerprints, listeners and redacted settings were observed, but the complete reviewed topology record still lacks host/database privilege disposition and named ownership. The later read-only role query found a least-privilege issue described in section 4. |
| `F01` | Local browser tests use delivered sink messages for reset, email verification and invitation tokens and exercise workspace deletion. A real approved mailbox/provider path and a production-like deletion run are still absent; this is missing target-path evidence, not a confirmed failure of those flows. |
| `F05` | At classification time, the complete exact-candidate PostgreSQL migration, process restart and readiness path with representative data was absent. Section 3 supplies it and closes this gate for `ddde69a`. |
| `F06` | At classification time, automated negative cases existed but no production-mode staged dependency timeout/fault exercise existed. Section 3 supplies it and closes this gate for `ddde69a`. |
| `S02` | Public/private listener topology passes, but database and hosting controls were incomplete. The read-only role check now confirms the runtime role is not least privilege; at-rest/TLS hosting evidence is also unresolved. |
| `S03` | HTTPS, current TLS protocols, headers and a successful renewal dry run now pass. A renewal-expiry alert reaching an owner is still absent, so the gate remains blocked rather than treating the technical checks as full proof. |
| `S05` | Automated session, token, revocation and anti-enumeration controls pass. No candidate exercise through the installed trusted-proxy path proves that forwarded addresses cannot spoof rate identities. |
| `S06` | Limits are configured and automated boundary tests pass. No installed-proxy abuse/legitimate-traffic run demonstrates the chosen thresholds under the real framing and forwarding path. |
| `I03` | Installed templates match and validate and the service is active. There is no exact-candidate installed restart plus host reboot/recovery record; absence of that test is not proof the service would fail. |
| `I04` | Disposable production-mode stacks exist, but no approved environment comparison shows a persistent staging installation mirrors production topology and handles only synthetic/sanitized data. |
| `I07` | Release procedures and drift fingerprints exist. The exact artifact/static/config/systemd deployment and rollback sequence has not been executed end to end in persistent production-like staging. |
| `D02` | Local/offsite object integrity evidence passes. The scoped backup identity still receives `AccessDenied` for Public Access Block, public-policy status, default encryption, versioning, lifecycle and bucket-policy reads, and no failure reaches a named operator. These unavailable control reads are not evidence that a bucket control is disabled. |
| `D05` | Candidate/previous-application database compatibility passes, but the real artifact/static/service switch and rollback have not been rehearsed in staging. The prior app's expected export-v2 behavior also needs Product/Platform disposition. |
| `O04` | No critical alert can yet be injected through the missing O03 delivery paths to a named operator with timed acknowledgement, escalation and recovery. |
| `O05` | The runbook exists, but an operator other than its author has not executed the required deploy/rollback/restore/security/provider/saturation tabletop or drill. |
| `A04` | Local export, live-record cleanup and workspace-deletion behavior pass. A production-like workspace deletion and the D04 post-restore replay path are untested. |
| `T01` | Repository surfaces were inventoried and current truth-state/disclaimer checks pass, but accountable exact-release review of UI, API exports, reports and any operator-controlled marketing/support statement has not been recorded. In particular, import-readiness wording must be disposed together with T04. |
| `T06` | No five-person supervised usability study demonstrates that representative pilot users complete the scoped workflow, understand evidence versus assumptions and obtain a correct export without engineering intervention. No usability defect is inferred merely from the absent study. |
| `T07` | The exact API has 50 routes, no billing/payment route and no upload/attachment route; registration is closed, billing is false, watches are unscheduled and alerts report unavailable. The gate still fails because actionable compliance-review endpoints remain accessible without T04-qualified ownership, and mail surfaces remain accessible while A02/A03 is unresolved. |

### 2.3 Human decision or approval required — 32

| Gate | Concrete blocker |
| --- | --- |
| `R04` | A reviewer independent of the implementation must approve or reject the exact `ddde69a` diff and record dated findings/dispositions for all required correctness and truthfulness areas. Automated success is not that review. |
| `R05` | Every K01–K12 risk still needs an accountable owner, disposition and review/expiry date; K13 is technically closed but must be recorded as such. High/blocking risks cannot be accepted around a failed gate. |
| `F07` | Product/Engineering must first approve the supported browser/device matrix. Current Chromium success cannot be generalized to unnamed browsers or devices. |
| `F08` | Product must declare the pilot accessibility target and supported assistive-technology scope before scan, keyboard and assistive-technology results can be judged against it. |
| `S01` | Security/Platform must name secret and access owners, attest uniqueness/least privilege, and approve rotation and emergency revocation procedures. Redacted parsing only proves values are syntactically acceptable. |
| `S04` | Platform/Operations must own the OS/nginx/PostgreSQL/Python/Node patch cadence, approve support windows, record update evidence and set the next review date. |
| `S07` | Security/Privacy and Operations must approve log access ownership and numeric retention. Installed disposable-marker verification is still required afterward. |
| `S09` | A qualified independent security reviewer must scope and execute the internet-facing authenticated review, then approve findings only after required remediation. |
| `S10` | Security/Operations must approve the named production/support access list, strong-authentication/MFA evidence, review cadence and offboarding procedure. |
| `I01` | Platform plus Product/Privacy must approve the five currently defaulted non-secret values, especially audit retention, before they may be made explicit in production. Safe defaults are not deliberate owner choices. |
| `I02` | Platform/Security must approve separate migration/runtime privilege design, database transport/at-rest controls, connection ceiling/pooling and maintenance/upgrade ownership. The current runtime role's broad rights must not be silently accepted. |
| `I05` | Product/Platform must approve normal/peak users, requests, jobs and data volume plus latency/error/resource/headroom/cost targets before a load result can pass this gate. The five-workspace specimen in section 3 is not target approval. |
| `I06` | Product/Security/Operations must approve the SMTP provider account, terms, region, quotas/budget, credential expiry and operational contacts. Amazon remains disabled pending a separate rights decision. |
| `D01` | Product/Platform/Operations must approve numeric RPO/RTO, backup scope, local/offsite retention and maximum tolerable loss. |
| `D03` | The timed 900-record restore in section 3 is useful evidence, but only an authorized owner can define representative scale and approve the RTO it must meet. It cannot be declared compliant against an unapproved four-hour proposal. |
| `O01` | Product/Platform/Security/Operations must approve availability, latency, error and rollback/stop thresholds and the support window in which they apply. |
| `O06` | Product/Operations must name the support owner, secure contact path, hours, response target and escalation route, then authorize publication and testing. |
| `O07` | Product/Operations must approve vendor/compute/storage/mail/support budgets and cost ceilings before bounded enforcement/alerts can be implemented and tested. |
| `A01` | Product/Operations must name the pilot owner, exact cohort and mailbox owners and confirm that nobody else is admitted. The existing registration and revocation controls already pass their exercised parts. |
| `A02` | The account-delivery owner must choose the SMTP path and approve provider/sender/DNS/bounce monitoring plus access to disposable real mailboxes. SMTP acceptance alone does not prove received-token flows. |
| `A03` | Alternatively, Product/Operations must choose to disable SMTP, name a trusted-channel operator, approve support hours and participant wording, then authorize the recovery drill. A03 is not automatically selected because A02 is incomplete. |
| `P01` | Product/Security/Privacy must approve the deployed data inventory, purposes, locations, access and retention choices. The repository inventory is a draft input, not accountable approval. |
| `P02` | Product/Privacy must approve and publish the versioned notice and its pre-data-entry delivery/acceptance record. |
| `P03` | Product/Privacy/Operations must approve complete numeric retention, including logs and providers, and the truthful deletion/backup-expiry wording; configured expiry tests alone cannot choose policy. |
| `P04` | Product/Privacy or qualified counsel must approve the permitted-use decision for every manual source-reference practice and confirm the disabled external-provider exclusion. |
| `P05` | Product/Privacy or qualified counsel must approve terms, limitations, prohibited use and the complaint/appeal route for the pilot jurisdiction and promise. |
| `P06` | Security/Privacy/Procurement must approve Resend and S3 processor/security/privacy terms, data locations, contacts and any required agreement. |
| `P07` | Security/Privacy must name incident-notification and data-request owners and approve the lawful procedure and request log before a tabletop can validate it. |
| `T02` | Product must approve the constrained manual-evidence agreement and participant notice, and representative participants must demonstrate comprehension. |
| `T04` | Product/domain owners must either name qualified independent import reviewers with category/jurisdiction scope and cadence, or authorize disabling actionable-review claims and behavior. Software role assignment does not prove qualification. |
| `T05` | Product and a methodology owner must approve the exact corridor, methods, formulas, units, assumptions, blind spots and claims for this candidate. Passing contracts proves implementation consistency, not substantive fitness. |
| `T08` | A qualified Nigerian regulatory/duty/source owner must approve the dated source review, scope and expiry cadence, or Product must authorize removal of current-law claims. |

### 2.4 Proposed N/A awaiting an authorized applicability decision — 7

| Gate | Exact applicability decision still required |
| --- | --- |
| `D06` | Platform and the independent reviewer must confirm that `ddde69a` contains no release migration and approve N/A; any unexpected DDL remains a stop condition. |
| `T03` | Product and the independent reviewer must approve the constrained T02 pilot and confirm the collector is disabled, inaccessible and unpromised before T03 can be N/A. |
| `C01` | Product and the independent reviewer must confirm the release is free, invitation-only, unadvertised and unpaid, so public customer/use-case evidence is outside this pilot. |
| `C02` | Product and Operations must confirm no price is charged and no commercial service model is promised, so pricing/cost coverage is outside this pilot. Internal cost ceilings under O07 remain required. |
| `C03` | Product and the independent reviewer must confirm payment, billing webhooks and paid entitlements are inaccessible and unpromised. |
| `C04` | Product and the independent reviewer must confirm public onboarding/operations are out of scope and no public availability is advertised. |
| `C05` | Product and Operations must confirm no public launch/incident communications promise is made. Internal pilot incident/support ownership remains required. |

The identifier sets in these four tables are disjoint and total `4 + 19 + 32 + 7 = 62`.
The seven proposed N/A rows remain **BLOCKED** until the named authorized applicability
decisions are recorded; none is counted as passed.

## 3. Technical work and verification completed

### CI and regression evidence

- Exact `ddde69a` remote CI passed backend SQLite and PostgreSQL jobs, frontend tests/type/build,
  Chromium browser tests, clean-clone reproducible artifact builds, secret/history scans and
  dependency/license checks.
- Local checks passed: 568 backend tests on SQLite, 568 on disposable PostgreSQL 16.4,
  141 frontend tests, TypeScript/build, and 53 Chromium browser tests.
- Runtime and development Python vulnerability scans found no known vulnerability; npm reported
  zero vulnerabilities; the locked 181-package license inventory and tracked/history secret scan
  passed.

### F05 migration, restart and readiness — PASS for `ddde69a`

The downloaded exact artifact was run against a disposable loopback-only PostgreSQL 16.4
container. A fresh database migrated through `0001`–`0006`. Five synthetic workspaces were
then populated with 20 investigations each: 100 products, 100 jobs, 400 evidence records,
100 CNY quotes, 100 saved decisions and 100 watches (900 domain records total). No customer
or production data was used.

The artifact started twice as a real two-worker Uvicorn process with production settings.
Both starts returned ready at `0006_workspace_invitations`; a no-op candidate upgrade was
run between them. Registration remained 403, billing false and Amazon disabled. The exact
artifact's backup script wrote a 191,745-byte custom dump in 0.260 seconds; its restore
script restored a separate database in 0.392 seconds. Workspace/record counts reconciled
by ID and all 100 saved assessments replayed with zero failure. The disposable databases,
dump and processes were removed afterward.

This satisfies F05. It does not approve capacity targets or RTO and therefore does not by
itself pass I05 or D03.

### F06 staged negative and dependency-fault exercise — PASS for `ddde69a`

The downloaded exact artifact ran as a two-worker production-mode process against a
disposable PostgreSQL 16.4 database and a local SMTP socket that accepted a connection but
never sent a greeting. Results were: invalid request 422, unauthorized read 401, oversized
request 413, and SMTP timeout after 15.083 seconds with a non-enumerating 202 response whose
wording remained conditional on delivery succeeding. The disposable email, password and
token markers did not appear in captured service logs. Existing automated negative tests
cover provider unavailable/rate-limit/auth failures, chunked and false-length oversized
requests, tenancy denials, session/token misuse and failed-read truthfulness.

This satisfies F06. It does not pass S05/S06 because it did not exercise the installed
production proxy or approved legitimate-traffic thresholds.

### Reusable host/environment evidence that remains partial

- The unchanged public endpoint redirects HTTP to HTTPS; TLS 1.2 and 1.3 succeed and TLS 1.1
  is refused. HTML, API and a hashed asset carry the expected CSP, HSTS, frame, content-type,
  referrer and permissions headers. The certificate covers the target hostname through
  6 December 2026, the Certbot timer is active, and a staging `certbot renew --dry-run`
  succeeded. S03 remains blocked on expiry alert delivery and named ownership.
- Nginx remains the only public TrendSell listener. The API and PostgreSQL listeners are
  loopback-only and UFW is default-deny inbound except limited SSH and HTTP/HTTPS. The
  installed unit and nginx fingerprints still match those recorded in the `150d118`
  package. This evidence is reusable because the successor does not alter the templates.
- The production database role is not superuser and cannot create roles/databases,
  replicate or bypass row security. It nevertheless has database `CREATE` and `TEMP` plus
  all table privileges, including `TRIGGER` and `TRUNCATE`; its observed app connection is
  not TLS. S02/I02 therefore have a demonstrated least-privilege/transport issue requiring
  an approved separate migration/runtime-role and hosting-control design.
- The scoped backup identity was denied every bucket-control read attempted: Public Access
  Block, public-policy status, default encryption, versioning, lifecycle and bucket policy.
  Existing object-level checksum/encryption/anonymous-denial evidence remains valid, but
  `AccessDenied` is not proof that bucket controls are absent or present. D02 remains blocked.

### S11/P07 incident and data-request procedure — drafted, gates remain BLOCKED

The new [incident, breach and data-request runbook](../INCIDENT_AND_DATA_REQUEST_RUNBOOK.md)
defines incident triggers, first response, evidence preservation, containment, credential
rotation, notification decision fields, recovery checks and request handling. This completes
the unblocked repository drafting work identified under S11 and supplies the P07 procedure
and empty request-log template.

It does not appoint notification or request owners, provide secure contact paths, approve a
legal or policy basis, implement the D04 out-of-band deletion register, wire O03 alerts, or
record an independent tabletop. Those are required evidence, technical dependencies or human
decisions, so S11 and P07 remain **BLOCKED**.

## 4. Gate disposition after this pass

Nine gates are now **PASS** for `ddde69a`: `R01`, `R02`, `R03`, `F02`, `F03`, `F04`,
`F05`, `F06` and `S08`. The other 60 mandatory gates remain **BLOCKED**. K13 is closed as
a risk-register maintenance item but is not a mandatory gate, so it does not change that
count. Production remains unchanged on `90d6312`.

## 5. Consolidated human decisions and approvals required

The same person may hold several release roles where the checklist permits, but every role
decision must be explicit and the independent reviewer must remain independent of the
implementation.

1. **Product/release owner:** name the exact owner and cohort; approve the manual
   China-to-Nigeria pilot scope, claim inventory, T02 agreement/participant notice,
   supported browser/device matrix, accessibility target, and exclusions for collectors,
   monitoring, attachments, additional markets and public/paid promises.
2. **Authorized applicability owners:** decide `D06` and `T03` individually and `C01`–`C05`
   individually as N/A or required; record the basis that each excluded capability is
   inaccessible and unpromised. Silence is BLOCKED, not N/A.
3. **Independent release/security reviewer:** review the exact `ddde69a` diff and artifact;
   approve or reject R04 with dated findings/dispositions and perform the S09
   internet-facing authenticated security scope, or identify a separate qualified reviewer.
4. **Risk owners:** assign K01–K12 and closed K13; record severity, user impact,
   mitigation/disposition and review/expiry dates. Blocking risks must be closed, not accepted
   around a failed gate.
5. **Security/Privacy policy owner:** approve the data inventory, privacy notice, terms,
   numeric retention/deletion wording, manual-source permitted use, Resend/S3 processor and
   location treatment, secret/access/rotation ownership, log access, incident/breach process
   and data-request process.
6. **Engineering/Platform owner:** approve the five explicit configuration values, a
   separate least-privilege migration/runtime database-role design, database encryption and
   maintenance ownership, patch cadence, persistent staging topology, capacity targets,
   deployment/rollback rehearsal, and the RPO/RTO/backup scope proposal.
7. **Operations/on-call owner:** name the alert and support destination, support hours,
   response/escalation target, log retention/access, monitoring view, change/observation
   window, stop thresholds, cost ceilings and alert-drill participants.
8. **Account-delivery owner:** choose exactly one pilot path—complete A02 using an approved
   SMTP sender, real disposable mailboxes and bounce/failure monitoring, or disable SMTP and
   satisfy A03 with a named trusted-channel operator, support window, participant notice and
   completed recovery drill.
9. **Qualified import-review owner:** name reviewer identities, Nigerian jurisdiction and
   product-category scope, qualification basis, requester independence and review/expiry
   cadence, or authorize disabling actionable-review claims and behavior.
10. **Methodology/domain owner:** approve the exact corridor, sources, formulas, units,
    assumptions, blind spots, claims and dated Nigerian regulatory/duty/source review with
    an expiry date.
11. **All four release roles:** record Product, Engineering/Platform, Security/Privacy and
    Operations UTC-dated decisions only after every required gate is PASS or validly N/A.
    Final signatures cannot substitute for the remaining technical work and verification.
