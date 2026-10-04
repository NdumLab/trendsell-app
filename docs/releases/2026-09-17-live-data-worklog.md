# Live-data implementation worklog

Last updated: 2026-09-18 UTC

## Objective

Finish every unblocked part of the narrow live-data pilot without changing production. The release candidate must use explicit Data Health states, support keyword discovery through evidence and economics, enforce provider retention at access time, pass focused and mandatory release checks, and be committed and pushed for successor CI review.

TrendSell is **not** live-data ready until authorized real observations are collected and displayed in production. Freight, regulatory collection, advertising/creator signals, observed sales, and sales attribution remain outside this narrow candidate and explicitly outstanding.

## Current checkpoint

- [x] Replace prose Data Health matching with typed configuration, collection, observation-storage, and API-availability states.
- [x] Add request-time provider-data expiry and historical-assessment redaction with tests.
- [x] Connect keyword discovery to the frontend and carry candidate lineage into investigation.
- [x] Add focused backend and fixture-labelled browser coverage for discovery, evidence display, economics, errors, and incomplete matches.
- [x] Correct provider pricing/rights/retention documentation against current first-party sources.
- [x] Run focused integration/browser checks and all mandatory application checks.
- [ ] Create reviewable commits and push the branch.
- [ ] Capture the successor CI run and exact release artifact; leave production unchanged.

## Resume notes

Branch: `impl/evidence-platform-phase0`

The implementation and documentation are ready for the first reviewable checkpoint commit. Inspect `git status --short` before editing and preserve unrelated user work. The invalid prose `display_status` contract has been replaced with typed fields; tests assert that the removed prose fields do not reappear.

Browser fixtures are test evidence only. They must be labelled as fixtures and must never be reported as live collection.

## Evidence log

- Focused backend integration after retention hardening: `32 passed` (`test_xray_and_jobs.py`, `test_amazon_creators_provider.py`, `test_live_source_providers.py`).
- Full SQLite backend suite after final implementation edits: `609 passed`, 3 dependency deprecation warnings.
- Frontend: typecheck passed, `141` unit tests passed, and the production build passed.
- Fixture-labelled browser keyword-to-economics check: `1 passed`; this is test evidence only, not live-data proof.
- Focused browser regression rerun: `5 passed`.
- Fresh full browser run: `54 passed` in 3.7 minutes, including visible evidence, typed Data Health, economics and honest WATCH/insufficient-evidence behavior. The provider calls in this suite are deterministic local fixtures, not live observations.
- Dependency and license checks completed before the final browser run: Python runtime and development audits reported no known vulnerabilities; npm audit reported 0 vulnerabilities; 181 locked packages passed the license policy.
- `git diff --check` and the stale prose-contract/pricing scan pass at this checkpoint.
- Next resume action: commit and push this checkpoint, capture the successor CI run and exact release artifact, and leave production unchanged. If CI fails, correct the implementation in a new reviewable commit and follow the new successor run.
