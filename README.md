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
pilot enforces and stores, and what it does not.

---

## The evidence rule

Every value carries a truth state, and the interface shows it beside the number:

| State | Meaning |
| --- | --- |
| **Observed** | Returned by a named source, stored with a raw snapshot |
| **Calculated** | Deterministic transformation of observed or user-provided inputs, with a formula version |
| **Estimated** | Inferred from partial evidence, shown as a range with its method |
| **User input** | Entered by someone in the workspace, stored separately from observed facts |
| **Unavailable** | No trustworthy observation for this source, window and market |
| **Demo** | A synthetic fixture, only inside an explicitly labelled demo workspace |

Consequences that are enforced, not aspirational:

- No production route returns invented revenue, ROAS, view counts, competitor strength or trend scores.
- A refresh with no new observation produces no score change.
- A failed collector lowers confidence; it never reads as falling demand.
- Missing chart points stay as gaps and are never interpolated.
- `GO` requires resolved compliance and confidence ≥ 70, regardless of how good the margin looks.

## What is in the pilot

| Area | State |
| --- | --- |
| Product X-Ray | Amazon US URL or ASIN → identifier capture, research job, user confirmation |
| Proof of demand | Timeline and evidence ledger, driven by observations; empty until a collector is connected |
| Decision Room | Editable unit economics, three scenarios, cost waterfall, sensitivity, saved assessments |
| Watchtower | Watches and materiality thresholds; scheduled collection and delivery are **not** enabled |
| Suppliers | User-recorded quotes and RFQ drafts; nothing is sent on your behalf |
| Data Health | Every source, its status, rights, freshness target and reason for being unavailable |
| Market Gaps | Corridor view that reports insufficient evidence rather than an untapped opportunity |

Image, video and keyword capture, live collectors, alerts and Creative DNA are later phases.
Follow [docs/ACTION_PLAN.md](docs/ACTION_PLAN.md) for implementation order.
`TrendSell_Complete_Redesign_Plan-1.docx` remains the broader product-vision reference.

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

CI runs backend tests, frontend type-check/tests/build, a clean-clone build, a secret scan and a
dependency scan on every pull request.

## Demo workspace

The demo is opt-in, stored only in the browser under its own namespace, and every value inside it is
labelled `Demo`. It never reaches the API, and no production route can load it.
