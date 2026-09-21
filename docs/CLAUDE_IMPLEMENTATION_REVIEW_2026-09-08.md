# Independent review of Claude's implementation

Reviewed: 2026-09-08. Branch: `impl/evidence-platform-phase0`. Commit: `83a4a0d`.
Comparison: implementation after the saved audit/plan commit `88e7c4c`.

**Assessment: substantial engineering progress, with material integration regressions still requiring correction. I would not sign off on deployment or on Gate A being complete at this commit. The live evidence engine remains unimplemented.**

Claude made 15 implementation/documentation commits affecting 87 files (9,398 insertions and 239 deletions). The work is considerably more than a visual update: it repairs original defects, adds meaningful tests, introduces migration/security/recovery foundations, and creates a manual evidence and import-review workflow. However, some later additions bypass or invalidate earlier fixes, and the current test suite does not catch those interactions.

This review inspected the repository and ran isolated tests and reproductions. It did not deploy changes, inspect customer records, contact providers, or establish that the deployed application matches this branch. The application source was left unchanged; this report and accompanying review artifacts are the review deliverables.

## What Claude achieved

| Area | Actual implementation |
| --- | --- |
| Original integrity fixes | Explicit saved versus draft exports; saved assessment evidence snapshots; shared decimal arithmetic and formula-version handling; detailed currency formatting; concurrent keyed creation; latest saved assessment displayed beside product evidence status. |
| Search and growing datasets | Server-side product search, keyset pagination, direct product reads, database summary counts, and a streamed workspace export. There are remaining coverage gaps described below. |
| Meaningful verification | Shared-database tenant fixtures, PostgreSQL test execution, concurrency and formula regressions, separate Vitest/Playwright discovery, and 25 real browser tests with an isolated API/database. CI configuration includes these jobs. Remote CI execution was not independently checked. |
| Security | Upgradeable scrypt hashes with a legacy verification path; separate authentication limits; streamed body-size enforcement; expired session/rate-bucket cleanup; browser cache clearing; named permissions; richer audit events. Password input handling has a regression. |
| Operations | Three tracked Alembic revisions, migration commands, deployment templates, a runbook, backup/restore scripts, assessment replay verification, request IDs, structured logging, and worker metrics. Several integration and operational gaps remain. |
| Manual evidence | Dated records with source, market, metric, method, and author; server-assigned `User input` truth state; evidence-quality breakdown and a 60-point manual-only cap. No collector is presented as connected. |
| Import readiness | Request, approve/reject/request-information, supersede, and expire reviews; source references and classification fields; server-side review permission checks. This is a manual workflow, not verified regulatory intelligence. |
| Decisions and demo | Saved real-workspace decisions read stored evidence and review state on the server. A synthetic GO example now exists alongside the other outcomes. |
| Dependencies and documentation | Runtime/dev dependency separation, pinned locks, pytest upgrade, capability corrections, status entries in the action plan, and privacy/permission documentation. |

## Independently verified checks

| Check | Result |
| --- | --- |
| Backend suite, SQLite | **367 passed, 11 skipped**; skipped cases require PostgreSQL. |
| Backend suite, PostgreSQL 16.4 | **378 passed**, using temporary schemas in the disposable `trendsell-test-db` container. |
| Frontend tests | **132 passed**. |
| TypeScript | **Passed**, including the browser-test configuration. |
| Production frontend build | **Passed**. |
| Claude's browser suite | **25 passed** in Chromium. |
| Python locked-dependency advisory scan | **No known vulnerabilities found** across both locks. |
| Frontend dependency advisory scan | **0 reported vulnerabilities**. |
| Additional independent browser regression | **Failed three assertions**: displayed/draft confidence, evidence count, and decision disagree with the saved assessment. |
| Additional isolated API/recovery reproductions | Confirmed the password, compliance, export, recovery, metrics, readiness, and migration-guide issues below. |

Local socket restrictions prevented the first sandboxed test runs from completing; successful reruns used approved execution outside that sandbox with disposable data. Passing dependency scans do not establish application security. No new production backup/restore drill, mobile/accessibility audit, or provider/data-rights validation was performed during this review.

The action plan's statement of “378 backend tests on SQLite and PostgreSQL” should distinguish collected cases from executed cases: SQLite executes 367; PostgreSQL executes all 378.

## Findings requiring correction

### R01 — P1: Decision Room ignores recorded evidence for products already in its loaded list

Locations: `frontend/src/features/DecisionRoom.tsx:23`, `frontend/src/features/DecisionRoom.tsx:45`, `frontend/src/features/DecisionRoom.tsx:63`, `backend/app/main.py:387`.

The product list returns stored product payloads without the computed `evidence_quality` or current evidence records. Decision Room prefers that list object, and enables its detail request only when the product is absent from the list. Therefore ordinary, recently created products never receive the evidence reading that the browser calculator expects. Draft exports also retain the hard-coded `no-observations/1` version.

**Browser reproduction:** create and confirm one product, add four current manual demand/local records, enter viable economics, export the draft, then save and export the assessment without changing inputs.

| Reading | Draft/current screen | Saved server assessment |
| --- | --- | --- |
| Confidence | 0 | 60 |
| Evidence records in export | 0 | 4 |
| Decision | INSUFFICIENT EVIDENCE | WATCH |

The current verdict remained at 0 even after the save. The product-detail API independently returned 60. This undermines the primary evidence-to-decision workflow and the export-integrity completion claim.

**Correction:** make Decision Room consume authoritative product evidence/review detail regardless of which list pages are loaded. Refresh that reading when evidence/reviews change. Export the matching evidence snapshot and method version. Add browser coverage for recorded evidence, approved/rejected review state, and unchanged-input draft/save agreement.

### R02 — P1: Password normalization locks out valid existing accounts

Locations: `backend/app/main.py:39`, `backend/app/main.py:44`, `backend/app/main.py:362`.

`Credentials` inherits `str_strip_whitespace=True`, so leading/trailing whitespace is removed from passwords before verification. The previous release hashed those characters as entered. The new legacy hash verifier works directly, but the login endpoint passes it a different password.

**Reproduction:** seed a legacy hash for a sufficiently long password with one surrounding space on each side. Direct hash verification returns true; signing in with that exact password returns **401**.

**Correction:** normalize email/display names at their own fields and preserve passwords exactly. Test migration through the HTTP login boundary, including whitespace and supported Unicode, rather than only the hash helper. Recovery is currently absent, making this regression harder for affected users to escape.

### R03 — P1: Expired regulatory evidence can clear the compliance gate

Locations: `backend/app/compliance.py:48`, `backend/app/compliance.py:70`, `backend/app/compliance.py:89`, `backend/app/main.py:514`.

Approval requires a nonempty source list, but source effective dates are only regex-checked and are not used to decide whether approval is current. The gate checks the newly assigned review expiry. Approval also accepts an empty confirmed HS code and empty requirements.

**Reproduction:** approve a review with a source effective from `2010-01-01` to `2011-01-01`, no confirmed code, and no requirements. The request succeeds and `gate.resolved` is **true** in September 2026.

**Correction:** validate real dates, date ordering, applicability, and the reviewed classification. Define how multiple sources determine validity; do not treat expired or not-yet-effective support as current. Require an explicit reviewed determination when no additional requirements apply. Bound/reassess the approval when applicable support expires. Tests should exercise the resulting decision gate, not just storage of the dates.

### R04 — P1: A rejected import review produces WATCH instead of enforcing the rejection

Locations: `backend/app/compliance.py:115`, `backend/app/main.py:419`, `backend/app/main.py:615`, `backend/app/economics.py:139`.

The review gate explicitly says “A reviewer rejected this product for import. Do not proceed.” But the economic decision receives only `compliance_resolved=False`; it does not receive that rejection. Only the user's `inputs.compliance == 'prohibited'` forces NO-GO.

**Reproduction:** add adequate manual coverage, reject the import review, and save otherwise viable economics with the default unresolved dropdown. The saved record reports **WATCH**, confidence **60**, and a rejected compliance gate saying not to proceed.

**Correction:** carry the authoritative rejection/prohibition outcome into the versioned decision gates and display it consistently. If some review rejections mean insufficient documentation rather than rejection for import, model those separately. Do not require users to repeat a reviewer decision in a dropdown. Preserve historical assessment behavior when changing gate versions.

### R05 — P1: “Export workspace records” omits the new evidence and review records

Locations: `backend/app/main.py:34`, `backend/app/main.py:706`.

`EXPORT_KINDS` enumerates only products, jobs, decisions, quotes, and watches. The later `evidence` and `compliance_review` kinds were never added. Export counts therefore conceal the omission, and `compliance_review_id` references cannot be resolved from the export.

**Reproduction:** the database contains four evidence records and two compliance reviews; the workspace export has neither collection. Saved decisions happen to embed evidence snapshots, but evidence that has not been saved into an assessment is absent, and review history/supporting sources are still omitted.

**Correction:** version/document the export contract, include all authorized research records and their references, and reconcile exported data with stored data. Test new kinds, unassessed evidence, superseded reviews, and a foreign workspace. Gate A's full-export acceptance criterion currently fails.

### R06 — P1: The restore verifier reports valid evidence-based assessments as corrupt

Locations: `scripts/verify_restore.py:44`, `scripts/verify_restore.py:60`.

The verifier calls `calculate(inputs, formula_version=...)` without the assessment's stored evidence reading. That defaults confidence/coverage to zero, even though new saved decisions use `evidence_quality`.

**Reproduction:** create two normal assessments with manual evidence and inspect the unchanged database. Both fail replay on **decision, blockers, and confidence**. A restore is unnecessary to trigger the false failure.

The same script groups workspace counts by display name. Separate workspaces with the same name are combined, weakening per-tenant recovery reconciliation.

**Correction:** replay historical inputs and evidence under their recorded formula, threshold, and evidence-method versions; retain a valid path for legacy no-evidence records. Reconcile workspaces by stable ID. Repeat the disposable restore drill with current evidence/review records, duplicate workspace names, and multiple historical versions before claiming recovery coverage.

### R07 — P1: Operational metrics retain arbitrary request paths and expose them across workspaces

Locations: `backend/app/observability.py:63`, `backend/app/observability.py:84`, `backend/app/main.py:764`.

Route labels are produced by replacing only long hexadecimal-looking segments. Other client-controlled segments, including arbitrary unknown API paths, become dictionary keys retained for the worker's lifetime. The metrics endpoint returns all worker counters to any workspace owner; workspace administration is not service operations administration.

**Reproduction:** request a path containing a test marker from one workspace; another workspace owner's metrics response contains that exact marker. Twenty distinct unknown paths produce twenty additional persistent metric labels. The paths do not require authentication. No load or exhaustion attack was performed.

**Impact:** an unbounded memory-growth surface and cross-workspace disclosure of request labels/aggregate activity. This reproduction does not show disclosure of database record contents.

**Correction:** derive labels from matched route templates, collapse unmatched requests to a bounded label, and impose cardinality bounds. Restrict global metrics to a distinct operator permission/internal surface, or expose genuinely tenant-scoped metrics. Test unauthorized route generation and a separate tenant.

### R08 — P2: The existing-installation migration guide stops at the wrong schema

Locations: `docs/RUNBOOK.md:35`, `docs/RUNBOOK.md:42`.

The guide expects a baseline installation to match today's models before stamping, then expects stamping `0001_pilot_baseline` to leave it current. Today's head is `0003_audit_detail`; the baseline correctly lacks the later audit and rate-bucket columns.

**Reproduction:** recreate the unstamped baseline. The initial check reports `matches_models=False`. Baseline stamping succeeds, but the following check reports `up_to_date=False`, at revision 0001 rather than 0003. This contradicts two documented expectations.

**Correction:** distinguish baseline-adoption validation from current-model validation, explicitly apply subsequent upgrades, and verify the resulting schema/readiness. Test the documented sequence against a disposable clone of the pre-migration schema. Do not mark P01's deployment documentation complete until it matches the supported upgrade path.

### R09 — P2: Readiness checks the revision label but misses a broken schema

Location: `backend/app/main.py:308`.

**Reproduction:** migrate a disposable database to head, remove `audit_events`, and request `/api/ready`. It returns **200 ready** because `SELECT 1` succeeds and the revision row still says 0003. Normal audited writes would fail.

**Correction:** add an appropriate actual-schema compatibility check, at startup/deployment and/or cached readiness, without making every probe perform unnecessarily expensive inspection. Test missing required tables/columns in addition to wrong revision labels. This matters particularly to recovery validation.

### R10 — P2: Growing lists and product selectors remain limited by loaded pages

Locations: `frontend/src/shared/Workspace.tsx:48`, `frontend/src/shared/Workspace.tsx:60`, `frontend/src/features/Operations.tsx:25`, `frontend/src/features/Operations.tsx:33`, `frontend/src/features/Operations.tsx:35`, `frontend/src/features/Products.tsx:20`.

Source inspection confirms quotes and watches still fetch only the first 200 records and provide no next-page control. Their total badges can exceed the records a user can access. Supplier product selection uses only the currently loaded product list, initially 50. Discover's search is stored globally and is not cleared on navigation, so it also changes product choices elsewhere.

**Correction:** use independent paged/searchable queries for growing lists and product pickers. Scope Discover filters to Discover. Test 250+ quotes/watches, an older product in the quote picker, and navigating after an unmatched search. The original oldest-product direct-read problem is repaired, but the broader T05 acceptance scope is incomplete. These UI boundary cases were identified by code inspection, not a new large-dataset browser run.

### R11 — P2: Authenticated structured request logs lose user/workspace identity

Locations: `backend/app/main.py:146`, `backend/app/main.py:179`, `backend/app/observability.py:25`.

The synchronous authentication dependency sets context variables in its execution context; the outer middleware subsequently logs from another context. During the real browser run, authenticated product, evidence, quote, and decision requests consistently logged `workspace_id: "-"` and `user_id: "-"`.

**Correction:** pass authenticated identity through a request-scoped mechanism visible to the logging middleware. Capture actual emitted logs in tests and verify actor/workspace/request correlation while excluding secrets. Audit rows already receive actor/workspace explicitly; this finding concerns the request logs and should not be read as claiming all audit identity is absent.

## Completion claims to revise

| Claim in action plan | Review disposition |
| --- | --- |
| Gate A / phase 0 done | Reopen for integration regressions. Existing tests pass, but current evidence-bearing drafts and full exports fail acceptance. |
| T01, T02, T04, T06, T09 | Substantial implementations with passing relevant regression suites. No new blocker identified in their central changes during this review. |
| T03, T05, T07, T08 | Earlier fixes exist; current integration coverage is incomplete, including stale evidence views, export scope, remaining list limits, and password normalization. |
| P01/P02 done | Require corrections to the upgrade guide/readiness and password compatibility before sign-off. |
| P04 | Implemented controls and passing limit/cache tests. This is not a claim that every future endpoint has been audited. |
| P05 | Named backend permissions and audit are implemented. Membership/invitations remain absent, as the documentation acknowledges. Owner accounts can approve their own reviews; qualified independent review has not been established by this permission model. |
| P06 partial | Correctly described as partial; the verifier also needs repair for the new assessment format before its drill is persuasive. |
| P07 done | Partial: structured-log identity and metrics need correction; external operational alerts remain explicitly absent. |
| E06 done (files deferred) | Usable manual capture exists. Attachments are deferred, so the full original item is partial. |
| E07 done | Quality method implemented; Data Health still returns static unconfigured sources with no attempts/freshness telemetry. Full original scope is partial. |
| N02/N03/D03 done | Important workflow implemented; current approval/rejection handling and frontend/server disagreement require review before completion. |
| U02 done | Synthetic GO example implemented and its browser test passes. No real product GO has been demonstrated. |

The repository contains updated status tables, but **no `docs/CLAUDE_HANDOFF.md`** was found. That requested handoff should summarize final commits, item-by-item acceptance evidence, residual defects, and exact external dependencies.

## What remains from the original product vision

- Authorized Amazon product resolution and collected demand evidence.
- A source feasibility/data-rights matrix based on current official documentation and permitted samples.
- Durable collection jobs, immutable source snapshots, retries, leases, and collector cost controls.
- Nigerian marketplace observations, local comparisons, and an operational Market Gaps workflow.
- Sales-driver association/attribution signals with appropriate uncertainty.
- Maintained, applicable regulatory evidence and a usable qualified-review operating process.
- Scheduled Watchtower collection, material-change alerts, and notifications.
- Supplier discovery/verification and richer quote intelligence.
- A professional opportunity report, guided onboarding, and a commercial/pricing model.
- Account recovery and ownership verification, membership operations, agreed retention/deletion behavior, scheduled production backups, demonstrated recovery objectives, and operational alert delivery.

Manual evidence and review are valuable progress, but all permitted production evidence is currently self-reported and capped at 60, below the 70-confidence GO requirement. A real end-to-end actionable GO remains unavailable. The application is a stronger manual investigation tool and demonstration; the evidence engine is still unconnected.

## Recommended next assignment for Claude

1. Address R01–R07 first with reproductions that fail on this commit and pass after the fix. Preserve legacy passwords and historical assessments; version changes to decision behavior explicitly.
2. Address R08–R11, then rerun the existing suites plus the new cross-feature cases. Repeat the disposable PostgreSQL restore drill using current evidence/review data and follow the corrected upgrade instructions verbatim.
3. Correct `ACTION_PLAN.md` statuses and write `docs/CLAUDE_HANDOFF.md`. Distinguish implemented, locally verified, externally blocked, and not started.
4. Continue useful work that does not need provider credentials: the public-source feasibility research, recovery flow against a local mail sink, guided onboarding, report generation from available records, and appropriately scoped collection infrastructure after source contracts are defined.
5. Name exact external decisions needed for activation: provider/account access, permitted use, email delivery, qualified compliance reviewers, recovery objectives, retention, and alert ownership. Separate these from local implementation work so one missing credential does not stop unrelated tasks.

This pass did not exhaust the work Claude could do without live provider access. For example, P03 explicitly calls for tests against a local mail sink, and E01 says feasibility work can start immediately. Production delivery/activation can remain blocked while those concrete implementations and research artifacts advance. Continue on the implementation branch and request final independent review before deployment.

## Reproduction artifacts

- [Backend reproduction script](review-artifacts/2026-09-08/backend_reproductions.py): creates temporary databases, exercises the reported cases, and deletes its temporary database directory. Run from the repository with `.venv/bin/python docs/review-artifacts/2026-09-08/backend_reproductions.py`. Its fixed September 8 evidence date reproduces this review; update the fixture date for runs outside the evidence window.
- [Backend results](review-artifacts/2026-09-08/backend_results.json): recorded independent outputs, with disposable IDs only.
- [Browser regression specimen](review-artifacts/2026-09-08/draft-evidence-regression.spec.ts.txt): copy to `frontend/e2e/review-regressions.spec.ts` and run `npm run test:e2e -- review-regressions.spec.ts` from `frontend`. It asserts the intended agreement and currently fails three assertions. It is stored outside automatic test discovery so this review does not silently alter Claude's suite.
- [Browser results](review-artifacts/2026-09-08/browser_results.json): captured draft/save disagreement and current-verdict text.

The reproduction fixture's invented source, product, classification rationale, and commercial values are strictly disposable test data, not market or regulatory evidence.
