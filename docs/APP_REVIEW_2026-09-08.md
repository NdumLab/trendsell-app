**TrendSell application review — 8 September 2026**

Reviewed checkout: `59414e5`. This was an assessment, not an implementation pass. Application source, production data, and deployment configuration were not changed. Browser and API mutation checks used an isolated local server and a disposable SQLite database in `/tmp`.

**Assessment**

TrendSell has a coherent product direction: investigate a product for the China → Nigeria corridor, distinguish evidence from assumptions, calculate unit economics, and preserve decisions. The deliberate refusal to manufacture demand data is a strength.

Today it is principally a manual research notebook and scenario calculator. The observation pipeline, compliance-review workflow, and monitoring needed to fulfill the evidence-to-decision promise do not exist yet. That is disclosed in the current README, but the breadth of the interface and older roadmap make the product appear further along than its working capabilities.

I would fix the integrity and reliability issues below before broadening the pilot, then complete one useful evidence workflow before adding more screens.

**What I verified**

| Check | Result |
| --- | --- |
| Backend redesign suite | 109 passed; sandbox restrictions required rerunning outside the sandbox with disposable test databases |
| Frontend unit/contract tests | 50 passed |
| TypeScript and production build | Passed; main JavaScript bundle 735.93 kB, 224.63 kB gzip |
| Browser route smoke checks | Ten routes at 1440px and 390px; no page exceptions or document-level horizontal overflow in the tested demo states |
| Browser behavior | Reproduced stale exports, incorrect historical evidence attachment, and supplier-price rounding |
| API behavior against one shared test database | Cross-workspace reads/writes denied in tested cases; reproduced concurrent-request failure, product truncation, body-limit bypass, and validation defects |
| `npm audit --json` | Zero reported vulnerabilities in the active frontend dependency tree |
| `pip-audit -r backend/requirements.txt --strict` | Failed: one reported vulnerability in `pytest==9.0.2` |
| `npm run test:e2e -- --list` | Failed; Playwright tries to load Vitest files and discovers no browser tests |
| Credential-pattern scan | No matches in tracked files or the five locally reachable commits; this is a pattern scan, not proof of credential revocation or exhaustive secret detection |
| Live deployment, read-only | HTTPS homepage and API health returned 200; production settings use PostgreSQL; deployed `main.py` and `db.py` match the checkout |

The deployed site has CSP, HSTS, frame protection, secure-cookie configuration, a loopback API listener, and a restricted systemd service. I found no confirmed cross-workspace disclosure in the checks performed. Production database recovery, infrastructure outside this host, and authenticated production workflows were not exercised.

**Fix first: decision integrity and reliability**

1. **High — an export can disagree with the decision currently displayed.**

   After saving a scenario, changing import status to `prohibited` updates the displayed verdict but leaves `saved` intact. The export button still downloads the previous assessment. Browser reproduction: the screen showed `NO-GO`, while the downloaded JSON contained `WATCH` and `compliance: unresolved`. The reproduction used demo data; the same state/export code handles real workspaces. Shipping and channel changes also fail to invalidate the saved-state indicator.

   Invalidate the saved reference whenever any input changes, or explicitly separate “export current draft” from “export saved snapshot.” Make the selection visible and test both paths.

   Evidence: [DecisionRoom.tsx](/root/trendsell-app/frontend/src/features/DecisionRoom.tsx:38), export selection at line 46.

2. **High — historical decision exports attach evidence from the currently selected product.**

   `exportDecision(a)` adds `product?.observations` from the open editor instead of the saved assessment. Reproduction: save the steamer, select the blender, then download the steamer from history. The JSON identifies `demo-steamer` and observations `d1/d2`, but its evidence array contains blender observation `d4`. Production observations are currently empty, so the populated-evidence failure is demonstrated in demo; this becomes a real lineage defect as soon as collection is enabled. The exporter also overwrites the saved threshold version with a current constant.

   Export a self-contained immutable assessment with its original evidence snapshot and versions. Never reconstruct historical provenance from current screen state.

   Evidence: [DecisionRoom.tsx](/root/trendsell-app/frontend/src/features/DecisionRoom.tsx:30), history download at line 48.

3. **High — older products silently disappear from the app and workspace exports.**

   The products API reads only the newest 200 rows, then applies search in Python. The frontend uses this list for product details, selectors, counts, and exports. With more than 200 products, the oldest test product disappeared from the list and search while its direct API URL still returned 200. Its UI detail view will report “Investigation not found.” Workspace export will omit it, although related decisions, quotes, and watches may remain.

   Add server-side filtering and pagination with an explicit total; load details directly by ID. Generate complete exports independently of the currently loaded page. Paginate the unbounded decision, quote, and watch collections too.

   Evidence: [main.py](/root/trendsell-app/backend/app/main.py:195), [Products.tsx](/root/trendsell-app/frontend/src/features/Products.tsx:22), [Operations.tsx](/root/trendsell-app/frontend/src/features/Operations.tsx:40).

4. **High — concurrent idempotent requests can return HTTP 500.**

   Six simultaneous X-Ray submissions with the same input and idempotency key produced one 500 and five 202 responses in the isolated SQLite deployment. `insert()` flushes before `queue_job()` reaches its `try/except IntegrityError`, so unique-key races escape the intended handler. Decisions and watch creation have similar read-then-insert patterns. The frontend also generates a new idempotency key for each save attempt, losing protection when retrying after an ambiguous timeout.

   Enclose all affected reads/inserts/flushes in the appropriate transaction/retry strategy, return the existing result for a matching key, and retain a request key through retries. Add concurrent tests against PostgreSQL; the observed 500 was reproduced on SQLite, not production.

   Evidence: [main.py](/root/trendsell-app/backend/app/main.py:129), queue flow at line 221; [Workspace.tsx](/root/trendsell-app/frontend/src/shared/Workspace.tsx:63).

5. **Medium — client and server money calculations are not fully equivalent.**

   Shared fixtures pass, but an additional valid input exposes different rounding: quantity 1, supplier cost 10.075, FX 1, zero freight/taxes/fees/budgets, selling price 100, stress 0. Python reports supplier cost `10.08`; JavaScript reports `10.07`. Adding `Number.EPSILON` does not make floating-point rounding match Python's decimal conversion for all accepted values.

   Define decimal input precision and rounding rules, use consistent decimal arithmetic or scaled integers, and add cases around half-cent and decision thresholds. A formula-version string and a small fixture set alone do not establish parity.

   Evidence: [economics.ts](/root/trendsell-app/frontend/src/lib/economics.ts:3), [economics.py](/root/trendsell-app/backend/app/economics.py:27).

6. **Medium — supplier prices lose their cents on screen.**

   A saved USD 8.40 quote displays as `US$8`. The shared formatter forces zero decimal places for every currency, including detailed quote comparisons and supplier-cost targets. The stored amount is correct; the visible amount is misleading.

   Use currency-appropriate precision for quotes and per-unit economics; reserve compact rounding for summary cards.

   Evidence: [utils.ts](/root/trendsell-app/frontend/src/lib/utils.ts:4), [Operations.tsx](/root/trendsell-app/frontend/src/features/Operations.tsx:33).

7. **Medium — saved assessments and product summaries diverge.**

   Saving a prohibited-product assessment returns `NO-GO`, but the product still reports `INSUFFICIENT EVIDENCE` and a generic evidence-collection blocker. Discover and Watchtower read that unchanged product verdict. The issue is ambiguous meaning: a product evidence status and a user's commercial assessment are presented as if they were one decision.

   Display the latest applicable saved assessment, including its scenario, date, and prohibition, separately from evidence coverage. Do not silently overwrite immutable history or turn subjective inputs into observed facts.

   Evidence: [main.py](/root/trendsell-app/backend/app/main.py:279), [Products.tsx](/root/trendsell-app/frontend/src/features/Products.tsx:27), [Operations.tsx](/root/trendsell-app/frontend/src/features/Operations.tsx:26).

**Security and account management**

8. **Medium — a known vulnerable test dependency is pinned and installed in production.**

   The Python scan reports `CVE-2025-71176` / `GHSA-6w46-j5rx-g56g` for `pytest==9.0.2`, involving local temporary-directory handling. Pytest's official changelog records the fix in 9.0.3. This is a local/test-execution risk; it does not establish a remotely exploitable FastAPI route. The same version is installed in `/opt/trendsell/venv`, and the repository's configured dependency-scan command fails today.

   Update to a patched version and separate development/test requirements from runtime requirements. Lock transitive Python dependencies as well as direct ones. Source: [pytest 9.0.3 release notes](https://docs.pytest.org/en/stable/changelog.html#pytest-9-0-3-2026-04-07).

   Evidence: [requirements.txt](/root/trendsell-app/backend/requirements.txt:9), [CI workflow](/root/trendsell-app/.github/workflows/ci.yml:114).

9. **Medium — password hashing needs stronger parameters and an upgradeable format.**

   Passwords are salted and hashed with scrypt, which is a sound foundation. The parameters are `N=16384, r=8, p=1`, below OWASP's recommended scrypt configurations. Stored hashes contain only salt and digest, so simply changing the constants would invalidate existing passwords.

   Introduce algorithm/parameter metadata, retain legacy verification, and rehash on successful login using a benchmarked stronger configuration or Argon2id. Source: [OWASP password storage guidance](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html).

   Evidence: [security.py](/root/trendsell-app/backend/app/security.py:11).

10. **Medium — account recovery and abuse controls are incomplete.**

    Public registration is enabled in the deployed configuration. There is no email verification, password reset/change, session-management screen, member invitation, or account deletion flow. A user who loses their password has no self-service recovery path. The only authentication quota combines login and registration into 20 requests per IP per hour; it can inconvenience shared networks and does not provide an account-specific limit against distributed guessing. Expired sessions and obsolete rate buckets have no cleanup path.

    Add verified recovery and session revocation, tune IP plus account limits, and expire operational records. Handle 401 centrally by clearing workspace caches and prompting sign-in; currently the client hides 401 errors from the shared error banner and does not invalidate authentication state on arbitrary API failures.

    Evidence: [main.py](/root/trendsell-app/backend/app/main.py:156), [api.ts](/root/trendsell-app/frontend/src/lib/api.ts:11), [Workspace.tsx](/root/trendsell-app/frontend/src/shared/Workspace.tsx:48), [db.py](/root/trendsell-app/backend/app/db.py:61).

11. **Lower immediate risk — the API request-size check trusts the header.**

    A 40,032-byte chunked JSON confirmation request returned 200 despite the intended 32 KiB limit. Checking `Content-Length` alone does not count streamed bytes. The deployed nginx configuration independently caps API bodies at 64 KiB, materially limiting the current exposure; the direct-backend reproduction does not prove unlimited public uploads.

    Enforce a byte limit while reading the body and align proxy/application limits. Source: [OWASP denial-of-service guidance](https://cheatsheetseries.owasp.org/cheatsheets/Denial_of_Service_Cheat_Sheet.html).

    Evidence: [main.py](/root/trendsell-app/backend/app/main.py:91), [nginx configuration](/etc/nginx/sites-available/trendsell.yerikasystems.com:45).

12. **Low — validation permits blank confirmed names and unusable supplier links.**

    Confirming a name of two spaces returns 200 and stores an empty name because length validation happens before trimming. A supplier quote with `source_url: "https://"` returns 201 because validation checks only the prefix. Similar trimming should apply to workspace and supplier names.

    Normalize before validating and use an actual HTTPS URL type. The current code does not fetch these supplier URLs, so this is not a demonstrated SSRF finding.

    Evidence: [main.py](/root/trendsell-app/backend/app/main.py:38), quote schema at line 49, confirmation at line 266.

**Testing and operations**

13. **High assurance gap — existing tenancy tests use separate databases.**

    `settings()` uses `sqlite://`, and `second_workspace()` constructs a second app/engine. Each engine owns a separate in-memory database. Foreign IDs naturally return 404 even if tenant filtering were removed. I independently tested two users against the same local server/database: the tested product, evidence, job, decision, quote, watch, and mutation boundaries held. The finding is inadequate regression coverage, not observed data leakage.

    Share the app/database while separating cookie jars. Assert the owner's record exists before making the unauthorized request, and cover all record types with PostgreSQL integration tests.

    Evidence: [conftest.py](/root/trendsell-app/backend/tests/redesign/conftest.py:19), second client at line 40.

14. **Medium — browser testing is declared but absent.**

    The E2E script has no Playwright configuration or browser test suite. Test discovery runs the Vitest files under Playwright, throws configuration errors, and finishes with zero tests. CI only exercises pure frontend functions and builds, which explains why export and UI-state defects escaped.

    Configure a separate browser test directory and disposable server/database. Cover registration/login, capture → confirmation → decision → watch, quote recording, saved/draft exports, session expiry, and switching products/demo modes. Check a small essential set in CI.

    Evidence: [package.json](/root/trendsell-app/frontend/package.json:16), [CI workflow](/root/trendsell-app/.github/workflows/ci.yml:34).

15. **High operational gap — deployment is not reproducible from the repository.**

    Production deliberately skips `create_all()`, but there are no Alembic configuration/revisions in the repository. The host has an external `/opt/trendsell/bootstrap_schema.py` that creates tables once. That makes the current deployment work but provides no tracked upgrade path. Service/nginx setup is also outside the repo. I did not find a TrendSell backup/restore runbook or app-specific scheduled backup in the inspected locations; host/provider backups could exist and were not verified.

    Track deployment configuration and migrations, verify schema state at readiness, document rollback, and prove a backup can restore into a separate database before relying on retained customer research. The existing `SELECT 1` health check establishes connectivity, not schema readiness or recovery capability.

    Evidence: [main.py](/root/trendsell-app/backend/app/main.py:65), [bootstrap_schema.py](/opt/trendsell/bootstrap_schema.py:1), [systemd service](/etc/systemd/system/trendsell.service:1).

16. **Medium before enabling collection — job recovery is unsafe for multiple workers.**

    Each worker's startup scans every historical job and marks all queued/running jobs interrupted. The live service uses two API workers. Starting one worker can therefore mark a job owned by another worker interrupted. Today's job merely appends unavailable-source events, so the immediate effect is limited; real, longer-running collection would expose the design flaw. Background tasks are not a durable queue, and the SSE endpoint emits a snapshot then closes.

    Before connecting collectors, add durable job ownership, leases/timeouts, retries, and bounded recovery of abandoned jobs. Choose polling or a real live event stream deliberately. Avoid converting every worker startup into a global job rewrite.

    Evidence: [main.py](/root/trendsell-app/backend/app/main.py:69), background execution at line 239, event endpoint at line 255; [systemd service](/etc/systemd/system/trendsell.service:14).

**Product gaps and additions I would prioritize**

| Addition | Reason |
| --- | --- |
| One approved demand collector with immutable raw snapshots and normalized observations | Supplies the currently missing foundation for timelines, freshness, and evidence confidence |
| A way to attach dated manual evidence and record review decisions | Gives users a path forward while connectors are incomplete; user submissions must retain their own truth state |
| A reviewed compliance workflow | The real API always uses absent evidence and never resolves compliance; favorable economics alone can currently produce neither GO nor WATCH |
| “Use this quote in Decision Room” with a quote/version reference | Quotes currently sit beside the calculator without feeding it; preserve currency, MOQ, date, validity, and Incoterm context |
| Save/resume drafts and reopen a saved scenario as a new draft | Switching products resets values; historical decisions can be downloaded but not reopened for editing as a new version |
| Archive products and supersede/edit quotes with history | Mistaken or abandoned investigations and outdated quotes currently accumulate with no practical lifecycle |
| Clear next actions tied to each blocker | Many screens direct users to Data Health, which only explains missing connections and cannot resolve them |
| More complete cost assumptions | Make treatment of delivery, packaging, insurance, clearing costs, payment terms, and quote inclusions explicit, even if initially entered manually |

I would keep decision confidence and commercial feasibility visibly separate. A negative-margin scenario can currently still receive `INSUFFICIENT EVIDENCE` because that gate runs before the margin rejection. Showing “economics fail under these assumptions” alongside “demand unverified” communicates both facts without inventing evidence.

**What I would simplify or remove**

- Move Market Gaps and nonfunctional monitoring deeper into the pilot navigation until they can perform useful work. Keep a compact capability/coverage page. Rename Watchtower to a saved watchlist while scheduling is unavailable.
- Replace “No alerts” / “Quiet, for the right reason” with “Monitoring unavailable.” The top notice is honest, but the empty feed still suggests the absence of observed changes.
- Archive or clearly supersede the root `FEATURES_ROADMAP.md`, `memory/PRD.md`, and old test notes. They prioritize Viral Video Spy, Store Spy, synthetic intelligence, and multi-market breadth, conflicting with the active rebuild. The redesign plan explicitly called for an observation pipeline before Decision Room; implementation has built much of the interface ahead of that foundation.
- Remove unused `App.css`, dead utility imports, and dependency wrappers where unused. Keep the prototype visibly isolated; do not restore its synthetic metrics to make the live app look populated.
- Format the dense source files and split routes/forms into reviewable modules. Several major screens are compressed into a few very long lines, making state dependencies and security review harder.
- Load charts and heavy feature routes on demand. All main screens, including Recharts, are eagerly imported into the roughly 736 kB main bundle. The mobile layout works in the smoke checks, but Decision Room requires a long scroll from inputs to outcomes; a compact sticky verdict would help.
- Improve demo consistency: all real products currently default to a steamer illustration; all demo search series reuse the same trajectory even when their headline values differ. Use neutral unknown-product art and coherent fixtures.

**Recommended sequence**

1. Fix export integrity, pagination, concurrency, monetary precision, and the failing dependency scan. Add focused regressions for the reproduced failures.
2. Repair shared-database tenancy coverage and browser tests; add account recovery, hash upgrades, tracked migrations, and a verified restore path.
3. Complete the useful core journey: capture → dated evidence → linked supplier quote → reviewed readiness → reproducible decision. Make the missing-evidence tasks actionable.
4. Enable monitoring only after durable collection and meaningful change detection work. Expand market discovery and creative intelligence after the core journey has demonstrated value.

Temporary audit evidence: `/tmp/trendsell-browser-findings.json`, `/tmp/trendsell-backend-findings.json`, `/tmp/trendsell-python-audit.json`, and desktop/mobile screenshots at `/tmp/trendsell-audit-1440.png` and `/tmp/trendsell-audit-390.png`. These are local review artifacts, not repository fixtures.
