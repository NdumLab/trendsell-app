**TrendSell — detailed plan of action**

Created: 8 September 2026. Last corrected: 9 September 2026. Status: **in progress**.

An independent review on 8 September ([CLAUDE_IMPLEMENTATION_REVIEW_2026-09-08.md](CLAUDE_IMPLEMENTATION_REVIEW_2026-09-08.md)) found that several items marked `Done` here had integration regressions that the suite did not catch, and declined to sign off on Gate A. Those findings (R01–R11) are corrected and verified — see [CLAUDE_HANDOFF.md](CLAUDE_HANDOFF.md) — and the statuses below have been rewritten to distinguish *implemented and locally verified* from *externally blocked*. Gate A is **in review**, not done: it is awaiting the independent re-review, and deployment stays pending that sign-off.

Phase 1 is implemented except account recovery (blocked on an email provider) and the production half of backup/restore. Selected Phase 2/3 items — manual evidence, the evidence-quality method, the compliance-review workflow and server-computed gates — are implemented against self-reported evidence only. **No live collector is connected**, so all production evidence remains self-reported and capped at 60 confidence, below the 70 a GO requires: a real end-to-end GO is not yet demonstrable.

This is the current execution roadmap. It combines the [repository and deployment review](APP_REVIEW_2026-09-08.md), the additional analyst review supplied by the product owner, and the subsequent reconciliation. It supersedes the implementation order in [FEATURES_ROADMAP.md](../FEATURES_ROADMAP.md) and the historical [prototype PRD](../memory/PRD.md). The [complete redesign document](../TrendSell_Complete_Redesign_Plan-1.docx) remains a vision reference; this plan determines the next work.

**Outcome we are building toward**

A user can investigate a real product for China → Nigeria, inspect its identity and dated demand evidence, compare local context and supplier quotes, understand landed cost and import readiness, and save a reproducible decision. When evidence is insufficient, the app identifies the specific missing work and provides a way to complete it.

The longer-term differentiator remains: **what appears to be driving interest, whether that opportunity translates to Nigeria, and what it would take to source and sell the product responsibly**. Search, marketplace activity, advertising, creators, promotions, and store activity belong in that investigation when permitted sources support them. Association must be distinguishable from measured sales and causal attribution.

The first real pilot does not require an artificially manufactured GO result. It requires useful evidence and a defensible result. A complete synthetic GO example will separately teach the full workflow.

**Baseline and planning assumptions**

| Area | State at the reviewed checkout, `59414e5` |
| --- | --- |
| Architecture | React/TypeScript/Vite frontend; FastAPI/Pydantic/SQLAlchemy API; production PostgreSQL; SQLite used locally |
| Product scope | China → Nigeria; Amazon US identifiers and prospective search demand as discovery inputs |
| Evidence | Zero connected collectors; populated search/review examples are demo fixtures |
| Actual API decisions | Zero evidence confidence; insufficient evidence, or NO-GO when the user marks an item prohibited; no working path to WATCH or GO |
| Sourcing | Manual quote records and downloadable RFQ drafts |
| Retention | Saved watch rules; no scheduled collection or notification delivery |
| Verification | 109 backend and 50 frontend tests passed, but tenancy fixtures and browser coverage have material gaps |
| Known failures | Export integrity, monetary precision, product truncation, request races, browser-test discovery, and a Python dependency advisory |
| Deployment | Running HTTPS/PostgreSQL installation; migrations and deployment configuration are not fully represented in the repository; restore capability unverified |

Planning scope is one corridor and a small, deliberately selected pilot catalog. Source access, licensing, provider costs, reviewer availability, email delivery, and infrastructure choices are unresolved dependencies. Verify them before selecting implementations or making capability promises. No API field, marketplace access right, regulatory rate, service price, or delivery date is assumed by this document.

**How to execute and maintain this plan**

- Keep each work item in one of: `Planned`, `Ready`, `In progress`, `Blocked`, `In review`, `Done`. All items below start as `Planned`.
- Each issue/PR must quote its item ID, dependencies, acceptance checks, and evidence of completion. Assign one accountable owner before starting it; suggested disciplines appear below, not named people.
- Move to `Done` only when acceptance checks pass and applicable migrations, documentation, operational checks, and release notes are complete. A mockup, successful build, or successful provider request alone does not complete a feature.
- Record blockers with the missing input, responsible owner, next action, and check-in date. Source-access research can begin while stabilization proceeds; enabling collection depends on the platform and data-rights gates.
- Size work after implementation discovery. Sequence is governed by acceptance gates, not speculative calendar deadlines. Provider approval waits and human review capacity must be tracked separately from engineering work.
- Implement narrow, reviewable changes. Preserve working pilot behavior and historical assessments. Do not combine a broad rewrite with a correctness fix.
- This document authorizes no spending, supplier outreach, advertising campaigns, data-source agreements, or deployment by itself. Those are separately configured execution activities; preparing code and a reviewable release should precede any final deployment decision.

**Implementation status**

Updated as work lands on `impl/evidence-platform-phase0`. An item is `Done` only when its
acceptance checks were run and passed; anything unverified stays `Planned` or `Blocked`.

The 8 September review showed that passing an item's own acceptance checks is not the same
as the feature working end to end — T03, T05, T07 and T08 each held while a cross-feature
path through them was broken. `Done` below therefore means *implemented and verified
locally, including the cross-feature regressions the review identified*. It does not mean
independently reviewed, and it does not mean deployed.

| Item | Status | Evidence |
| --- | --- | --- |
| T01 audit regressions | Done | `tests/redesign/test_tenant_isolation.py`; shared app/database with separate cookie jars; whole suite also runs on PostgreSQL via `TEST_POSTGRES_URL`; removing the workspace filter fails 6 tests |
| T02 Playwright isolation | Done | `frontend/playwright.config.ts`, `frontend/e2e/`; disposable API + SQLite file per run; `test:e2e -- --list` reports browser tests only; CI job added |
| T03 export state and lineage | Done | Draft and saved exports are separate actions; assessments store their own evidence and versions; `e2e/export-integrity.spec.ts` reproduces both review findings. **Reopened and re-fixed (R01):** Decision Room preferred the list payload, which carries no evidence reading, so a current draft showed 0 confidence where the saved assessment showed 60. Now reads authoritative product detail; `e2e/decision-room-evidence.spec.ts` and the reviewer's own `e2e/review-regressions.spec.ts` |
| T04 monetary precision | Done | `backend/app/money.py` / `frontend/src/lib/money.ts`; formula versioned to `unit-economics/1.1.0` with 1.0.0 replay preserved; 4000-case cross-language fuzz agrees exactly |
| T05 pagination and export | Done | `backend/app/pagination.py`; server-side search, keyset cursor, `/api/v1/export`, `/api/v1/summary`; 250-product regression. **Reopened and re-fixed (R05, R10):** the export omitted the `evidence` and `compliance_review` kinds entirely; quotes and watches were capped at a flat 200 with no next-page control, and the supplier picker chose only from the loaded page. `e2e/large-workspace.spec.ts` covers 250 quotes, 210 watches, the oldest product, and search scoping |
| T06 concurrency | Done | `insert_unique()` savepoint; `tests/redesign/test_concurrency.py` reproduces the reported 500 against the pre-fix code |
| T07 assessment vs evidence | Done | `latest_assessment` on products/watches, `economics_summary()`; `tests/redesign/test_assessment_visibility.py`, `e2e/assessment-visibility.spec.ts`. Depends on the R01 correction above for the draft/saved agreement it claims |
| T08 input normalisation and copy | Done | Real HTTPS URL validation, monitoring copy corrected; `tests/redesign/test_input_normalisation.py`. **Reopened and re-fixed (R02):** blanket `str_strip_whitespace` reached passwords too, so a legacy account whose password had surrounding spaces was locked out. Normalisation is now per-field and login is tested through the HTTP boundary |
| T09 dependencies | Done | pytest 9.0.3; runtime/dev requirements split and locked; `pip-audit --strict` clean on both locks; runtime install verified free of test packages |
| P01 migrations and deployment config | Done | `backend/migrations/` 0001→0003, `python -m app.migrate {check,upgrade,stamp,check --against}`, `deploy/` templates with placeholders only, `docs/RUNBOOK.md`. **Reopened and re-fixed (R08, R09):** the adoption guide checked a deliberately-behind baseline against today's models and expected stamping 0001 to leave it current; readiness trusted the revision label over a schema missing `audit_events`. The documented sequence is now executed verbatim by `test_migrations.py` |
| P02 password hashing | Done | `backend/app/passwords.py`; self-describing scrypt at an OWASP-listed set; legacy hashes verify and are rehashed on a correct sign-in, now including passwords with leading/trailing whitespace (R02). **Note:** with P03 blocked there is still no self-service recovery, so any future lockout has no user-facing escape |
| P03 account recovery | **Blocked** | Needs an email provider decision. Nothing implemented; `docs/PRIVACY_AND_PERMISSIONS.md` states plainly that recovery and deletion do not exist |
| P04 caches, limits, cleanup | Done | ASGI `BodyLimit` counting streamed bytes; separate sign-in/registration limits per address and per account; `purge_expired()`; central 401 handling and cache clearing in the browser |
| P05 permissions and audit | Partial | `backend/app/permissions.py` matrix with a reviewer role; audit carries actor, workspace, request id and target detail; `docs/PRIVACY_AND_PERMISSIONS.md`. **Not done:** membership and invitations are absent, so a workspace is one person; an owner can still approve their own compliance review. This permission model does not establish qualified independent review |
| P06 backup and restore | Partial | Scripts and `verify_restore.py` present; drill run against a disposable PostgreSQL instance. **Reopened and re-fixed (R06):** the verifier replayed assessments without their stored evidence and reported every evidence-bearing one corrupt, and grouped workspaces by display name so duplicates merged. **Not done:** production drill, scheduling, retention decision, agreed recovery objectives |
| P07 logs, request ids, metrics | Partial | JSON logs with no bodies or secrets, `X-Request-ID` through to audit rows, `/api/v1/ops/metrics`, runbook diagnosis section. **Reopened and re-fixed (R07, R11):** metric labels came from raw paths, so any unauthenticated request minted a permanent label and any workspace owner could read every worker's counters; authenticated request logs recorded `workspace_id: "-"` because the auth dependency ran in another context. Labels are now matched route templates behind an operator token, and identity travels on the request scope. **Not done:** forwarding alerts to an on-call destination |
| E01 source feasibility matrix | Blocked | No provider access has been sought or granted in this pass; nothing is connected and nothing claims to be |
| E02–E05 collectors and snapshots | Planned | Depend on E01. No collector is connected; manual capture (E06) is the current path |
| E06 manual evidence capture | Partial | Dated records with metric, market, source, method and author; truth state fixed server-side to `User input`. **Not done:** file attachments, deliberately deferred until upload, scanning and retention are designed — so the original item is partial, not done-with-a-caveat |
| E07 evidence-quality method | Partial | `evidence-quality/1.0.0` with per-component explanations, a 90-day window, and a cap of 60 on self-reported evidence; `contracts/evidence_cases.json` holds both implementations together. **Not done:** Data Health still lists static unconfigured sources with no attempt or freshness telemetry, which is the other half of the original item |
| N02 classification model | Done | Candidate codes stay candidates; every rule carries publisher, link and effective date |
| N03 compliance-review workflow | Done | Request → decide → supersede, behind `compliance.review`; expiry enforced; an analyst cannot decide their own request. **Reopened and re-fixed (R03, R04):** an approval citing only expired sources, with no classification and no requirements, cleared the gate; and a rejection produced WATCH because the decision received only `compliance_resolved=False`. Approvals must now rest on a source in force and name what they approved; a rejection forces NO-GO without the user restating it |
| D03 gates from real records | Done | The decision endpoint computes coverage, confidence and compliance from stored records; the client cannot set them |
| U02 coherent demo | Done (synthetic only) | The demo GO passes the production method and gates on labelled synthetic evidence and a synthetic reviewer approval; distinct per-product trajectories. **No real product has reached GO**, and none can until a collector supplies evidence above the 60-point self-reported cap |
| N01, D01, D02, D04, U01, U03–U05, M01–M06, C01–C04 | Planned | Not started in this pass |

**Operating rules that every phase must preserve**

1. Every market value has its truth state, unit, market, source or input author, relevant time, and lineage. No synthetic production fallback.
2. Product identity, evidence coverage, scenario economics, compliance review, and overall decision are distinct concepts in both storage and UI.
3. Production evidence gates are computed on the server from authorized records. Client input cannot assert that evidence exists or that compliance was reviewed.
4. Saved assessments remain immutable. New inputs, evidence, classification, or formulas create a new version; they do not rewrite history.
5. Missing or failed observations remain unavailable. They cannot imply zero demand, no competition, or favorable market headroom.
6. Demo fixtures and real workspace records remain separate in persistence, requests, caches, downloads, and reports.
7. Tenant checks cover every resource, job, attachment, export, and notification path, including background processing.
8. Retain the current GO prerequisites unless a separately reviewed, versioned change is justified: adequate coverage, resolved compliance, confidence at least 70, base margin at least 25%, downside margin at least 10%, and overall score at least 75. Prohibited status blocks GO regardless of economics. Validate the meaning and calibration of confidence/overall scores before presenting them as real decision evidence; they are not probabilities by default.

**Phase 0 — repair integrity and establish trustworthy regression checks**

Objective: the existing manual product is reliable before additional data starts flowing through it.

| ID / priority | Deliverable and implementation scope | Dependencies | Acceptance checks | Owner discipline |
| --- | --- | --- | --- | --- |
| T01 / P0 | Establish audit regressions. Replace separate in-memory tenancy apps with clients using one database and different cookie jars. Add an isolated PostgreSQL test job alongside suitable SQLite coverage. | None | Confirm the owner's resource exists, deny another workspace's read/write, and verify owner data remains unchanged. Cover products, jobs/events, decisions, quotes, watches, audit, and subsequent export endpoints. | Backend / QA |
| T02 / P0 | Configure Playwright with its own test directory, disposable application/database, stable fixtures, and CI execution. Keep Vitest discovery separate. | None | `test:e2e -- --list` discovers only browser tests. Capture → confirm → decision → watch, quote entry, demo switching, and auth flows execute successfully; failure artifacts are retained without secrets. | Frontend / QA |
| T03 / P0 | Fix saved/draft export state and historical lineage. Make the export source explicit. Preserve original threshold/formula versions and assessment-specific evidence. | T02 for regression harness | Changing compliance, channel, shipping, stress, or any numeric input cannot accidentally export the prior result as current. Downloading product A while viewing B retains only A's original evidence and versions. Demo and real paths are covered. | Frontend / Backend |
| T04 / P0 | Specify monetary precision and rounding end to end. Use consistent decimal arithmetic or integer scaling; version changed formulas and serialization. Correct detailed currency formatting. | T01; T02 for display checks | USD 8.40 displays as 8.40. The 10.075 reproduction agrees client/server. Negative values, half-cent boundaries, accepted precision limits, decision thresholds, and overflow cases are covered. Old assessments retain their original outputs/version and replay behavior. | Backend / Frontend |
| T05 / P0 | Replace the 200-product cutoff with server-side search and stable pagination. Read details by ID. Add full-workspace export and summary counts independent of loaded pages. Paginate other growing lists. | T01 | A 250+ product workspace can find and open its oldest product. Search runs before pagination. Export includes every authorized record exactly once with consistent references; pagination has a stable sort and tie-breaker. | Backend / Frontend |
| T06 / P0 | Make product/job/decision creation and watch upserts safe under concurrency. Catch errors around the actual flush/transaction. Keep one client idempotency key for retries of one logical submission. | T01 | Repeated concurrent matching submissions converge on one logical result with no unexpected 500. Conflicting reuse returns 409. Ambiguous timeout retry does not duplicate a decision or double-charge research entitlement. Exercise PostgreSQL and supported SQLite behavior. | Backend / Frontend |
| T07 / P1 | Reconcile product summaries with applicable saved assessments. Distinguish evidence status from the user's latest commercial assessment and show its date/scenario. | T03; T05 | A saved prohibited assessment is visible from product, Discover, and watchlist views. Stale evidence and newer drafts are labeled. Historical assessments remain unchanged. An economic failure can be visible alongside insufficient demand evidence. | Product / Frontend / Backend |
| T08 / P1 | Normalize inputs before validation; use real HTTPS URL validation for supplier references. Fix overpromising text and unavailable-state copy. | None | Whitespace-only names fail. `https://` fails as a quote URL. Home copy accurately describes current capability; “No alerts” does not imply monitoring is running. | Backend / Frontend / Product |
| T09 / P0 | Resolve the flagged pytest dependency, separate runtime/dev requirements, and lock Python transitive resolution. Review active frontend dependencies and scan configuration. | None | Dependency scans pass against the chosen patched versions and lock state. Runtime installation excludes test-only packages. The build and test suite pass from the resulting clean dependency environment. | Backend / Platform |

Primary existing files: `backend/app/main.py`, `backend/app/security.py`, `backend/app/economics.py`, `backend/tests/redesign/`, `frontend/src/features/DecisionRoom.tsx`, `frontend/src/features/Products.tsx`, `frontend/src/shared/Workspace.tsx`, `frontend/src/lib/{api,economics,utils}.ts`, `contracts/`, and `.github/workflows/ci.yml`.

**Gate A — trustworthy manual workflow:** T01–T09 pass their acceptance checks. The reviewed defects have focused regressions; scans, build, contract tests, shared-database authorization checks, and essential browser tests pass. A full export can be reconciled with stored records.

The 8 September review is the reason this gate now also requires *cross-feature* evidence, not only per-item checks: T03 and T05 both passed their own acceptance checks while the draft-versus-saved reading disagreed and the export silently omitted two record kinds. Reconciling the export against stored records, and agreement between a current draft and an unchanged saved assessment, are checked directly.

**Phase 1 — make persistence, accounts, and operations ready for customer evidence**

Objective: safely retain and recover real customer work while evolving the data model.

| ID / priority | Deliverable and implementation scope | Dependencies | Acceptance checks | Owner discipline |
| --- | --- | --- | --- | --- |
| P01 / P0 | Add tracked Alembic migrations and document adoption of the existing PostgreSQL schema. Capture service/nginx/deployment templates without secrets. Keep SQLite support explicit. | T01 | Both an empty database and a representative copy of the existing schema reach the target revision. Baseline stamping happens only after schema validation. Deploying requires the expected schema; no accidental empty replacement or destructive migration occurs. | Backend / Platform |
| P02 / P0 | Introduce an upgradeable password-hash format with benchmarked stronger hashing and legacy verification. | T09 | Existing users can sign in and are rehashed on successful authentication. New hashes record algorithm/parameters. No wholesale constant change locks out existing accounts. Verification workload and failure behavior are measured. | Backend |
| P03 / P0 for public accounts | Add verified email ownership, password reset/change, session listing/revocation, and a documented account/workspace deletion process. Define treatment of existing unverified accounts. | P01; P02; email delivery configuration | Reset/verification tokens are hashed, short-lived, single-use, purpose-bound, and rate-limited. Responses avoid account enumeration. Password/security changes revoke appropriate sessions. Tests use a local mail sink; recovery is exercised end to end. | Backend / Frontend / Product |
| P04 / P0 | Clear sensitive client caches on logout/session expiry/workspace changes. Add IP and account-aware auth controls, fair workspace write quotas, body-byte enforcement, and expired-record cleanup. | T01; T06; P01 | Expired sessions cannot leave another user's records visible after account changes. Cross-tab sign-out is handled. Chunked bodies obey the documented size limit. Quotas work across workers; expired sessions/buckets are removed without affecting active windows. | Backend / Frontend |
| P05 / P0 | Make role permissions explicit, add necessary reviewer permissions, and improve audit events. Define privacy, retention, export, source-rights, and deletion behavior for a real pilot. | P01; T01; T05 | A documented permission matrix is enforced server-side. Audit entries include actor, workspace, action, target/version, time, and request/job reference without credentials. Export/download/review actions are audited. Pilot privacy notices match actual storage and third parties. | Backend / Product / Data review |
| P06 / P0 | Establish automated database backups, retention, monitoring, restore drills, and deployment rollback procedures. Extend backup scope when snapshot/object storage arrives. | P01 | Restore into a separate database and run tenant/record/assessment checks against it. Record observed recovery duration and recovery point against agreed targets. A staged release can roll back its application version without corrupting retained data. | Platform |
| P07 / P0 | Add structured logs, request IDs, schema-aware readiness, operational metrics, and alerts. Track failures, latency, DB saturation, quota rejection, and later collector cost/freshness. | P01; T06 | An injected staging failure is identifiable by request/job ID and triggers the configured operational signal. Logs omit secrets and private raw payloads. Health distinguishes liveness from readiness. Runbook includes owner, diagnosis, and recovery steps. | Platform / Backend |

**Gate B — recoverable platform:** a clean deployment and an upgrade from the existing schema both succeed; a restore has been demonstrated; authentication and permissions work against one PostgreSQL database; security scans are current; privacy and retention behavior are documented for the actual pilot. Recovery objectives and operational ownership are recorded, not assumed.

**Phase 2 — build the first real evidence pipeline**

Objective: a supported input produces verified identity where available, real dated observations, traceable source records, and truthful partial results.

| ID / priority | Deliverable and implementation scope | Dependencies | Acceptance checks | Owner discipline |
| --- | --- | --- | --- | --- |
| E01 / P0 | Complete a source feasibility/rights matrix for Amazon identity, demand, Nigerian listings, regulatory material, freight/FX, and later advertising/creator sources. Select the first viable identity and demand sources. | Can start immediately; activation waits for Gate B | For each source record permitted fields, market/window coverage, history, access credentials/approval, storage/display/export rights, retention, quotas, price basis, maintenance owner, and failure fallback. Verify capabilities with current official material and a permitted sample; unknowns remain unknown. | Data integrations / Product |
| E02 / P0 | Add immutable source snapshots, normalized observations, product identifiers/variants, and evidence lineage behind migrations. Respect ADR 001 by extracting only domain tables now needed. | P01; P05; E01 selected-source contract | Snapshot → parser → observation → derived metric → assessment is traceable. Corrections append/supersede; they do not overwrite history. Tenant and data-rights boundaries apply to raw access. Backup/restore includes snapshots. Contract tests reject malformed or unscoped evidence. | Backend / Data integrations |
| E03 / P0 | Replace in-process-only collection with durable jobs, tasks, leases, bounded retries/backoff, idempotent writes, budgets, and explicit partial completion. Choose polling or genuine SSE. | P01; P04; P07; E02 | Restarting one worker does not interrupt another worker's active job. Expired leases are recovered, duplicate deliveries do not duplicate observations, and retries stop at the budget. Users see actual steps and resumable progress. | Backend / Platform |
| E04 / P0 | Connect Amazon identifier resolution through the selected approved source. Store exact identity/variant confidence and supported catalog fields; require confirmation where ambiguous. | E01; E02; E03 | A real supported ASIN resolves permitted product facts with source/time. Unsupported price, reviews, seller count, history, or variant fields remain unavailable. Amazon catalog access is not assumed to expose all desired fields. No arbitrary user URL is fetched; ambiguity remains visible. | Data integrations / Backend / Frontend |
| E05 / P0 | Connect the first approved demand source. Normalize metric meaning, market, time windows, sampling, and coverage; render genuine timelines and evidence drawers. | E01; E02; E03; E04 identity mapping | A real observation reaches the UI with raw-source lineage. Sparse/failed collection leaves chart gaps. Compare aligned windows only. A single snapshot is never presented as a 14-day change or review velocity. No new information means no demand-score change. | Data integrations / Frontend |
| E06 / P0 | Add manual evidence capture: dated source link, notes, author, product/market, and explicit truth state; support reviewer annotation. Introduce private file attachments only with a defined upload/retention design. | E02; P05; P06 | Users can act on a missing-evidence task without waiting for every connector. An uploaded document or typed number does not automatically become an observed fact. If files ship, authorization, MIME/size checks, scanning, safe download, and retention are verified. | Backend / Frontend / Data review |
| E07 / P0 | Make Data Health reflect real attempts, freshness, errors, rights, and coverage. Implement a documented versioned evidence-quality method and actionable blockers. | E02–E06 | Every confidence/quality component can be explained from source records. Missing local coverage reduces eligibility. Failure/freshness can change evidence readiness without being called falling demand. The method is evaluated against reviewed examples and cannot be overridden by client-supplied scores. | Data / Backend / Product |

**Minimum evidence contract to settle in E02**

| Record | Required information and invariants |
| --- | --- |
| Product identity | Canonical ID, source identifiers, market, parent/variant relationships, match method/reasons, user confirmation, source linkage; changing a match is auditable |
| Source snapshot | Source ID/URL or request identity, collected time, source-effective time when available, content hash, private object reference or permitted retained representation, collector version, rights/retention metadata |
| Observation | Product, metric, raw value/unit, market, observation window, observed/fetched times, truth state, snapshot ID, parser version, quality/coverage flags, author where user supplied |
| Derived metric | Input observation IDs, method/formula version, normalization/window rules, calculated time, value/unit, limitations |
| Assessment | Product/market/scenario, exact commercial inputs, input author, referenced quote/review/evidence versions, all gate results, formula/threshold versions, evaluated-at time, saved result |
| Source task/job event | Workspace, request/task ID, idempotency key, status, attempt, lease owner/expiry, error category, timestamps, cost/usage, monotonic event cursor |

Generated/validated API contracts must keep TypeScript and Pydantic aligned. Define time zones, decimal serialization, null semantics, pagination, error envelopes, and schema versions. Preserve legacy assessment replay using its recorded inputs/results; current exports must not silently substitute new rules. Where source rights require raw-data expiry, preserve permitted lineage metadata and explicitly state limits on later replay rather than retaining prohibited copies.

**Gate C — genuine evidence:** demonstrate a real ASIN resolving through approved access, at least one real demand observation flowing through retained provenance, visible failure/freshness behavior, and a saved assessment referencing the correct evidence version. This gate proves data flow, not yet a defensible trend or Nigerian market opportunity. Historical analysis waits for adequate observed or permitted historical coverage.

**Phase 3 — turn evidence into a useful Nigeria-specific decision**

Objective: local context, reviewed import readiness, real sourcing inputs, and commercial assumptions work together.

| ID / priority | Deliverable and implementation scope | Dependencies | Acceptance checks | Owner discipline |
| --- | --- | --- | --- | --- |
| N01 / P0 for local opportunity claims | Collect permitted Nigerian marketplace observations, or start with clearly labeled reviewed manual collection. Match equivalent products and record coverage limits. | E01; E02; E03; E04; E06 | Local prices/listings include date, currency, seller/listing identity, variant relevance, and source. Duplicate listings are handled. Missing or sparse coverage cannot be interpreted as low competition. Global/local comparisons use compatible windows and units. | Data integrations / Market research |
| N02 / P0 | Model classification candidates, official supporting sources, applicable requirements, duty/tax assumptions, effective dates, and reviewer decisions. | E02; E06; P05 | Candidate HS codes remain candidates until reviewed. Each rule has jurisdiction, provenance, effective period, applicability, and review status. No uncited/generated regulatory rate is treated as current law. | Backend / Domain reviewer |
| N03 / P0 | Build the compliance-review workflow: submit evidence, request clarification, approve/reject with scope and expiry, and supersede on new rules. | N02; P05 | Authorized review can resolve the gate; a user's dropdown cannot. Missing, expired, or contradictory reviews block eligibility. Reviewer identity, rationale, documents, and effective scope are preserved. Changes trigger reassessment, retaining prior decisions. | Frontend / Backend / Domain reviewer |
| D01 / P0 | Make quotes actionable: “Use this quote,” explicit validity/expiry, revision history, product specifications, MOQ, currency, Incoterm, delivery inclusion, payment terms, and source. | T04; E02; P01 | Selecting a quote creates a scenario referencing that exact quote version. Later quote edits do not change saved scenarios. Expired quotes and MOQ conflicts are visible. Self-reported supplier claims remain labeled. | Frontend / Backend |
| D02 / P0 | Expand and document landed-cost assumptions: packaging, insurance, clearance, local delivery, payment fees, returns, FX timing, reserves, and cash timing where supported. | D01; N02; T04 | Every included cost has a basis and source/input label. Incoterm/inclusion checks prevent obvious double counting without pretending a quote is complete. Air/sea and FX comparisons use explicit assumptions. Client/server scenarios agree under the new version. | Backend / Frontend / Domain review |
| D03 / P0 | Connect production decision gates to actual demand/local evidence, quality metrics, reviewed compliance, and quote/scenario versions. Show economic feasibility separately from evidence readiness. | E07; N01; N03; D02; T07 | A reviewed fixture can reach GO only when all gates pass. Missing/rejected/expired evidence prevents GO. Real assessments retain contributing records and reasons. Gate boundaries and conflicting evidence are covered; confidence cannot be set from the browser. | Backend / Data / Product |
| D04 / P1 | Add resumable drafts, “copy saved assessment to new draft,” product archive/restore, and quote supersession. Use stable record versions for concurrent edits. | P01; T03; T05; D01 | Navigating away or switching products does not silently destroy entered work. Editing a prior decision produces a new draft. Archived products remain accessible from historical references and complete exports. Concurrent draft edits are detected. | Frontend / Backend |

A user's review request should identify the product/specifications, destination, evidence, intended use, and unresolved question. It should not force a reviewer to reconstruct context from unrelated screens. Regulatory review requires a suitably qualified human owner; software acceptance alone cannot establish classification correctness.

**Gate D — complete real investigation:** a real product can move from capture through identity, available demand and local evidence, supplier quote, cost scenario, and a completed review or actionable review request to a versioned decision. The app provides a usable workflow for every blocker. If sufficient coverage or review is absent, the result remains insufficient evidence with explicit next work.

**Phase 4 — make the complete journey understandable and shareable**

Objective: a new user understands what to do, why the decision exists, and what their report actually says.

| ID / priority | Deliverable and implementation scope | Dependencies | Acceptance checks | Owner discipline |
| --- | --- | --- | --- | --- |
| U01 / P0 for pilot usability | Add guided first investigation and a persisted progress checklist: destination context, capture, confirmation, evidence, quote, freight/costs, readiness review, decision. | E06; D01–D04; P03 | Completion reflects stored state, not page visits. Each blocked step links to an action. Nigeria is clearly the supported destination. Refreshing/signing in on another device resumes saved work. | Product / Frontend |
| U02 / P1 | Add a coherent GO demo alongside WATCH, NO-GO, and insufficient-evidence examples. Correct mismatched fixture timelines and generic real-product imagery. | T03; T04; D03 | The GO example passes the same decision functions using explicit synthetic evidence/review fixtures; no production gate is relaxed. All screens/downloads retain demo labeling. Product headlines match fixture histories and demo never writes real evidence. | Product / Frontend / QA |
| U03 / P0 for report release | Generate a professional opportunity report from the immutable assessment. Provide printable/PDF output plus a machine-readable export. | T03; T05; D03; P05 | Report includes summary, verdict/gates, demand/local evidence, quote comparison, landed costs, scenarios, compliance status, risks/actions, timestamps, and sources. Missing sections explain why. Changing the current UI cannot change a historical report. Source rights and tenant permissions filter content. | Backend / Frontend / Product |
| U04 / P1 | Review keyboard flow, focus, labels/errors, contrast, chart alternatives, mobile ergonomics, empty/loading/error states, and reduced motion. Split heavy routes/charts and improve verdict visibility on mobile. | T02; U01; U03 | Essential workflows are usable by keyboard and on a narrow viewport. Dialog focus returns correctly. Tables provide chart alternatives. Record performance baselines on a stated device/network and verify route splitting improves the relevant load; no fabricated performance claims. | Frontend / QA |
| U05 / P1 | Consolidate capability messaging and information architecture. Keep unavailable features clearly labeled and out of the main task path. Document actual capabilities and known limitations. | E07; U01 | Home, onboarding, Data Health, navigation, demo, report, and README agree. “Real signals” appears only when the described signals are actually connected. Watchlist-only behavior is named accordingly. Historical documents remain clearly superseded. | Product / Frontend |

Optional sharing after U03: scoped, revocable, expiring report links with access logging and export-rights filtering. Public links must never expose raw private evidence, provider credentials, or unrelated workspace records. Downloadable reports can ship before hosted sharing.

**Gate E — controlled pilot:** at least five representative pilot users complete a real investigation without engineering intervention, using the planned human-review workflow where needed. They can explain the decision, distinguish evidence from assumptions, resume their work, and obtain the correct report. The synthetic GO example demonstrates success; no real GO is required unless its evidence and review support it. Record usability failures and fix blockers before increasing access.

**Phase 5 — monitoring, sales-driver analysis, and proactive discovery**

Objective: evidence updates create useful reasons to return, and TrendSell starts suggesting investigations rather than only storing supplied ideas.

| ID / priority | Deliverable and implementation scope | Dependencies | Acceptance checks | Owner discipline |
| --- | --- | --- | --- | --- |
| M01 / P1 | Enable scheduled Watchtower collection with per-source cadence, workspace limits, budgets, durable ownership, deduplication, and pause controls. | E03; E07; D03; P07 | A scheduler restart recovers due work without duplicating it. Schedules obey quotas and source limits. Last/next run and source failures are visible. Monitoring cannot appear active before collection is actually scheduled. | Backend / Platform |
| M02 / P1 | Implement material-change evaluation and persistent in-app alerts; add opted-in email delivery with separate delivery state. | M01; P03; D03 | A qualifying fixture update creates one alert with before/after values, source/time, rule, and decision impact. No new evidence produces no alert. Delivery failures retry without duplicating the alert; source failure creates a health notice, not a false demand decline. | Backend / Frontend |
| M03 / P1 strategic differentiator | Build an evidence-backed “What is driving interest?” timeline across search, marketplace/review activity, public advertising, creator/video activity, and promotions where sources permit. Add connected first-party attribution only when authorized data supports it. | E01 review for every new source; E02; E04; E05; E07; D03 | Every statement links to dated observations/derived metrics. Counts, direction, windows, product relevance, and coverage are inspectable. Cross-posts/reposts and duplicate advertisers are considered. Sparse evidence produces an explicit limitation. No inferred sales, spend, ROAS, or causal claims from public activity alone. | Data integrations / Data / Product |
| M04 / P1 after adequate coverage | Activate Market Gaps with a transparent, versioned comparison of global evidence and Nigerian demand/supply/readiness. | N01; E07; D03; enough comparable history | Candidates can be plotted and traced to the underlying comparable evidence. Minimum coverage is enforced; missing listings never increase headroom. Rankings have reviewed examples and explain changes. Users can open a suggested candidate as an investigation. | Data / Backend / Frontend |
| M05 / P2 | Extend supplier intelligence beyond manual quotes: permitted candidate discovery, specification matching, verification evidence, quote normalization, samples, and reliability history. | E01 for supplier sources; D01; E06; P05 | Supplier identity and claims have provenance and verification status. Price differences are explained by specs, quantities, currency, terms, and date before flagging anomalies. Reliability uses actual documented history; missing evidence is not a positive rating. | Data integrations / Sourcing / Product |
| M06 / P2 | Add RFQ response tracking and, only when configured, user-authorized sending with drafts, recipients, send status, and response/version history. | M05; P03; P05 | Users review what will be sent and to whom. Sending is idempotent/audited and respects permissions. A retry cannot send duplicate messages. Imported responses retain original quote details and remain unverified until reviewed. | Backend / Frontend / Product |

Sales-driver scope is explicit: TikTok/creator activity, Amazon advertising, Meta ads, Shopify/store activity, search, and marketplace promotions are desired evidence categories, not promised integrations. For each, record what is public, what requires the customer's authorized first-party connection, what can be retained/displayed, and what cannot be measured. The presence of an app on a store or a persistent ad does not establish its contribution to sales.

**Gate F — reliable recurring value:** a real monitored product produces a traceable material-change notification; retries/restarts/source failures behave correctly; users can pause monitoring and understand consumption. Market Gaps and driver analysis have their own coverage/rights gates and are enabled only when their acceptance checks pass.

**Phase 6 — commercial readiness and public release**

Objective: the product's audience, price, operating cost, claims, and support obligations match what it actually delivers.

| ID / priority | Deliverable and implementation scope | Dependencies | Acceptance checks | Owner discipline |
| --- | --- | --- | --- | --- |
| C01 / P1 | Define the initial customer and use case through the controlled pilot. Measure successful investigations, time to a usable assessment, unresolved blockers, report use, and return behavior. | Gate E | Findings distinguish importer/reseller/research use cases and record why users do or do not return. Metrics measure completed useful work rather than clicks. Product priorities are updated using observed feedback. | Product |
| C02 / P1 | Measure source/research/storage/review/notification costs and design transparent entitlements: investigations, monitoring, reports, team access, and optional human-review fees. | E03; P07; C01; source commercial terms | Document variable cost per relevant action and a conservative budget ceiling. Failed/retried work has a clear credit policy. Prices and quotas describe shipped capabilities; no numerical pricing is assumed by this plan. | Product / Operations |
| C03 / P1 for paid access | Add billing only after pricing/entitlements are defined, plus owner-managed invitations and enforced analyst/viewer/reviewer permissions for any team offer. | C02; P03; P05 | Billing events/webhooks are verified and idempotent; subscription/credit changes cannot bypass tenant controls. Cancellation, refunds, export rights, and credit exhaustion are clear. Team members cannot exceed server-enforced permissions. | Backend / Frontend / Product |
| C04 / P0 for public release | Complete release readiness: privacy/terms, current source-rights review, support ownership, accessibility evidence, dependency/secret scans, restore/rollback drill, capacity/budget checks, and post-deploy smoke procedure. | Gates A–E; Gate F for advertised monitoring; C02/C03 for paid offers | Every promised capability maps to a passed acceptance check. Known residual issues have severity, owner, mitigation, and disposition. Staging release evidence is reproducible, recovery is demonstrated, and launch messaging contains no unsupported claims. | Product / Platform / QA |

**Release process and migration safeguards**

1. Build a versioned artifact and run applicable unit, shared-contract, integration, browser, dependency, and secret checks. Scan reachable history appropriately and redact findings; the old regex-only current-tree scan is insufficient as a long-term control.
2. Validate the migration against both a fresh database and a sanitized copy of the current schema. Prefer additive changes with explicit backfills, verification counts, and rollback-compatible application behavior. Do not treat `create_all()` as a migration system.
3. Back up the target data and confirm a known restore path. Assess retention/rights implications when adding snapshot storage, quote files, and exports.
4. Deploy to staging, migrate, and execute a complete isolated investigation/report workflow. Exercise source unavailability, review rejection/expiry, permission denial, and interrupted job recovery.
5. Prepare the exact production release, affected records, expected behavior, validation evidence, rollback target, and operational owner for the final release decision under the applicable deployment policy.
6. After deployment, verify health/readiness, login/session handling, representative reads, source/job health, and a designated smoke workspace. Observe error rates, latency, quotas, and costs; use documented rollback criteria rather than ad hoc repair.

No raw production customer data should be copied to an unrestricted development/test environment. Historical assessments must survive schema/formula evolution; store a replay specification or compatible versioned implementation and retain saved outputs for each released formula version.

**Proposed first ten implementation changes**

These are reviewable change boundaries, not an instruction to combine all work into ten oversized PRs. Split further if a change is difficult to review.

| Order | Change | Plan IDs | Required proof |
| --- | --- | --- | --- |
| 1 | Repair shared-database auth tests and establish PostgreSQL coverage | T01 | Both workspaces coexist; forbidden operations fail without changing owner records |
| 2 | Isolate Playwright discovery and add essential browser fixtures | T02 | Browser tests are discoverable and run against disposable state |
| 3 | Correct current/saved exports and historical provenance | T03 | Stale-input and wrong-product reproductions are fixed in browser tests |
| 4 | Version decimal arithmetic and detailed currency formatting | T04 | Shared boundary cases match and USD cents are visible |
| 5 | Paginate/search correctly and produce complete exports/counts | T05 | Oldest record in a 250+ product workspace remains accessible/exportable |
| 6 | Fix concurrent creation and preserve retry keys | T06 | Parallel and timeout-retry cases converge safely on PostgreSQL |
| 7 | Clarify latest assessment/evidence status; tighten validation and copy | T07; T08 | Saved prohibition is visible; malformed inputs fail; unavailable monitoring is explicit |
| 8 | Patch and separate dependencies; reproduce clean installs | T09 | Scans and appropriate checks pass using runtime/dev dependency sets |
| 9 | Establish migration baseline and tracked deployment configuration | P01 | Existing and empty schemas migrate without data loss |
| 10 | Begin account hardening and recovery in separate focused changes | P02–P04 | Legacy login, reset/revocation, tenant cache clearing, and quota/body boundaries verified |

E01 source-access research can start during these changes. Do not let external approval delays prevent completing the integrity/operations work; equally, do not enable a collector before evidence storage, rights, durable jobs, and budgets are ready.

**Dependency and decision register**

| Decision/input | Needed before | What must be recorded |
| --- | --- | --- |
| Identity and demand provider access | E04/E05 activation | Actual approved coverage, sample payload, storage/display/export rights, cost and limits |
| Nigerian collection method | N01 | Allowed marketplace/manual method, comparable product definition, sampling limits, freshness target |
| Compliance reviewer | N03; any reviewed GO | Qualified accountable reviewer, supported categories, turnaround, evidence requirements, expiry/appeal process |
| Decimal/replay design | T04 | Accepted precision, rounding points, serialization, supported ranges, historical replay/version behavior |
| Queue/snapshot infrastructure | E02/E03 | Hosting, durability, backup, retention, cost ceilings, operational ownership; keep the pilot architecture proportionate |
| Account email delivery | P03 | Provider/configuration, verified sending identity, local test sink, abuse controls, deliverability monitoring |
| Recovery objectives | P06 | Agreed recovery point/time targets, storage location, retention, restore-test evidence |
| Retention/privacy/export policy | E02/E06/U03 | Treatment of customer data, licensed source payloads, deletion, private files, historical lineage, and report rights |
| Pricing and audience | C02/C03 | Observed pilot use, unit costs, included quotas, failed-job credit policy, human-review fees, support scope |

**Traceability: every reviewed concern has a place**

| Input concern | Work items |
| --- | --- |
| Repository review 1–2: stale export and wrong historical evidence | T03; E02; U03 |
| Review 3: 200-product cutoff and incomplete export | T05 |
| Review 4: request races and ineffective retry keys | T06; E03 |
| Review 5–6: calculation parity and missing cents | T04; D02 |
| Review 7: assessment/product contradiction | T07; D03 |
| Review 8: vulnerable dependency/runtime test packages | T09 |
| Review 9: hash strength and migration format | P02 |
| Review 10: account lifecycle, cache expiry, limits, cleanup | P03; P04; C03 |
| Review 11–12: body-size and input-validation defects | P04; T08 |
| Review 13–14: tenancy fixtures and broken browser coverage | T01; T02 |
| Review 15–16: migrations/recovery and multi-worker jobs | P01; P06; P07; E03 |
| Analyst 1: no live evidence | E01–E07 |
| Analyst 2: missing sales-driver analysis | M03; source feasibility in E01 |
| Analyst 3: non-operational Market Gaps | N01; E07; M04 |
| Analyst 4: unverified X-Ray identity | E04; E02 |
| Analyst 5: manual supplier intelligence | D01; M05; M06 |
| Analyst 6: compliance cannot clear a gate | N02; N03; D03 |
| Analyst 7: watchlist without monitoring | E03; M01; M02 |
| Analyst 8: no complete GO example | U02 |
| Analyst 9: no professional opportunity report | T03; U03 |
| Analyst 10: missing guided onboarding | U01; D04 |
| Analyst 11: overpromising copy | T08; U05 |
| Analyst 12: absent pricing/commercial model | C01–C04 |
| Additional UX/maintenance concerns | D04; U04; U05; focused module cleanup during the relevant changes |

**Deferred deliberately**

- Broad multi-country expansion, image/video identity resolution, and store/app intelligence beyond permitted evidence categories until the core corridor and identity model work.
- Automatic purchasing, inventory ordering, ad spending, or unsolicited supplier contact. Those require separate product workflows, permissions, limits, and explicit user intent.
- A comprehensive relational rewrite of every pilot record at once. Follow [ADR 001](ADR-001-record-storage.md): introduce tables when real workflows need their constraints and querying.
- AI-written market narratives before an evidence-linked statement contract exists. A narrative must be reproducible from permitted facts and distinguish inference; it cannot fill empty evidence with plausible prose.
- Large visual redesigns before the integrity, data, and workflow gaps are closed. Improve specific usability and accessibility problems as part of their feature work.

**Completion record**

When implementation begins, append dated milestone evidence here or link to issues/PRs. Include commit/release, item IDs, test results, migration/restore evidence where relevant, source-access status, residual risks, and the next enabled dependency. Do not mark the plan complete because the interface is populated or because the original 159 tests still pass.

| Milestone | Status | Evidence |
| --- | --- | --- |
| Plan saved and linked | Done — 2026-09-08 | This document, README link, and supersession notices |
| Gate A: trustworthy manual workflow | ~~Done — 2026-09-08~~ **In review — 2026-09-09** | Claimed done on 8 September; the independent review the same day declined to sign off, because an evidence-bearing draft disagreed with its own saved assessment (R01) and the full export omitted evidence and compliance reviews (R05) — two of Gate A's own acceptance criteria. R01–R11 are corrected and verified (see [CLAUDE_HANDOFF.md](CLAUDE_HANDOFF.md)); the gate stays **in review** until the re-review signs off. Current: **447 backend tests collected — 433 executed on SQLite (14 skipped, requiring PostgreSQL) and 447 executed on PostgreSQL 16.4**, 141 frontend tests, 35 browser tests, TypeScript, production build, dependency scans. Each reviewed defect has a regression that fails against the pre-fix code. |
| Gate B: recoverable platform | Partial — 2026-09-09 | Clean deployment and adoption of an existing schema both verified, the latter now against a disposable clone following the corrected runbook verbatim; a restore drill was demonstrated against a disposable PostgreSQL instance and the replay verifier repaired (R06); permissions and authentication work against one PostgreSQL database; scans current; privacy and retention documented. **Outstanding:** account recovery (P03, blocked on an email provider), a production restore drill, scheduled backups, and agreed recovery objectives. |
| Gate C: genuine evidence | Planned | — |
| Gate D: complete real investigation | Planned | — |
| Gate E: controlled pilot | Planned | — |
| Gate F: reliable recurring value | Planned | — |
| Public/paid release readiness | Planned | — |
