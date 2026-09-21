# Independent follow-up review of Claude's work

Reviewed 9 September 2026. Branch: `impl/evidence-platform-phase0`. Commit: `71cd584`.
Assignment checked: the five numbered instructions under “Recommended next assignment for
Claude” in [the previous review](CLAUDE_IMPLEMENTATION_REVIEW_2026-09-08.md).

**Verdict: no, Claude has not completed everything requested. Eight of the eleven original
findings can be closed for their reviewed scope. R01, R03 and R07 remain partially fixed.
The new account-recovery implementation has two additional security defects. Source
feasibility research, guided onboarding and opportunity-report generation remain undone,
although these were explicitly identified as work that could proceed without provider
credentials. Gate A and deployment should remain unsigned.**

The handoff and much of the implementation are real. Its statement that “all eleven
findings are corrected and verified” is too broad. Existing tests pass, but additional
independent cases still fail.

This review used disposable local databases and browser accounts. It did not deploy,
inspect customer records, verify remote CI, contact providers, or send messages to Claude.
Application source and the established test suite are unchanged. The new browser specimen
is retained outside automatic discovery; the report and reproduction artifacts are the
only repository additions.

**Independent verification**

| Check rerun on this checkout | Result |
| --- | --- |
| Backend, SQLite | 458 passed, 14 PostgreSQL-only skips |
| Backend, PostgreSQL 16.4 | 472 passed, no skips, disposable schemas |
| Frontend unit/contract suite | 141 passed |
| `npm run typecheck` | Passed, including `tsconfig.e2e.json` |
| Production frontend build | Passed; main JS bundle 765.75 kB, 232.73 kB gzip |
| Claude's existing browser suite | 35 passed in Chromium |
| Claude's previous-review reproduction script | Its original cases now produce the corrected outcomes |
| Independent additional API reproductions | Confirmed classification, legacy approval, metric-label and recovery defects below |
| Independent additional browser specimen | Failed: evidence-request failure still creates contradictory draft/saved exports |
| Repeated PostgreSQL dump/restore drill | Both workspace counts and record-kind counts matched; two assessments replayed without failures at revision 0004 |

Some initial sandbox runs could not use local sockets or finish test-client communications;
the completed runs used approved execution outside that sandbox. Dependency advisory scans
were not repeated: the lockfiles are unchanged since the prior independent review. No
claim of newly verified advisory status or production recovery is made.

**Remaining defects, in priority order**

**F01 — P1: a password-reset token can be redeemed twice concurrently.**

Location: [backend/app/main.py](../backend/app/main.py), lines 574–590.
`reset_password()` reads the token, checks `used_at`, and later writes it without a row
lock or conditional atomic claim. Two requests can both pass validation before either
commits. The existing single-use test sends its requests sequentially and misses this.

The PostgreSQL reproduction submits two different new passwords using the same token.
A barrier in the password-hash call ensures both requests have validated the token; it
does not replace token validation, database operations or hashing. **Both return 200.**
The final password depends on which transaction wins. This violates the claimed
single-use guarantee; holding an already-used reset credential can still matter during
the overlapping request window.

Required correction: atomically claim the eligible token within the password-update
transaction, serialize the relevant account-security operations, and add real PostgreSQL
concurrency coverage. Exactly one redemption should succeed.

**F02 — P1: changing a password leaves previously issued reset tokens valid.**

Location: [backend/app/main.py](../backend/app/main.py), lines 593–605.
The authenticated password-change endpoint revokes other sessions but never invalidates
the account's recovery credentials.

Reproduction: request a reset through the local mail sink, change the password using the
current password, then redeem the older reset token. **The reset succeeds with 200**;
the user's newly chosen password then returns **401**, and the reset password returns
**200** at login. A leaked earlier reset message can therefore undo the security change
until the token expires.

Required correction: invalidate outstanding recovery credentials transactionally when a
password changes, including password resets. Cover concurrent issuance/change/redemption,
as well as this sequential case. This work does not require an email provider.

**F03 — P1, R01 remains open: an evidence-read failure becomes a zero-evidence draft.**

Location: [frontend/src/features/DecisionRoom.tsx](../frontend/src/features/DecisionRoom.tsx),
lines 37–38, 63–65 and 83–92.
The normal successful-read path is repaired. However, the screen falls back to the list
product while the authoritative detail request is unavailable. It never handles the
detail query's error state, and a missing reading falls through to `NO_EVIDENCE`.
Export remains enabled.

The browser reproduction creates four actual manual records in its disposable workspace,
then makes only the product-detail request return 503. Other requests work normally.
Without changing the commercial inputs, the user can produce:

| Field | Draft export | Saved export |
| --- | --- | --- |
| Confidence | 0 | 60 |
| Evidence records | 0 | 4 |
| Decision | INSUFFICIENT EVIDENCE | WATCH |

Required correction: represent unavailable evidence explicitly and provide retry/loading
behavior. Do not calculate or export an evidence verdict from a missing authoritative
reading. Test delayed and failed reads, product switching and recovery from the failure.
The saved server result is correct in this reproduction; the defect is in the draft/UI.

**F04 — P1, R03 remains open: incomplete classification approvals still clear the gate.**

Locations: [backend/app/compliance.py](../backend/app/compliance.py), lines 110–129 and
161–174. Two independently reproduced paths remain:

- An approval with `hs_code: "."`, current support and an explicit no-additional-requirements
  determination returns **200**, and `gate.resolved` is **true**. The new validator checks
  allowed characters without requiring any classification digits or valid structure.
- A legacy approval with current support, an unexpired review, **empty classification and
  empty requirements**, and no explicit “none apply” determination still returns
  `gate.resolved: true`. New-request validation does not apply when existing approvals
  are read. This is a record shape the previous implementation allowed.

Required correction: define and enforce the supported classification format and apply
the approval-completeness conditions when computing current gates from older records.
Incomplete legacy approvals should require a new review. Preserve historical saved
assessment snapshots. These are software-validation findings, not an assertion that a
syntactically valid code establishes a correct regulatory classification.

**F05 — P2, R07 remains partially open: requests rejected before routing retain raw paths.**

Locations: [backend/app/observability.py](../backend/app/observability.py), lines 73–95;
[backend/app/main.py](../backend/app/main.py), lines 188–206.
`route_label()` falls back to the old raw-path logic when no matched route exists.
CSRF rejection happens before routing, so it exercises that fallback. Twenty POSTs to
distinct `/api/review-private-marker-*` paths without the CSRF header all return 403,
yet create **20 distinct retained labels** containing the marker.

The important improvements are real: workspace owners now receive 403 from the operator
surface, and cardinality has a hard bound. This is **not** the old unbounded-growth or
cross-workspace owner-access defect. The remaining issue is retention/logging of
client-controlled paths and poisoning the finite metric vocabulary. The supplied
regression tests GETs that match `/api/{retired:path}`, so they do not test an unmatched
or pre-routing request.

Required correction: collapse every request without a trusted matched template into a
constant label, including middleware rejections. Exercise those paths in both counters
and actual emitted logs.

**Disposition of each original finding**

| Finding | Re-review outcome |
| --- | --- |
| R01 evidence/draft agreement | Partial; successful reads fixed, failed-read reproduction still fails (F03) |
| R02 password normalization | Closed for reviewed scope; exact whitespace/Unicode cases and HTTP legacy login pass |
| R03 compliance validation | Partial; expired-only support refused, but invalid/legacy incomplete approvals remain (F04) |
| R04 reviewer rejection | Closed for reviewed scope; server and browser yield NO-GO; prior gate version retained |
| R05 complete workspace export | Closed for reviewed scope; evidence and review collections present and reconciled |
| R06 restore replay and workspace identity | Closed for reviewed scope; repeated disposable restore matches by workspace ID and replays |
| R07 metrics privacy/cardinality | Partial; operator isolation and bound fixed, pre-routing labels remain (F05) |
| R08 baseline adoption guide | Closed for functional sequence; baseline check → stamp → upgrade → current check passes |
| R09 physical-schema readiness | Closed for reviewed scope; missing audit table returns 503; schema cases pass |
| R10 growing lists and picker | Closed for reviewed scope; pagination, independent search and navigation browser cases pass |
| R11 request-log identity | Closed for reviewed scope; actual emitted-log tests and browser logs carry identity |

**Did Claude follow all five instructions?**

| Previous assignment | Actual completion |
| --- | --- |
| 1. Fix R01–R07, retain passwords/history, add regressions | Substantial but incomplete: R01/R03/R07 remain open in the cases above |
| 2. Fix R08–R11, rerun suites, repeat restore and adoption | Completed for reviewed scope; independently rerun successfully |
| 3. Correct statuses and supply a detailed handoff | Handoff exists and statuses improved; “all eleven corrected” is inaccurate, and some status text remains stale |
| 4. Continue unblocked source research, recovery, onboarding and reports; infrastructure after source contracts | Recovery backend/local sink implemented with defects; source matrix, guided onboarding and report generation not done; no recovery/change/session-management UI exists |
| 5. Name external decisions and separate them from local work | Handoff names the decisions clearly; E01 still being marked fully Blocked on provider access contradicts the instruction to start public feasibility research now |

The original roadmap remains much larger than this correction pass. No live collector,
durable evidence-collection pipeline, operational monitoring/alerts, marketplace
intelligence or real actionable GO has been demonstrated. The synthetic GO remains
explicitly synthetic. External provider access can block connection and permitted sample
validation; it does not block documenting currently published capabilities and unknowns.
Email ownership verification can likewise be developed against a local sink before
production delivery is available.

Specific documentation corrections still needed: the action-plan introduction says Phase
1 is complete except recovery and production restore, although its own table also leaves
permissions/team work and alert forwarding partial. Its Gate A count still says 447
collected, although the current suite collects 472. P01/runbook descriptions still name
0001–0003 after 0004 was added. Recovery delivery is described as configuration-only even
though the runbook requires a new transport class/build branch and settings currently
accept only empty, `sink`, or `log`. The missing browser account flows and unfinished
verification/deletion work should be separated from the provider decision.

**Next work for Claude**

Correct F01–F05 with focused regressions, then rerun the affected suites and amend the
handoff/status claims. Complete the public-source feasibility matrix, account-security
browser flows and local verification work, guided onboarding, and record-based report
generation. Name the exact remaining external dependencies without using them to stop
unrelated local work. Keep Gate A in review and prepare another independent review before
deployment. This document is an assignment proposal, not a message sent to Claude.

**Reproduction evidence**

- [Independent API/concurrency script](review-artifacts/2026-09-09/independent_recheck.py)
  and [captured results](review-artifacts/2026-09-09/independent_results.json).
  Run `.venv/bin/python docs/review-artifacts/2026-09-09/independent_recheck.py --postgres`
  from the repository root. It uses a unique disposable schema in the test instance.
- [Browser specimen](review-artifacts/2026-09-09/independent-rereview.spec.ts.txt).
  Copy into `frontend/e2e/independent-rereview.spec.ts` and run
  `npm run test:e2e -- independent-rereview.spec.ts` from `frontend/`. It deliberately
  demonstrates the remaining mismatch and fails at the reviewed commit.
- [Rerun of original cases](review-artifacts/2026-09-09/independent_original_case_results.json).
- [Restore wrapper](review-artifacts/2026-09-09/independent_restore.py) and
  [restore results](review-artifacts/2026-09-09/independent_restore_results.json).
  The wrapper runs Claude's existing drill with unique database names and cleanup.
- [Check summary](review-artifacts/2026-09-09/independent_check_summary.json).

All source names, classifications, identities and prices in these artifacts are disposable
software-test fixtures, not market observations or regulatory evidence.
