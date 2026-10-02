# Claude handoff — live-research engineering continuation

Prepared 30 September 2026 UTC and continued 2 October 2026 UTC on branch
`impl/evidence-platform-phase0`.

## Objective and boundary

Continue making TrendSell technically ready for bounded live research. Preserve every
truthfulness, tenancy, lineage, retention and safety invariant. Do not spend money, create
provider accounts, request or install credentials, accept provider terms, appoint owners,
claim independent review, or mutate production merely to clear a gate. Those are the human
or external blockers the user asked us to leave alone while engineering work continues.

The production decision is still **NO-GO**. The current target facts and exact residual gaps
are in [`2026-09-30-target-technical-audit.md`](2026-09-30-target-technical-audit.md).

## Repository checkpoint

The continuation reviewed and preserved the handoff work as two distinct implementation
commits:

* `c732e93` — provider-boundary hardening; and
* `6ac6fec` — actionable, immutable supplier-quote revisions.

They follow the previously pushed checkpoint
`431e9ac4d9a81c8385511748a1e11a469d563dae`. The complete combined candidate was verified
before the commits were created. No provider was activated and no deployment was performed.

## Change set A — provider-boundary hardening

These changes appeared concurrently while the quote work below was being implemented; their
origin was not established during the original handoff. They were preserved, reviewed and
committed separately from the quote work.

The provider hardening currently:

* bounds JSON provider responses at 10 MiB;
* validates clickable Amazon and Jumia evidence links as HTTPS on the expected host family;
* deliberately omits provider image URLs from the retained catalog mapping;
* retries and safely classifies DataForSEO's internal task status codes returned inside HTTP
  200 responses without exposing provider response text;
* preserves valid `0` and `false` Jumia fields instead of erasing them through truthy fallback;
* rejects non-positive, boolean, NaN and infinite FX rates;
* bumps provider collector/parser versions to `1.1.0`; and
* wraps each normalized provider save in a database savepoint so a save/parser failure cannot
  leave a snapshot or evidence row behind while the job reports that source unavailable.

The continuation checked the DataForSEO classifications against the provider's official error
appendix and reviewed the expected host suffixes. The behavior remains fixture-tested only;
no live account or credential was used.

## Change set B — actionable, versioned supplier quotes

This turn advanced action-plan item `D01` without relying on provider access or human approval.
The current implementation:

* records explicit `valid_until`, product specifications, payment terms and delivery scope;
* creates immutable quote revisions using `supersedes_quote_id`, `revision` and
  `root_quote_id`, and refuses a second child revision from the same version;
* enforces the same supplier identity across a revision chain in both the API and the UI;
* retains legacy compatibility by allowing old API submissions with no explicit validity;
* exposes a **Revise** action that prefills a new immutable version instead of editing the old
  quote;
* offers **Revise** only on the current leaf and labels prior versions as superseded;
* shows revision, validity, delivery coverage, payment terms and quoted specification in the
  supplier/decision flows;
* warns in the Decision Room when a quote is expired, has no legacy validity date, or the
  scenario quantity is below MOQ; and
* snapshots those facts as `quote_checks` on the saved assessment so later exports preserve
  the exact validity/MOQ evaluation rather than recomputing it from current state.

The server deliberately allows saving an expired or below-MOQ scenario but records explicit
warnings. This supports comparison/history without presenting the quote as usable. Reassess that
policy before changing it; silently accepting without the warning snapshot is not acceptable.

## Continuation decisions

The open supplier-identity question was resolved conservatively: a revision must retain the
exact supplier string of the version it supersedes. The revision form keeps that field
read-only, and the API rejects attempts to change it. A different supplier must be recorded
as a new root quote. This prevents a historical quote chain from silently changing identity.

The requested browser regression now creates a quote, revises it, confirms that both immutable
versions remain visible, confirms the supplier cannot be changed, and selects the intended
revision in Decision Room. The large-workspace browser fixture was also updated to satisfy the
new actionable-quote fields.

## Verification completed

All of the following passed against the complete combined candidate on 2 October 2026:

```text
git diff --check
npm --prefix frontend run typecheck
  TypeScript application + E2E configs: PASS
npm --prefix frontend test -- --run
  5 files, 141 tests: PASS
TEST_POSTGRES_URL= .venv/bin/pytest -q -n 0 backend/tests/redesign/test_live_source_providers.py
  26 passed
TEST_POSTGRES_URL=postgresql+psycopg://...@127.0.0.1:55433/trendsell_test \
  .venv/bin/pytest -q -n 0 backend/tests/redesign/test_decisions_and_records.py \
  backend/tests/redesign/test_amazon_creators_provider.py backend/tests/redesign/test_concurrency.py
  46 passed
cd backend && TEST_POSTGRES_URL=postgresql+psycopg://...@127.0.0.1:55433/trendsell_test \
  ../.venv/bin/python -m pytest -q
  639 passed, 2 warnings
npm --prefix frontend run build
  Production build: PASS
npm --prefix frontend run test:e2e
  55 Chromium tests passed
```

The PostgreSQL and browser commands needed execution outside the restricted sandbox because
loopback/container access is denied inside it. `trendsell-test-db` was running on
`127.0.0.1:55433`; the first sandboxed attempt therefore produced fixture setup connection
errors, not application failures. A forced SQLite attempt also hung while entering Starlette's
`TestClient` under that sandbox. The authorized PostgreSQL run above is the meaningful result.

The two backend warnings are the existing Starlette `anyio.abc.BlockingPortal` deprecation.

## Remaining release work

The implementation is locally complete, but the code commits form a new release candidate.
Prior candidate-specific independent review, deployment evidence and production confirmation do
not transfer to it. Re-run the repository's independent release review against this exact head
before changing any release gate.

Do not deploy this work or turn on a collector. Production still runs the older flat-layout
installation, providers are disabled, the database role split is not installed, and monitoring
is not installed. Those facts are blockers, not invitations to bypass the release contract.
