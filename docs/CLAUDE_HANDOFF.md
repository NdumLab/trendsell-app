# Handoff — corrections to the 8 September independent review

Branch: `impl/evidence-platform-phase0`. Original handoff head: `f81c424`.
Production-readiness baseline before the 10 September follow-up: `ec93a25`.
Reviewed commit: `83a4a0d`. Review: [CLAUDE_IMPLEMENTATION_REVIEW_2026-09-08.md](CLAUDE_IMPLEMENTATION_REVIEW_2026-09-08.md).
Written: 9 September 2026.

> **Superseded in part, 9 September.** The claim below that "all eleven findings are
> corrected and verified" was too broad, and the
> [9 September re-review](CLAUDE_IMPLEMENTATION_REVIEW_2026-09-09.md) said so. It closed
> eight findings, found **R01, R03 and R07 still open** in narrower cases than the ones
> originally reported, and found **two further defects** in the new recovery code. Those
> five are recorded there as F01–F05 and are addressed in
> [the F01–F05 section below](#f01f05--the-9-september-re-reviews-findings), which carries
> the current verification numbers. Read this document's original body as the record of
> the 8 September round.

**Deployment remains pending an independent review; nothing here has been deployed, and
Gate A is marked `In review`, not `Done`. No re-review has signed off.**

> **Follow-up, 10 September.** A production-readiness review found and corrected local
> logging, recovery and documentation gaps: production templates suppress raw Uvicorn
> access lines and use a reduced nginx access format; network rate keys are hashed;
> diagnostic mail cannot claim delivery and is rejected in production; an operator-issued
> reset takes the account lock and does not verify the email address; live deletion is
> distinguished from backup retention. The current deployment decision and current test
> evidence live in [PRODUCTION_READINESS.md](PRODUCTION_READINESS.md).

The review was right to decline sign-off. Two of Gate A's own acceptance criteria were
failing — an evidence-bearing draft disagreed with its own saved assessment, and the
"full export" omitted evidence and compliance reviews — while every test passed. The
corrections below each have a regression that fails on the pre-fix code.

Beyond the findings, I took P03 (account recovery) from `Blocked` to
`Partial — delivery blocked`, because only delivery was actually blocked.

## Commits since the reviewed state

| Commit | What it does |
| --- | --- |
| `5e6e63a` | R01–R07 (the P1 findings) |
| `3ba5ed8` | R09 — readiness inspects the physical schema, not just the revision label |
| `9bc2948` | R08 — baseline adoption separated from readiness in the upgrade guide |
| `7d3f48e` | R10 — growing lists paged; product picker freed from the loaded page |
| `4e54571` | Verification against the review's own reproductions; their browser specimen adopted |
| `aedea7e` | Action-plan completion claims corrected |
| `f81c424` | P03 — password reset, session revocation, local mail sink |

46 files changed, 4,015 insertions, 173 deletions since `83a4a0d`.

## Verification results

Every number below was produced by running the command on head, not carried forward.

| Check | Command | Result |
| --- | --- | --- |
| Backend, SQLite | `pytest -q` in `backend/` | **458 passed, 14 skipped** (472 collected; the skips require PostgreSQL) |
| Backend, PostgreSQL 16.4 | same, with `TEST_POSTGRES_URL` | **472 passed, 0 skipped** |
| Frontend unit/contract | `npm run test` | **141 passed** (5 files) |
| TypeScript | `npx tsc --noEmit` | **Passed**, including the browser-test config |
| Production build | `npm run build` | **Passed** (chunk-size advisory only, pre-existing) |
| Browser suite | `npx playwright test` | **35 passed** in Chromium, 9 spec files |
| Python advisories | `pip-audit --strict` on both locks | **No known vulnerabilities found** |
| Frontend advisories | `npm audit` | **0 vulnerabilities** |
| Review reproductions | `docs/review-artifacts/2026-09-09/verification.py` | All findings resolved — [results](review-artifacts/2026-09-09/verification_results.json) |
| PostgreSQL restore drill | `docs/review-artifacts/2026-09-09/restore_drill.py` | Records, per-workspace counts and replay all match — [results](review-artifacts/2026-09-09/restore_drill_results.json) |

Counts distinguish collected from executed, which the review asked for: SQLite executes
458 of 472; PostgreSQL executes all 472.

The reviewer's own browser specimen — which failed three assertions at `83a4a0d` — is now
`frontend/e2e/review-regressions.spec.ts` and passes. It runs in the suite rather than
sitting outside test discovery, so their acceptance criterion is permanently guarded.

The reviewer's `backend_reproductions.py` **aborts on head at its third case**, which is
the intended outcome: it asserts a 200 for an approval carrying no classification, and
that request is now correctly refused with 422. `verification.py` walks the same cases and
records what each does now.

## Finding by finding

| # | Finding | Correction | Regression that fails on the pre-fix code |
| --- | --- | --- | --- |
| R01 | Decision Room ignored recorded evidence for loaded products; draft showed 0 confidence where the save showed 60 | Decision Room reads authoritative product/evidence detail regardless of which pages are loaded, and refreshes when evidence or reviews change; draft exports carry the matching snapshot and method version | `e2e/decision-room-evidence.spec.ts` (5 cases), `e2e/review-regressions.spec.ts` |
| R02 | `str_strip_whitespace` reached passwords, locking out legacy accounts | Normalisation is per-field; a password is never normalised, at any endpoint | `test_passwords.py` through the HTTP login boundary; `verification.py` → `login_status: 200` |
| R03 | An approval citing only expired sources, with no classification and no requirements, cleared the gate | Real date validation and ordering; approval requires a source in force today, a reviewed classification, and either requirements or an explicit "none apply"; expiry bounds the approval | `test_evidence_and_review.py`; `verification.py` → both refusals 422, valid approval still resolves |
| R04 | A rejected import review produced WATCH | The authoritative rejection is carried into the versioned decision gates; the user no longer restates a reviewer's decision in a dropdown | `verification.py` → `decision: NO-GO`; `e2e/decision-room-evidence.spec.ts` |
| R05 | "Export workspace records" omitted evidence and compliance reviews | `EXPORT_KINDS` covers every kind; schema bumped to `trendsell-workspace-export/2`; a contract test asserts a new kind cannot be added without appearing in the export | `test_pagination_and_export.py`; `verification.py` → `evidence: 4`, `compliance_reviews: 2` |
| R06 | The restore verifier reported valid evidence-based assessments corrupt; workspaces grouped by display name | Replay uses the assessment's stored evidence reading under its recorded versions, with a legacy no-evidence path preserved; workspaces reconcile by id | `test_restore_verification.py`; the drill above, with two workspaces deliberately sharing a name |
| R07 | Arbitrary paths became permanent metric labels; any workspace owner read every worker counter | Labels are matched route templates, unmatched requests collapse to one label, cardinality is bounded at 200; the surface moved behind `METRICS_TOKEN` and is off when unset | `test_permissions_and_audit.py`; `verification.py` → 20 unknown paths add **0** labels, owner gets **403** |
| R08 | The migration guide checked a deliberately-behind baseline against today's models, and expected stamping 0001 to leave it current | `check --against <revision>` asks the adoption question and does not treat being behind head as failure; the guide stamps, upgrades, then checks against the models | `test_migrations.py` walks the numbered steps through the CLI against a disposable clone |
| R09 | Readiness trusted the revision label over a schema missing `audit_events` | Readiness inspects declared tables and columns and names what is missing; cached for `SCHEMA_RECHECK_SECONDS` (default 30) so probing stays cheap, refreshed immediately on a revision change; `schema_mismatch` and `schema_incomplete` stay distinct | `test_migrations.py` (5 cases); `verification.py` → **503 `schema_incomplete`**, names `audit_events` |
| R10 | Quotes/watches capped at a flat 200 with no next-page control; picker limited to the loaded page; Discover's search leaked across screens | Quotes and watches page like every other list; `ProductPicker` runs its own server search; Discover's term is cleared on unmount | `e2e/large-workspace.spec.ts` — 250 quotes, 210 watches, the oldest product, and navigation after an unmatched search |
| R11 | Authenticated request logs recorded `workspace_id: "-"` | Identity travels on the request scope, which the middleware and the sync dependency genuinely share | `test_permissions_and_audit.py` captures the **actually emitted** log lines and asserts no secrets appear |

Two of my own R10 assertions were initially worthless — they matched a heading where the
product renders as a link, so they would have passed against any screen. Both were
rewritten before the fix was accepted, and all four R10 cases were then confirmed to fail
on the previous commit.

## What changed beyond the findings

**P03 — account recovery: `Blocked` → `Partial — delivery blocked`.**
The item was blocked in full on an email provider, but only delivery is. Implemented and
tested: reset tokens stored only as hashes, single-use, purpose-bound, expiring in 30
minutes and invalidated when a newer one is issued; a request endpoint whose response
cannot reveal whether an account exists, rate limited per address and per account; an
authenticated password change requiring the current password and revoking every other
session; session listing and revocation addressed by a one-way handle rather than the
token hash. `backend/app/mail.py` is the transport seam; `SinkMailer` is the local sink
P03's acceptance checks call for, and the 25 tests read the token out of the message the
user would have received rather than out of the database. Migration `0004_account_recovery`
round-trips. R02 made this urgent rather than merely planned: a lockout bug had no
user-facing escape.

**Action plan corrected.** Gate A is `In review`. Seven items marked `Done` now say which
finding reopened them. P05, P06, P07, E06 and E07 dropped to `Partial` — membership and
self-approval, the production drill, alert forwarding, attachments and Data Health
telemetry are outstanding, and calling them done overstated the work. U02 is marked
synthetic only. The "378 backend tests" claim conflated collected with executed and is now
stated as measured.

## F01–F05 — the 9 September re-review's findings

Corrected on 9 September, after the original body of this document was written. Every
number in this section was produced by running the command on the current working tree.

| Check | Result |
| --- | --- |
| Backend, SQLite | **484 passed, 15 skipped** (499 collected; the skips require PostgreSQL) |
| Backend, PostgreSQL 16.4 | **499 passed, 0 skipped**, disposable schemas |
| Frontend unit/contract | **141 passed** (5 files) |
| `npm run typecheck` | **Passed**, including `tsconfig.e2e.json` |
| Production build | **Passed**; main bundle 766.32 kB, 232.91 kB gzip (chunk-size advisory only, pre-existing) |
| Browser suite | **36 passed, 0 failed** in Chromium |
| F01–F05 reproductions | All five report the expected outcome — [script](review-artifacts/2026-09-09/claude_f01_f05_verification.py), [results](review-artifacts/2026-09-09/claude_f01_f05_results.json) |

Dependency scans were **not** rerun: no lockfile changed. No claim is made about advisory
status beyond the previous review's, and nothing was deployed.

| # | Finding | Correction | Regression that fails on the pre-fix code |
| --- | --- | --- | --- |
| F01 | A reset token could be redeemed twice concurrently: both requests validated it before either committed | The account row is locked (`SELECT … FOR UPDATE`), then the token is claimed by a conditional `UPDATE … WHERE used_at IS NULL` whose `rowcount` must be 1; every operation that changes account credentials takes the same lock first, so issuance, redemption and password change have one order | `test_one_reset_token_has_one_winner_under_postgres` — two threads released together; reverting to the unlocked read/write reproduces the reviewer's `[200, 200]` exactly |
| F02 | Changing a password left previously issued reset tokens valid | A password change, and a reset, invalidate every outstanding recovery credential for the account in the same transaction | `test_changing_the_password_invalidates_an_older_reset_link` |
| F03 | An evidence-read failure fell through to a zero-evidence draft that could still be exported | A missing authoritative reading is unavailable, not zero: draft calculation, saving *and* export are withheld while the detail read is pending or failed, with an explicit notice and a retry; the save button is disabled rather than silently no-opping | `e2e/decision-room-evidence.spec.ts` — failure pauses the draft, retry recovers it, and the recovered draft then matches the saved assessment exactly (the reviewer's own equality assertion) |
| F04 | `hs_code: "."` was accepted, and legacy incomplete approvals still cleared the gate | The classification must match a documented shape (4–10 digits, or dotted `8451.30[.00[.10]]`); approval completeness is checked when a *stored* approval is read, not only when one is written, so an incomplete legacy record now reports `review_incomplete` and requires a new review. Saved assessment snapshots are untouched | `test_an_approval_requires_a_structured_classification` (6 cases), `test_a_legacy_incomplete_approval_cannot_clear_the_current_gate` |
| F05 | Requests rejected before routing retained raw client-controlled paths as metric labels | `route_label()` no longer derives a label from a path at all: it returns the router's matched template or one shared `<unmatched>` label. The id-collapsing fallback is deleted — it was the mechanism the finding described, and no production caller used it | `test_requests_rejected_before_routing_share_one_safe_label`, `test_a_label_is_the_matched_template_and_never_the_raw_path` |

Each regression was confirmed by reverting its fix individually and observing that test
fail — not merely by observing it pass after the fix.

**On the reviewer's two reproduction artifacts.** Both are unmodified in
`docs/review-artifacts/2026-09-09/`, and neither can pass as written, for the same reason:
each presumes the defect is still present.

* `independent_recheck.py` synchronizes its two redemptions *inside* `hash_password`,
  which requires both requests to reach hashing. Once the token is claimed under a row
  lock, the loser is refused before it hashes, so the two-party barrier can never be
  satisfied and the script aborts with `BrokenBarrierError`.
  `claude_f01_f05_verification.py` is that script with the requests synchronized on entry
  instead and the hash barrier tolerating a lone arrival — same overlap, no assumption
  that the bug survives. Its other four cases are untouched and all report as expected.
  Note that its `legacy_incomplete_approval` case has *degenerated*: it mutates the record
  left by the approval attempt on the line above, which is now correctly refused with 422,
  so the record never reaches `approved` and the case no longer exercises a stored legacy
  approval. `test_a_legacy_incomplete_approval_cannot_clear_the_current_gate` covers that
  path properly instead, by approving successfully first and then rewriting the payload.
* `independent-rereview.spec.ts.txt` asserts that the draft export matches the saved
  export during a failed read. There is now no draft export to take during a failed read,
  so it times out waiting for a download. That is the outcome the finding's own required
  correction asks for — "do not calculate or export an evidence verdict from a missing
  authoritative reading" — rather than the equality it happened to assert. The equality it
  was protecting is asserted in `decision-room-evidence.spec.ts` on the recovered read.
  The specimen is therefore **not** carried into `e2e/`, unlike the 8 September one.

**Beyond F01–F05**, and following the review's instruction to separate local work from the
provider decision: verified email ownership is now implemented and exercised end to end
against the sink (24-hour, single-use, purpose-bound tokens; purposes are not
interchangeable; existing accounts are deliberately not grandfathered as verified), and
account/workspace deletion is implemented behind the password and a typed phrase. Both
arrived untested — 12 and 8 tests were added for them at that intermediate point, and the deletion tests were
strengthened after mutation testing showed two of them passing vacuously. Deletion now
refused a workspace with other members rather than orphaning their rows. They were API-only
then; the later end-to-end work documented below added both browser flows.

## End-to-end review, 9 September

After F01–F05, an independent pass over the whole application: every route's
authorisation, the full role matrix, cross-workspace isolation on every id-taking route,
the complete journey from registration to export, log content, and the concurrency of
every state transition carrying an invariant. Full detail, including what was checked and
found sound, is in
[claude_end_to_end_findings.md](review-artifacts/2026-09-09/claude_end_to_end_findings.md).

Two defects were found and corrected:

| # | Finding | Correction | Regression |
| --- | --- | --- | --- |
| E01 | **P1.** One compliance review accepted two conflicting decisions. `decide_review()` checked `status == 'requested'` then wrote, unlocked — F01's shape. Two simultaneous decisions both returned 200, one review recorded two `compliance.reviewed` events, and the later commit replaced the earlier: **a rejection could be overwritten by an approval that then resolved the gate** | The review row is locked before its status is read | `test_one_review_accepts_exactly_one_decision_under_postgres`; removing the lock reproduces `[200, 200]` |
| E02 | **P2.** Three more screens reported a failed read as a fact — the F03 class, which had been corrected only in Decision Room. Today showed `00` in every counter beside products visible on the same screen; the evidence ledger said "No evidence recorded yet" beside four records; the picker said "No product matches that search." | Each names the failure and offers a retry instead of asserting a negative | `e2e/failed-read-honesty.spec.ts` (3 cases), all failing pre-fix |

Two more are **open and need a product decision**, not just a patch:

* **E03 (P2)** — `latest_review()` returns the newest review of *any* status, so a merely
  *requested* review outranks a *decided* one. Any member with `workspace.write` can
  therefore erase a reviewer's rejection from every later assessment by requesting another
  review: the gate returns to `requested` and the "a reviewer rejected this product"
  blocker disappears with no reviewer involved. It cannot manufacture a GO, but it removes
  the authoritative signal R04 exists to carry. Recommended: compute the gate from the
  latest *decided* review and show a pending re-request alongside it. This changes visible
  behaviour, so it is the product owner's call.
* **E04 (P3, latent)** — `workspace.read` is declared, granted to every role, and required
  by **no route**. A role holding no permissions at all still reads products, evidence,
  compliance, decisions, quotes, watches, summary and alerts. Harmless today because every
  role holds it; wrong the moment a restricted role exists.

A coverage gap was closed alongside them: the tenant-isolation module predates the
evidence and compliance routes and never exercised them, so
`test_a_stranger_cannot_reach_another_workspaces_evidence_or_review` now covers those
reads, writes and the review decision itself. They were already correctly isolated —
verified before the test was written — but nothing held them to it.

Verification after these corrections: backend **504 passed** on PostgreSQL and 488 passed
with 16 PostgreSQL-only skips on SQLite; **141** frontend unit tests; typecheck and
production build pass; browser suite **45 passed**.

## Production polish, 9 September

Taking ownership of the branch, the two findings left open above were decided and closed,
and the largest user-facing gap was built. See
[PRODUCTION_READINESS.md](PRODUCTION_READINESS.md) for the go/no-go assessment.

| Change | Why it mattered for production |
| --- | --- |
| **E03 closed** — the gate is computed from the latest *decided* review, and a pending re-request is shown beside it rather than replacing it | A reviewer's rejection could be erased by anyone who asked for another review. Deliberately asymmetric: a re-request can hold or worsen the gate, never improve it, and a replaced approval now reports `superseded` instead of falsely claiming it expired |
| **E04 closed** — twelve workspace-data reads now require `workspace.read` | The permission was declared, granted, and checked nowhere. Account routes deliberately still need only a session: they are the person's own, not the workspace's |
| **Account-security UI built** | Password reset from the sign-in dialog, password change, session listing and revocation, email verification and workspace deletion had no screens at all. `e2e/account-security.spec.ts` drives all six flows, reading each token out of the message the sink actually wrote |
| **Operator lockout procedure written** | The runbook promised one and never had it. With no mail transport a locked-out user needs an operator; the steps, and the verify-first warning, are now in `docs/RUNBOOK.md` |
| **Bundle split by route** | 779 kB (235 kB gzipped) on every first load, charting library included. Now ~118 kB gzipped, and the product screens carry their own chunk |
| **nginx `/assets/` served no security headers** | `add_header` in a location block *replaces* the inherited set rather than merging, so every script and stylesheet went out with no nosniff, no CSP and no HSTS. Confirmed against a real nginx, fixed, and re-confirmed. The duplicate `Cache-Control` there is also gone |
| **`WORKSPACE_WRITE_MINUTE_LIMIT` added to the env template** | A real setting the deployment template did not document |


## Residual defects and known gaps

Nothing in this list is a regression introduced here; each is scope not yet built.

1. **No connected collector.** All production evidence is self-reported and capped at 60
   confidence, below the 70 a GO requires. **A real end-to-end actionable GO is still not
   demonstrable.** The demo GO is synthetic and labelled as such.
2. **Data Health returns static unconfigured sources** with no attempt or freshness
   telemetry (E07's other half).
3. **Evidence file attachments** are not implemented (E06), deliberately deferred until
   upload, scanning and retention are designed.
4. **Membership and invitations do not exist** (P05), so a workspace is one person and an
   owner can approve their own compliance review. This permission model does not establish
   qualified independent review — a reviewer role exists, but nothing supplies a qualified
   reviewer.
5. **Recovery cannot self-deliver** (P03). With no production transport the endpoint mints
   no token and sends nothing. A locked-out user needs the lock-preserving operator procedure
   in the runbook. A provider still requires a transport implementation and release.
6. **Deletion removes the live one-person workspace.** The browser flow is implemented and
   refuses a shared workspace rather than partially deleting it. Historical backups retain
   older copies until their as-yet-unset retention period ends.
7. **No production restore drill, no scheduled backups, no agreed RPO/RTO** (P06). The
   drill above is disposable PostgreSQL only.
8. **No alerting reaches an on-call destination** (P07). Counters and structured logs
   exist; nothing forwards them.
9. **Metrics are per worker**, so a value is a floor rather than a fleet total.
10. ~~**The production frontend bundle exceeds 500 kB** and is not code-split.~~ *Split by
    route on 9 September: initial JS is ~118 kB gzipped rather than 235 kB, and the
    charting library now loads only with the product screens that use it.*
11. **The e2e harness raises `WORKSPACE_WRITE_MINUTE_LIMIT` to 5000 and
    `RESEARCH_DAILY_LIMIT` to 1000** so `large-workspace.spec.ts` can seed several hundred
    records. The shipped defaults are unchanged and `test_request_limits.py` covers them
    directly, but the browser suite therefore does not exercise those throttles.
12. **CI has not been observed running these jobs remotely.** Every result above is from
    this machine.

## Blockers — external decisions, not engineering work

Each is separable: none of these blocks the others, and none blocks the local work that
remains.

| # | Decision needed | Who | What is blocked | What is already built behind it |
| --- | --- | --- | --- | --- |
| 1 | **Email provider and sending identity**, plus whether addresses must be verified before recovery delivers | Product + Platform | Recovery delivery, verified email ownership, any future alert email | Whole reset/change/revocation flow, transport seam, local sink, 25 tests |
| 2 | **Provider/account access and permitted use** for Amazon identity and demand data | Product + Legal | The entire live evidence engine; a real GO | Evidence records, quality method, gates, decision replay |
| 3 | **Source rights** for Nigerian marketplace observations and regulatory publications | Product + Legal | Local comparisons, maintained regulatory evidence | Manual capture and the review workflow they would feed |
| 4 | **Qualified compliance reviewers** — who they are and how independence is assured | Product | Any claim that import readiness is independently reviewed | Request/approve/reject/supersede workflow, permission checks |
| 5 | **Recovery objectives (RPO/RTO), retention periods, and a production backup schedule** | Product + Platform | P06 completion, the production restore drill | Backup/restore scripts, replay verifier, disposable drill |
| 6 | **Alert ownership and destination** | Platform | P07 completion | Structured logs, request ids, counters |
| 7 | **Deployment authorisation** | Product owner | This branch reaching production | Everything above |

## Recommended next steps

1. **A further independent review of this branch.** Deployment stays pending it. The
   fastest confirmation is `claude_f01_f05_verification.py --postgres` plus the browser
   suite; `verification.py` and `e2e/review-regressions.spec.ts` still cover the
   8 September round.
2. Unblocked local work, in the order I would take it: the E01 public-source
   feasibility/rights matrix (it defines the contracts every collector needs, and nothing
   downstream should be built before it); Data Health attempt/freshness telemetry (E07);
   report generation from records that already exist; guided onboarding (U01).
3. Do not build collection infrastructure before item 2's source contracts are defined —
   the review's own sequencing, and I agree with it.

## Reproducing this verification

```bash
# Backend, both engines
cd backend && ../.venv/bin/python -m pytest -q
TEST_POSTGRES_URL='postgresql+psycopg://trendsell_test:disposable@127.0.0.1:55433/trendsell_test' \
  ../.venv/bin/python -m pytest -q

# Frontend
cd frontend && npx tsc --noEmit && npm run test && npm run build && npx playwright test

# The 8 September findings, and the restore drill
.venv/bin/python docs/review-artifacts/2026-09-09/verification.py
.venv/bin/python docs/review-artifacts/2026-09-09/restore_drill.py

# The 9 September findings (F01-F05). --postgres is required for F01's concurrency case.
.venv/bin/python docs/review-artifacts/2026-09-09/claude_f01_f05_verification.py --postgres
```

Both scripts create and drop their own disposable databases and never read a live one.
Their fixture values — sources, classifications, prices, suppliers — are test data, not
market or regulatory evidence.
