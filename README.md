# TrendSell — evidence-backed opportunity decisions

> Paste a product identifier. See what the evidence supports, what it costs to land in your market,
> and what is still missing — with the source behind every value.

TrendSell turns a product idea into a reproducible **GO / WATCH / NO-GO** decision for one import
corridor: **China → Nigeria**, with Amazon US and search demand as discovery inputs. It is not a
list of "winning products". Where evidence does not exist, TrendSell says so instead of estimating.

This repository was rebuilt from a synthetic-data prototype. The prototype is preserved, unbuilt and
unimported, under [`prototype/`](prototype/README.md); its numbers were seeded, not observed.

The current implementation roadmap is the [detailed action plan](docs/ACTION_PLAN.md), combining
the [September 2026 application review](docs/APP_REVIEW_2026-09-08.md) and product-capability review.
It defines work items, dependencies, acceptance checks, and release gates; planned features are not
claims about what this release already supports.

Operational and policy documents: [runbook](docs/RUNBOOK.md) for schema, release, rollback and
recovery; [permissions, privacy and retention](docs/PRIVACY_AND_PERMISSIONS.md) for what the
pilot enforces and stores, and what it does not; [production readiness](docs/PRODUCTION_READINESS.md)
for the current deployment decision and unresolved owner actions.

## Selected release tier

TrendSell is scoped as a **free, invitation-only controlled pilot**. Production uses
`RELEASE_TIER=controlled_pilot` with `ALLOW_REGISTRATION=false`; existing workspace owners admit
the small approved cohort through email-bound, single-use invitations. There is no billing or
public sign-up in this tier. Selecting this scope does not override the remaining approval and
operational gates in the [production-readiness checklist](docs/PRODUCTION_READINESS.md).

---

## The evidence rule

Every value carries a truth state, and the interface shows it beside the number:

| State | Meaning |
| --- | --- |
| **Observed** | Returned by a named source, stored with a normalized snapshot and response hash |
| **Calculated** | Deterministic transformation of observed or user-provided inputs, with a formula version |
| **Estimated** | Inferred from partial evidence, shown as a range with its method |
| **User input** | Entered by someone in the workspace, stored separately from observed facts |
| **Unavailable** | No trustworthy observation for this source, window and market |
| **Demo** | A synthetic fixture, only inside an explicitly labelled demo workspace |

Consequences that are enforced, not aspirational:

- No production route returns invented revenue, ROAS, view counts, competitor strength or trend scores.
- A refresh with no new observation produces no score change.
- A failed collector is recorded as unavailable/degraded; it never becomes a zero value or falling demand.
- Missing chart points stay as gaps and are never interpolated.
- `GO` requires compliance resolved **by a reviewer** and confidence ≥ 70, regardless of how good the margin looks.
- Confidence is an evidence-coverage score, not a probability, and every component of it is shown.
- Evidence you type is user input: it counts, but it is capped below the confidence a `GO` needs.
  Only a connected, authorised collector can raise it further. Selected commercial adapters remain
  disabled until provider credentials and a recorded accepted-terms/plan/intended-use basis are
  installed; configured keys, authentication and fixtures do not count as live collection.

## What is in the pilot

| Area | State |
| --- | --- |
| Product X-Ray | Amazon US URL, ASIN or keyword → candidate selection → exact-ASIN resolution and a user-requested multi-source job. When separately authorised, DataForSEO resolves exact-ASIN identity/current offer and Nigeria search interest, Bright Data supplies Jumia candidate listings, and Open Exchange Rates supplies dated reference pairs. A keyword candidate is not a confirmed exact product match; unavailable sources remain unavailable |
| Evidence ledger | Manual records remain **User input**. Authorised provider responses are separately **Observed**, with source/check URL, provider and collection time, snapshot/hash, parser/collector versions, use-rights reference and expiry |
| Sales drivers | Product-level advertising, creator, search and marketplace evidence. Signals are presented as association, never causal attribution; absent spend, ROAS, revenue, seller count and sales history stay unavailable |
| Evidence coverage | A versioned, explainable score (`evidence-quality/1.1.0`) with a component-by-component breakdown. Self-reported evidence is capped below the confidence a GO needs |
| Import readiness | Request a review, and a workspace reviewer approves, rejects or asks for more. An approval cites its official sources and expires. A dropdown cannot clear this gate |
| Decision Room | Editable unit economics, three scenarios, cost waterfall, sensitivity, saved assessments. A dated supplier quote can populate MOQ/cost and is snapshotted with explicit non-USD conversion. Coverage, confidence and compliance come from the server, not the browser |
| Watchlist | Saved watches and materiality thresholds. Scheduled collection and delivery are **not** enabled, and the screen says so |
| Suppliers | User-recorded quotes preserving original amount, currency, MOQ, terms, date, source and author; RFQ drafts are not sent on your behalf |
| Data Health | Every required source, with typed adapter, configuration, collection outcome, freshness, stored-observation and API-availability states. The API never claims browser display; browser tests and an authorised real-data check prove that separately |
| Market Gaps | Corridor view that reports insufficient evidence rather than an untapped opportunity |

Not enabled in the current production deployment, and not implied where unavailable: authorised
live catalog/search/Jumia/FX access, scheduled monitoring, alert delivery, billing, evidence-file attachments,
and image, video or keyword
capture. Password reset/change, session management, email verification, owner-managed team
invitations and member removal have browser screens. The release includes a TLS-enforced SMTP
transport, but a deployment still needs an approved provider, sending identity, DNS
authentication and delivery monitoring before those messages can reach real inboxes. See
[permissions, privacy and retention](docs/PRIVACY_AND_PERMISSIONS.md).

See the current [source feasibility and access register](docs/releases/2026-09-17-live-data-feasibility.md)
and [proposed live-data pilot](docs/releases/2026-09-17-live-data-pilot.md). TrendSell is not
live-data ready until real observations have been collected and displayed in production.

Image/video capture, scheduled collection, alerts and Creative DNA are later phases. Keyword
discovery is implemented for the selected DataForSEO pilot but remains disabled without access.
Follow [docs/ACTION_PLAN.md](docs/ACTION_PLAN.md) for implementation order.
`TrendSell_Complete_Redesign_Plan-1.docx` remains the broader product-vision reference.

Workspace export schema `trendsell-workspace-export/3` includes catalog source snapshots,
workspace-scoped source health, original-currency quotes, and quote snapshots/conversions on
saved decisions. Older saved assessments retain immutable formula inputs, calculations and
versions. Provider evidence payloads are removed at expiry and replaced in historical assessments
by explicit retention tombstones, so an expired observation cannot continue to appear usable.

## Architecture

| Layer | Choice |
| --- | --- |
| Frontend | React 19 + TypeScript + Vite, TanStack Query, Recharts, hand-authored CSS design tokens |
| API | FastAPI + Pydantic v2 + SQLAlchemy 2, cookie sessions, per-workspace scoping |
| Storage | SQLite for the pilot, PostgreSQL in production (`postgresql+psycopg://`) |
| Contracts | `contracts/*.json` — shared cases both the API and the frontend must reproduce |

```
backend/app/      main.py (routes) · db.py (models) · economics.py (decision maths) · security.py · settings.py
backend/tests/    redesign/ — auth, tenancy, X-Ray, jobs, decisions, contract parity
frontend/src/     features/ (Today, Xray, Products, DecisionRoom, Operations) · shared/ · lib/
contracts/        economics_cases.json · identifier_cases.json
prototype/        the retired synthetic prototype, kept for reference only
```

## Running it

```bash
# API — http://127.0.0.1:8001
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env          # then edit
uvicorn app.main:create_app --factory --port 8001

# Frontend — http://localhost:3000, proxying /api to 8001
cd frontend
npm ci
npm run dev
```

The service refuses to start when required settings are missing. `APP_ENV=production` additionally
requires a PostgreSQL `DATABASE_URL` and HTTPS-only `CORS_ORIGINS`; there is no wildcard origin.

No provider credentials are read in the browser, and no `VITE_*` variable may hold a secret.

## Tests

```bash
cd backend  && python -m pytest tests/redesign   # API, tenancy, jobs, decisions, contracts
cd frontend && npm test                          # decision contract, identifier contract, sensitivity
cd frontend && npm run typecheck && npm run build
```

`contracts/economics_cases.json` is asserted by both suites, so a change to the decision maths on
one side fails on the other. `contracts/identifier_cases.json` does the same for the inputs X-Ray
accepts — including the URLs it must refuse, since TrendSell never fetches a user-supplied address.

CI runs backend tests, frontend type-check/tests/build, reproducible clean-clone release builds,
dependency vulnerability/license policy checks, and redacting secret scans on every pull request.

## Demo workspace

The demo is opt-in, stored only in the browser under its own namespace, and every value inside it is
labelled `Demo`. It never reaches the API, and no production route can load it.
