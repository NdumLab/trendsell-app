# D02 truth and drift contract handoff

Prepared 4 October 2026 UTC on branch `impl/evidence-platform-phase0` from
checkpoint `4b36e1d`.

## Outcome

Action-plan item D02 is implemented and locally verified. It remains **in review** because
the landed-cost method has not received domain or independent release review, and this
candidate has not been deployed.

The engineering meaning of “do not hallucinate or drift” is now explicit in
[`../TRUTH_AND_DRIFT_CONTRACT.md`](../TRUTH_AND_DRIFT_CONTRACT.md). This does not claim that
a user entry or third-party statement is correct. It ensures the software labels its
authority, preserves the exact basis used, does not silently strengthen missing data, and
does not change historical calculations under a newer method.

## Implemented boundary

- Current calculations use `unit-economics/1.2.0` and `landed-cost/2.0.0`.
- New assessments require explicit packaging, international freight, insurance, clearance,
  local delivery, duty/tax, channel/payment fees, returns, FX buffer, reserve, supplier
  deposit and cash-timing values. Zero is accepted only when it was actually submitted.
- The application supplies no fallback FX, freight, customs or regulatory rate.
- New assessments must name their sales channel and freight mode; omitted route labels no
  longer become “Direct sales” or “Air.” Missing quote Incoterms remain unknown, and generic
  unit prices require an explicit currency.
- Each saved formula cost input carries its value, unit, `User input` truth state, author,
  recorded time and source label. The landed-cost basis and missing-cost policy are saved
  with the assessment.
- Supplier quotes carry an explicit included-cost list. An omitted list from an older
  client/record remains `not recorded`; only an explicitly submitted empty list means none.
  Incoterms never imply inclusion. Known separate-input duplicates are rejected by the
  server, and the browser disables only lines the quote explicitly includes.
- The Decision Room exposes the added cost and cash-timing fields, displays every waterfall
  line, labels demo assumptions, and invalidates saved-export state whenever route or inputs
  change.

## Drift controls

`scripts/generate_economics_contract.py --check` reproducibly verifies the committed current
contract. Backend and browser implementations independently replay every current case.
`contracts/economics_v1_1_cases.json` and `contracts/economics_legacy_cases.json` freeze the
superseded 1.1 and 1.0 behavior, so current changes cannot rewrite historical assessments.
Tests also fail if a formula cost input lacks a lineage definition.

The quote-inclusion representation deliberately distinguishes three states:

1. a named cost is explicitly included;
2. an explicit empty list says none of the named costs is included; and
3. a missing legacy list is unknown and produces a warning.

## Verification

The complete candidate passed on 4 October 2026:

```text
python scripts/generate_economics_contract.py --check
  PASS
python -m compileall -q backend/app scripts/generate_economics_contract.py
  PASS
backend/tests/redesign/test_contract_parity.py
  125 passed
backend/tests/redesign/test_decisions_and_records.py (PostgreSQL)
  31 passed
full backend suite (PostgreSQL)
  665 passed
npm --prefix frontend test -- --run
  5 files, 160 tests passed
npm --prefix frontend run typecheck
  PASS
npm --prefix frontend run build
  PASS
npm --prefix frontend run test:e2e
  55 Chromium tests passed
git diff --check
  PASS
```

The backend warnings are the existing Starlette `anyio.abc.BlockingPortal` deprecation.
PostgreSQL and browser verification use disposable loopback services; no production data or
provider credential is involved.

## Residual boundary and next work

Passing tests establishes the behavior above, not the correctness of a supplier statement,
FX input, tariff assumption or market opportunity. A qualified domain reviewer must still
review the landed-cost basis and user-facing language. The exact candidate also needs the
normal independent release review before any deployment decision.

No provider was enabled, no credential was installed, and no deployment or production
mutation was performed. Gate D remains planned because real local evidence and the complete
investigation journey are not finished. The next unblocked engineering item is D04:
resumable/versioned drafts, copying a saved assessment into a new draft, and product
archive/restore without weakening immutable history.
