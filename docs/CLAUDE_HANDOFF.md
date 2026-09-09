# Handoff — corrections to the 8 September independent review

Branch: `impl/evidence-platform-phase0`. Head: `f81c424`.
Reviewed commit: `83a4a0d`. Review: [CLAUDE_IMPLEMENTATION_REVIEW_2026-09-08.md](CLAUDE_IMPLEMENTATION_REVIEW_2026-09-08.md).
Written: 9 September 2026.

**All eleven findings (R01–R11) are corrected and verified locally. Deployment remains
pending Codex's final independent review; nothing here has been deployed, and Gate A is
marked `In review`, not `Done`.**

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
5. **Recovery cannot deliver** (P03). With no transport the endpoint mints no token and
   sends nothing; a locked-out user still needs an operator, and that procedure is not
   written. Verified email ownership is not implemented.
6. **Account and workspace deletion** is not implemented.
7. **No production restore drill, no scheduled backups, no agreed RPO/RTO** (P06). The
   drill above is disposable PostgreSQL only.
8. **No alerting reaches an on-call destination** (P07). Counters and structured logs
   exist; nothing forwards them.
9. **Metrics are per worker**, so a value is a floor rather than a fleet total.
10. **The production frontend bundle exceeds 500 kB** and is not code-split. Pre-existing;
    no user-visible failure, but it should be addressed before a public release.
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

1. **Codex's independent re-review of this branch.** Deployment stays pending it. The
   fastest confirmation is `verification.py` plus `e2e/review-regressions.spec.ts`.
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

# The review's findings, and the restore drill
.venv/bin/python docs/review-artifacts/2026-09-09/verification.py
.venv/bin/python docs/review-artifacts/2026-09-09/restore_drill.py
```

Both scripts create and drop their own disposable databases and never read a live one.
Their fixture values — sources, classifications, prices, suppliers — are test data, not
market or regulatory evidence.
