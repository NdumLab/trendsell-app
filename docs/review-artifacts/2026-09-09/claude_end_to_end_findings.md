# End-to-end review findings — 9 September 2026

An independent end-to-end pass over the whole application after F01–F05 were corrected:
every route's authorisation, the full role matrix, cross-workspace isolation on every
id-taking route, the complete user journey, log content, and the concurrency of every
state transition that has an invariant.

Reproductions are the scripts named below. All used disposable databases and throwaway
accounts; nothing live was read or deployed.

## What was checked and found sound

| Area | Method | Result |
| --- | --- | --- |
| Route authorisation | Introspected every route's dependency tree | Every non-public route requires a session; the public ones are health, ready, config, data-health, register, login, recovery, verification-confirm and the token-gated metrics surface |
| Role matrix | 4 roles × 12 permission-gated routes | 48/48 enforced exactly as `permissions.py` declares |
| Cross-workspace isolation | Every id-taking route, attempted by a second workspace | 10/10 refused (404); the victim's records byte-identical afterwards |
| Assessment immutability | Saved a decision, then withdrew *every* evidence record | Saved assessment unchanged, snapshot intact, live product correctly drops to 0 |
| Export completeness | Counts vs streamed rows, all seven kinds | Reconciled |
| Evidence method | Full-coverage journey | Caps at 60 as designed; GO correctly unreachable from self-reported evidence |
| Log content | Registered, reset, logged in wrongly, read metrics, searched | No password, cookie, token, email, ASIN, product name, body or query string in any emitted line |
| Identifier parsing | `resolve_input` | Parse-only; no fetch, host/scheme/port/userinfo all constrained |
| Cross-language contracts | `contracts/*.json` | Consumed by **both** the Python and TypeScript suites, so the two implementations cannot drift apart silently |
| Settings validation | `Settings.from_env` | Production requires PostgreSQL and HTTPS origins; no wildcard CORS |

## Corrected in this pass

**E01 — P1: one compliance review accepted two conflicting decisions.**
`decide_review()` read `status == 'requested'` and then wrote, with no lock and no
conditional claim — the shape F01 had. Two decisions submitted at the same moment (two
reviewers, or one double submission) **both returned 200**, one review recorded **two**
`compliance.reviewed` audit events, and the later commit silently replaced the earlier
decision: a rejection could be overwritten by an approval that then **resolved the gate**.
Corrected by locking the review row before its status is read.
Regression: `test_one_review_accepts_exactly_one_decision_under_postgres`; removing the
lock reproduces `[200, 200]`.

**E02 — P2: three more screens reported a failed read as a fact (the F03 class).**
F03 was corrected in Decision Room only. The same pattern remained where a query fails
with no previously cached success:

| Screen | What it displayed | Reality |
| --- | --- | --- |
| Today | `00` in all four counters, no error shown | Products visible in the grid on the same screen |
| Evidence ledger | "No evidence recorded yet" | Four records existed |
| Product picker | "No product matches that search." | The product existed |

Each now names the failure and offers a retry instead of asserting a negative.
Regressions: `e2e/failed-read-honesty.spec.ts` — all three fail against the pre-fix code.

## Open — these need a decision, not just a patch

**E03 — P2: a pending re-review erases a decided one, including a rejection.**
`latest_review()` returns the newest review record *of any status*, so a merely
**requested** review outranks a **decided** one in the gate.

Reproduction (`probe_compliance.py`): a reviewer rejects a product — the assessment
correctly becomes `NO-GO` with "A reviewer rejected this product for import. Do not
proceed." Any member holding `workspace.write` then requests another review, and with no
reviewer involvement the gate returns to `requested` and the next assessment reads
`INSUFFICIENT EVIDENCE` with the rejection blocker gone. The rejection survives only in
the history list. The same happens to an approval, where the effect is fail-safe.

This does not manufacture a `GO` — evidence is still capped and compliance unresolved —
but it removes the authoritative "do not proceed" that R04 exists to carry.

Recommendation: compute the gate from the latest **decided** review, and surface a pending
re-request alongside it rather than in place of it. The records already support this: every
review carries `supersedes` / `superseded_by`. This changes visible behaviour — after a
rejection the product keeps reading `rejected` until a new decision lands — so it is a
product call, not only an implementation one.

**E04 — P3 (latent): `workspace.read` is declared, granted, and enforced by no route.**
Every read route depends on `current_user`, not on `permitted('workspace.read')`; the
permission is checked nowhere. It is harmless today because all four roles hold it, but
the matrix advertises a control that does not exist.

Reproduction (`probe_read_perm.py`): a role holding **no permissions at all** still reads
the product list, product detail, evidence, compliance, decisions, quotes, watchlist,
summary and alerts — while `export` and `audit`, which do check, correctly return 403.

Recommendation: require `workspace.read` on the read routes, so a future restricted role
(a suspended member, a billing contact) is actually restricted. `workspace.admin` is
likewise declared and unenforced, but nothing it would guard exists yet.

## Reproductions

Scripts used for E01–E04 are kept with this session's scratch work rather than committed;
each is a few dozen lines and is described precisely enough above to rebuild. The two
findings that were corrected carry permanent regressions in the suite instead:
`test_one_review_accepts_exactly_one_decision_under_postgres` and
`frontend/e2e/failed-read-honesty.spec.ts`.
