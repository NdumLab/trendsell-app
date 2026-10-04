# Truth and drift contract

This is the engineering meaning of “TrendSell must not hallucinate or drift.” It is a
release invariant, not a claim that stored user input or a third-party source is correct.
The application preserves what a source or person said, labels its authority, and refuses
to strengthen that statement without evidence.

## Truth boundary

1. Missing, expired, failed or unauthorized evidence is **Unavailable**. It is never zero,
   falling demand, low competition, a favorable rate or a completed review.
2. **Observed** means a named collector produced a retained, dated observation with source,
   version and snapshot lineage. Configuration or a successful health check is not an
   observation.
3. **User input** remains user input, including supplier claims, FX, freight, costs and
   manually transcribed market evidence. It cannot silently become Observed.
4. **Calculated** output is deterministic and retains its exact inputs, method and version.
   A calculation is not a market fact or forecast.
5. **Demo** data stays in the opt-in browser demo namespace and cannot support a production
   assessment. Production has no synthetic fallback.
6. An association is not sales or causation. A candidate identifier is not a confirmed
   product. An Incoterm is not proof of cost inclusion. A confidence score is not a
   probability.
7. The server alone computes evidence coverage, compliance state and decision gates from
   authorized workspace records. The browser cannot assert them.

## Commercial-assumption boundary

- Every current landed-cost line must be submitted explicitly; zero means the user stated
  that the separate cost does not apply. Omission is rejected.
- New assessments must also submit their sales channel and freight mode; the API cannot
  turn an omitted route into “Direct sales” or “Air.”
- Every saved cost line receives a user/source label, author and recorded time.
- A selected quote retains its original amount, currency, date, supplier, immutable
  revision and explicit included-cost list.
- An omitted inclusion list remains **not recorded**; only an explicitly submitted empty
  list means that none of the listed cost categories is included.
- An omitted Incoterm remains **not recorded**, and a generic unit price must name its
  currency. The legacy `unit_price_usd` field is already unambiguously USD.
- Separate inputs for costs explicitly included in a quote are rejected as double counts.
  No inclusion is inferred from CIF, DDP or another Incoterm.
- Air/sea mode and FX values are scenario inputs. Changing a label never inserts a freight
  quote, FX rate, transit time or regulatory rate.

## Anti-drift controls

| Boundary | Enforced by |
| --- | --- |
| Browser/server decision arithmetic | `contracts/economics_cases.json`, replayed independently by both test suites |
| Historical decisions | Frozen `economics_v1_1_cases.json` and `economics_legacy_cases.json`; formula and gate versions are saved |
| Contract regeneration | `scripts/generate_economics_contract.py --check`; CI fails when the committed current contract is stale |
| Cost-model version | The shared contract pins `landed-cost/2.0.0` on both server and browser |
| Cost provenance | The API snapshots every formula cost input into `cost_lineage`; a test requires complete field coverage |
| Quote double counting | Explicit quote inclusion mapping plus server-side rejection; the UI disables only explicitly included lines |
| Evidence scoring | Shared evidence cases and server-computed gates; self-reported evidence remains capped |
| Immutable history | Assessments snapshot inputs, outputs, evidence/review/quote references and all method versions |
| Demo separation | Demo fixtures load only in opt-in browser state; the retired prototype endpoint returns `410` |
| Growing collections | Server pagination/export contracts prevent a loaded page from masquerading as the whole workspace |

Changing a method requires a new version, new shared cases, frozen replay of the superseded
version, updated user-facing basis text, and review of every export/restore path. Do not
rewrite a frozen contract to make a new implementation pass.

## Release language

Reports and release notes must distinguish implemented, fixture-tested, independently
reviewed, deployed and observed-live. Passing tests proves the tested software behavior; it
does not prove provider rights, source correctness, a production deployment, domain-review
approval, or a real market opportunity.
