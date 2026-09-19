# Release blocker register after the priority implementation pass

Prepared 16 September 2026 UTC against the work following documentation commit `5051f5d`.
This is an execution register, not an approval record. Candidate SHA and remote CI evidence are
recorded separately after the implementation is committed and CI finishes.

## Reconciled baseline

The checklist contains **69 unique mandatory gate IDs**. Exactly **9 are PASS** for the prior
`ddde69a` candidate: `R01`, `R02`, `R03`, `F02`, `F03`, `F04`, `F05`, `F06`, `S08`.
The other **60 are BLOCKED**. A repeated `C05` visible in one prior combined command output was an
overlapping display boundary, not a seventieth checklist row; the source has one `C05`.

The 60 remaining unique IDs are:

`R04`–`R06`; `F01`, `F07`, `F08`; `S01`–`S07`, `S09`–`S11`; `I01`–`I07`;
`D01`–`D06`; `O01`–`O07`; `A01`–`A04`; `P01`–`P07`; `T01`–`T08`; `C01`–`C05`.

Once a successor code candidate exists, candidate-specific PASS evidence must be reattached to
that exact SHA. Prior results are not silently transferred where the changed code or environment
matters.

## Classification rules and totals

Each blocked gate has one primary remaining dependency, even where later dependencies also exist:

| Class | Meaning | Count |
| --- | --- | ---: |
| `E` | A particular environment, credential, mailbox, provider, target host or independent exercise is required | 15 |
| `H` | A named accountable human must choose scope/targets/owners or approve policy/risk | 38 |
| `N` | A named applicability owner must approve the proposed N/A and an independent reviewer must verify the exclusion | 7 |
| **Total** | Unique blocked gates | **60** |

“Implemented/tested locally” below is capability evidence only. It never means the complete gate
passes in production.

## Every remaining blocker

| Gate | Local implementation state | Primary remaining dependency and exact next evidence |
| --- | --- | --- |
| R04 | No substitution attempted | `H` — independent reviewer approves the exact candidate diff/artifact with dated findings |
| R05 | Updated risk dispositions can be drafted from this register | `H` — named owners accept severity, mitigation/disposition and review dates; blocker risks close rather than receive waivers |
| R06 | Templates now cover split database roles, immutable releases, deletion replay and monitoring | `E` — authorized read-only installed topology/config/ownership comparison, then owner review |
| F01 | Account, recovery, invitation and durable deletion paths have automated coverage | `E` — exact-candidate PostgreSQL smoke through an authorized real mailbox and a production-like workspace deletion |
| F07 | Chromium regression suite exists | `H` — Product/Engineering first names the supported current browser/device matrix; authorized devices then run it |
| F08 | Server/UI changes preserve keyboard-native controls | `H` — Product declares pilot accessibility/assistive-technology target before scan and human keyboard/screen-reader evidence |
| S01 | Separate runtime/migration/monitor service designs and fail-closed settings exist | `H` — Security/Platform names secret/access owners and approves storage, rotation and emergency revocation; redacted audit follows |
| S02 | Least-privilege PostgreSQL grant/apply/check/rollback tools are implemented | `E` — isolated staging apply plus target listener/firewall/database TLS and privilege evidence |
| S03 | TLS probe and alert event exist | `E` — configured target expiry alert reaches a named operator and recovery is recorded |
| S04 | No unsupported component is introduced | `H` — Platform/Operations approves patch owner, cadence, support windows and next review date |
| S05 | Authentication controls remain covered automatically | `E` — installed proxy trust/spoof exercise on the exact artifact |
| S06 | Limits remain server-enforced | `H` — Security/Product approves legitimate and abusive traffic thresholds; installed proxy exercise then verifies them |
| S07 | Monitor reads bounded structured journal signals; existing safe log formats remain | `H` — Security/Privacy and Operations approve access and numeric retention; installed disposable-marker test follows |
| S09 | No claim of independent testing | `H` — qualified independent security reviewer scopes and performs the authenticated target review |
| S10 | Separate service identities are templated | `H` — Security/Operations approves named production/support access, MFA, review and offboarding records |
| S11 | Incident/data-request procedure already drafted | `H` — named Security/Privacy decision-makers approve it; an independent tabletop then exercises it |
| I01 | Production validation now refuses ambiguous pilot/deletion/review configuration | `H` — owners approve every non-secret value and review a redacted installed environment |
| I02 | Role split uses non-superuser migration ownership and DML-only runtime grants; CI exercises both | `E` — provider/staging roles, TLS/at-rest/capacity facts and privilege checker output for the exact installation |
| I03 | Hardened service templates include distinct migration and monitor identities | `E` — install/diff/verify, restart and reboot on approved staging/target hosts |
| I04 | Synthetic-data-only staging proposal is documented | `H` — Engineering/Platform funds/names staging; Security/Privacy approves topology, access and data-handling rule |
| I05 | No unapproved load claim added | `H` — Product/Platform approves normal/peak users, requests, records, jobs and success/headroom targets |
| I06 | SMTP and selected live collectors remain explicit server-side opt-ins; adapter/configuration/collection/stored-observation/API states are distinct and browser display is verified separately | `H` — accountable owners approve accounts, accepted terms/plan/intended-use bases, region, quota/budget, expiry and contacts; Bright Data compliance accepts the declared `jumia.com.ng` use; then `E` — authorized real collection and browser-display evidence |
| I07 | Exact checksum/manifest staging, atomic activation and drift-resistant paths are implemented | `E` — exact CI artifact deploy log and configuration comparison from production-like staging |
| D01 | Recovery proposals are in the decision sheet | `H` — named Product, Platform and Operations owners approve RPO/RTO, scope and retention |
| D02 | Backup age/integrity is included in persistent monitoring; deletion sync has a path plus reconciliation timer | `E` — bucket TLS/Public Access Block/IAM/lifecycle proof and a delivered absence/failure alert |
| D03 | Existing representative synthetic restore method remains available | `H` — owners approve representative scale/RTO; authorized isolated timed restore then meets it |
| D04 | Append-only checksummed deletion register, off-host sync, verifier and idempotent restore replay are implemented/tested locally | `E` — exact-artifact restore, register download/verification/replay and audit record in authorized isolated staging |
| D05 | Exact release switch and application rollback preserve the prior target without schema downgrade | `E` — staging proves previous application compatibility after migration or new-database restore/switch |
| D06 | This pass adds no schema revision | `N` — Platform and independent reviewer confirm no release migration/backfill and approve N/A for this candidate |
| O01 | Proposed thresholds are configurable and recorded in monitor state | `H` — four release roles approve SLOs, stop/rollback thresholds and support window |
| O02 | Host-persistent fleet journal/readiness/error/latency, PostgreSQL, service, disk, backup and TLS state/metrics are implemented | `H` — Operations names viewer/owner and approves 30-day retention; installed access proof follows |
| O03 | State-change/reminder/recovery webhook delivery and independent heartbeat support are implemented | `H` — Operations selects destination/recipients and thresholds; Security approves credential handling |
| O04 | Synthetic `--test-alert` injection is implemented without being invoked externally | `E` — authorized end-to-end drill reaches the named operator and times acknowledgement/escalation/recovery |
| O05 | Existing runbook plus new role/deletion/monitor/release tooling cover the technical procedures | `E` — operator other than the author completes staging deploy/rollback/restore/provider/saturation drills |
| O06 | No owner fabricated | `H` — Product/Operations names support contact, hours, response target and escalation, then tests a request |
| O07 | Rate/mail/storage work remains bounded in code | `H` — Product/Operations approves budgets/quotas and destinations before vendor cost alerts are tested |
| A01 | Registration remains closed and owner invitations/revocation are enforced | `H` — Product/Operations names initial owner, exact cohort and mailbox owners; target smoke follows |
| A02 | Standards-based TLS SMTP flows and monitor probe exist | `H` — owners approve provider/sender/terms and authorize disposable-mailbox plus bounce/failure alert evidence |
| A03 | No-mail config reports operator-required recovery and existing trusted-channel procedure remains | `H` — only if A02 is rejected: name operator, support window, participant notice and authorize drill |
| A04 | Deletion register/replay closes the prior repository implementation gap | `E` — production-like delete/export, backup expiry and restore replay evidence under approved retention |
| P01 | Repository data map can incorporate new pseudonymous deletion and monitor state | `H` — Product/Security/Privacy approves deployed locations, purposes, access and retention |
| P02 | Product surfaces expose actual disabled/recovery state | `H` — Product/Privacy approves and publishes versioned notice plus delivery/acceptance record |
| P03 | Every retention is configurable or proposed; no policy is asserted as approved | `H` — Product/Privacy/Operations approves numeric schedule and deletion wording; expiry tests follow |
| P04 | Selected collectors are implemented but remain off; manual provenance remains explicit and cannot count as collection | `H` — Product/Privacy or counsel approves each provider’s internal research, user display, derived-metric and retention rights plus manual-source permitted use |
| P05 | Existing limitations/appeal drafts remain inputs only | `H` — accountable Product/Privacy/counsel approves terms, prohibited use and complaint/appeal route |
| P06 | No vendor approval fabricated | `H` — Security/Privacy/Procurement approves Resend/S3 terms, locations, contacts and required agreements |
| P07 | Procedure and log template exist | `H` — named lawful-notification/data-request owners approve them; tabletop/response record follows |
| T01 | Public config/UI now exposes feature truth and import-review exclusion | `H` — Product and independent reviewer sign exact UI/API/export/marketing claim inventory |
| T02 | Manual evidence cap and unavailable capabilities remain enforced/disclosed | `H` — Product approves pilot agreement/notice and participant comprehension protocol |
| T03 | Live collection is now required product scope; production still has no selected collector or observation | `E` — after provider rights/budget approval, exact-candidate staging and bounded production investigations display real catalog, Nigeria demand/local-market and FX provenance; independent reviewer verifies no demo/manual/auth-only substitution |
| T04 | Production defaults import review off; API returns 404, UI fails closed, old records cannot clear the gate | `H` — Product/domain owner approves exclusion; independent reviewer verifies it, or qualified review scope must be supplied |
| T05 | Contract/replay tests remain; no substantive methodology approval inferred | `H` — Product and methodology owner approves corridor, formulas, units, assumptions, coverage and blind spots |
| T06 | Usability is not fabricated by automated browser tests | `E` — after cohort approval, five representative users complete the supervised protocol and findings are dispositioned |
| T07 | Public feature inventory now explicitly disables billing, public registration, monitoring alerts, attachments, extra markets and import review | `H` — Product approves exclusions; independent exact-artifact UI/API audit confirms inaccessible and unpromised |
| T08 | No current-law approval inferred | `H` — qualified Nigeria domain owner approves dated claims/sources/cadence or Product removes them |
| C01 | Free controlled-pilot proposal exists | `N` — Product/independent reviewer confirms no public customer promise |
| C02 | Billing remains absent and disabled | `N` — Product/Operations confirms no charge or commercial model; O07 internal budget still applies |
| C03 | Payment/webhooks/paid entitlement routes are absent | `N` — Product/independent reviewer confirms inaccessible and unpromised |
| C04 | Public/paid tier is rejected by settings | `N` — Product/independent reviewer confirms no public onboarding/availability claim |
| C05 | No public launch channel is claimed | `N` — Product/Operations confirms public communications are out of scope; internal support/incident ownership remains required |

## Priority implementation completed before target verification

- `I02/S02`: separate PostgreSQL runtime and migration roles, idempotent least-privilege
  grants, live CRUD/DDL privilege checks, dedicated migration unit and explicit emergency rollback.
- `D04/A04`: fail-closed durable deletion intent, checksums, off-host sync units, startup replay,
  restored-database replay command and tamper/missing-register tests.
- `O02/O03`: host-persistent observations/deliveries/metrics, state-change and reminder alerts,
  retryable recovery delivery, heartbeat support and probes for the checklist's host/service/data
  dependencies.
- `I07/D05`: exact-artifact checksum/manifest validation, immutable release directories, atomic
  current/previous links, repeat-safe activation and application rollback without destructive
  database downgrade.
- `A02/A03/T04/T07`: explicit recovery mode and feature inventory; production import review is
  off without an approved policy reference, server endpoints reject use, calculations cannot treat
  stored reviews as actionable, and the UI fails closed.

These changes deliberately do not provision infrastructure, change production, send an alert or
mail, appoint an owner, approve a policy, or satisfy independent review.
