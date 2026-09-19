# Proposed live-data controlled pilot

Prepared 17 September 2026 UTC; updated 18 September 2026 UTC. This proposal replaces the manual-only product scope. It does not
approve a provider, spend, policy, participant, production change or release. All existing
deployment, security, privacy, recovery, operational, accessibility, independent-review and
go/no-go gates remain mandatory.

## Product outcome

For a user-supplied keyword or Amazon US ASIN, TrendSell will collect current external evidence and answer:

1. **Which current products are candidates for this keyword?** Organic Amazon US results returned
   by DataForSEO, labelled as candidates rather than recommendations, sales or verified matches.
   The user selects one candidate before exact identity resolution.
2. **What product is this?** Exact selected-ASIN identity, current title/brand/current offer/rating fields
   returned by DataForSEO, with provider/check URL, provider observation time, collection time and
   retained snapshot reference.
3. **Is there current Nigeria search interest associated with this product query?** A 90-day
   DataForSEO Trends relative series for Nigeria, with the exact query and method. It is an
   indicator—not absolute search volume, observed sales or causation.
4. **Are candidate listings visible in one Nigerian marketplace query?** Bright Data Jumia results,
   ranked by transparent title/brand token overlap and labelled **candidate / human review
   required**. Counts describe the collected result only, not Jumia or Nigeria market coverage.
5. **What dated reference FX can inform a scenario?** Optionally, Open Exchange Rates USD/NGN and USD/CNY; any
   CNY/NGN value is explicitly calculated. Decision Room still treats the chosen rate as a user-
   approved assumption.
6. **Is there enough evidence to act?** No. Until freight, a real supplier quote, qualified import
   review and necessary local evidence exist, the decision remains `INSUFFICIENT EVIDENCE` or a
   user-saved `WATCH`; missing evidence cannot become an opportunity score.

This is bounded keyword discovery followed by user selection and product investigation—not
automatic opportunity ranking across an entire market. Broader discovery and continuous ranking
remain on the roadmap after the minimum DataForSEO + Bright Data pipeline proves coverage and use.

## Deliberate boundaries

| Evidence class | Pilot capability | Explicitly unavailable |
| --- | --- | --- |
| Catalog identity | Current keyword candidates followed by exact-ASIN current catalog response | Exhaustive Amazon discovery, automatic opportunity ranking, claim verification, image collection |
| Current pricing | Current Amazon offer/range and candidate Jumia listing prices | Historical price trajectory, complete offers, total Nigeria market price distribution |
| Demand indicators | Nigeria relative search interest; current review count as context | Observed units/revenue, review velocity until comparable repeat observations, causal demand-driver claims |
| Local market | Candidate results from one documented Jumia Nigeria query | All Jumia listings, other Nigerian channels, “low competition” or “market gap” conclusion |
| Economics | Existing transparent scenario formula using dated FX plus explicit user inputs | Live freight, duty/tax/classification, supplier cost verification, forecast or guaranteed margin |
| Sales | None | Competitor sales, merchant sales, refunds and conversion |
| Attribution | None | Ad/creator/search-to-sale attribution, spend, ROAS |
| Regulation | Linked official references plus existing qualified-review gate | Automated NAFDAC status, HS classification, tariff/legal opinion |

## Implemented candidate behavior

- Server-only DataForSEO catalog/Trends, Bright Data Jumia and Open Exchange Rates adapters.
- Three bounded attempts for network, rate-limit and 5xx failures; safe error classes contain no
  response body or credential.
- Provider/task timestamps, collection timestamps, check/source URLs, task IDs, parser/collector
  versions, response hashes, usage-basis reference, expiry and snapshot ID. Complete raw provider
  responses are hashed in memory and discarded; retained snapshots are field-limited and normalized.
- Deterministic product-candidate matching with score and human-review limitation; no equivalence is
  inferred.
- Content-addressed snapshot/evidence keys prevent retry duplication.
- Provider-specific configured retention intervals; expiry is enforced at startup and before every
  authenticated request. Expired evidence/snapshots, discovery runs and dependent product fields
  are removed. Historical assessments retain their inputs/economics but provider values become
  explicit expiry tombstones. Restores apply the same purge before serving data.
- Per-workspace Data Health uses explicit typed states for adapter implementation, configuration,
  latest collection, current stored observations and authenticated API availability. It makes no
  claim that API availability means a screen displayed the data; browser acceptance proves display.
- Real search series is selected for the user chart; chart rows retain their real truth state and
  source instead of the prior hard-coded demo label.
- Amazon Creators is excluded from orchestration. Its adapter remains only as isolated legacy code
  until removal/migration is separately approved.

Automated provider tests use fixtures and prove only parsing/orchestration. They are not live-data
evidence.

## End-to-end proof required before “live-data ready”

Run only after accounts, use rights, retention, spend and production change are approved:

1. Install server-side secrets and non-secret accepted-terms/plan/intended-use references; leave
   each `*_ENABLED` flag false until a redacted config review and formal internal approval pass.
2. In isolated production-like staging, enable one provider at a time; resolve US/Nigeria location
   codes from the authenticated provider endpoint and pin them. Run one bounded real keyword,
   select one result and collect its exact real ASIN.
3. Verify the product view shows the real identity and current offer with source URL, provider
   observation time, collection time and snapshot ID. Export the workspace and verify the same
   provenance, expiry and no credentials.
4. Verify the Nigeria search series shows its exact query and limits. Verify Jumia rows say
   “candidate” and show one-market/one-query coverage. A zero-result collection must say “zero in
   this collected result,” never “no competition.”
5. Verify FX source pairs and the calculated CNY/NGN formula. Enter an explicit supplier unit-cost,
   quantity, freight, duty, tax, channel fee, returns, marketing, fixed-cost and stress assumption.
   The saved assessment must preserve every input/formula version and say which values are user
   inputs versus source observations.
6. Confirm the verdict remains `INSUFFICIENT EVIDENCE` (or a user chooses `WATCH`) while qualified
   import review/freight/supplier evidence is absent. It must not become `GO` merely because catalog,
   search, local candidates and FX succeeded.
7. Exercise one authorized transient failure. Data Health must show latest attempt failed, retain
   the earlier success time, show freshness, and never create a zero/declining observation.
8. Let or force one test-policy expiry in staging. Confirm the live record, discovery run and
   dependent displayed fields disappear; the historical assessment must preserve inputs/economics
   but replace expired provider values with an expiry tombstone.
9. Deploy the exact checksum-verified candidate only after every mandatory release gate passes.
   Repeat steps 2–7 with a bounded production collection and a named pilot account.

Required evidence package: candidate SHA/artifact checksum; redacted provider plan/terms/intended-
use and internal approvals; exact ASIN/query; provider request IDs; source and snapshot URLs/IDs; provider observation
and TrendSell collection timestamps; product/evidence/Data Health screenshots or API exports; the
saved economics record; failure/freshness exercise; and named reviewer sign-off.

## Current proof state

The end-to-end proof is **BLOCKED, not failed**:

- no selected provider account/intended-use/internal approval or credentials have been authorized;
- the candidate is not deployed;
- production remains the older artifact with zero live observations; and
- purchasing, requesting secrets in chat, enabling collectors, or changing production would exceed
  current authority.

Therefore TrendSell is **not live-data ready**. Completion requires a real collection displayed in
production, not adapter tests, configured keys, authentication, demos or manual evidence.
