# TrendSell — AI-Powered Global Product & Sales Intelligence Dashboard

> Discover what's selling, why it's selling, and who to source it from — calibrated to **any** market in the world.

TrendSell is a full-stack e-commerce intelligence dashboard that surfaces trending products across TikTok Shop, Amazon, Shopify, Mercado Libre, Jumia, Shopee, Flipkart and 40+ other marketplaces — and unpacks the exact stack of apps, ads, and platforms driving each breakout. Every score, price, competitor, and platform recommendation recalibrates the moment you switch the country selector.

---

## Screenshots

> _Add screenshots after cloning: dashboard.png, product-detail.png, compare.png, watchlist.png_

- `/docs/dashboard.png` — Main dashboard with local KPIs and 7-week trajectory chart
- `/docs/product-detail.png` — Tabbed deep-dive: Overview / Sales & Ads / Sourcing & Profit / Intelligence
- `/docs/compare.png` — Side-by-side head-to-head comparison
- `/docs/watchlist.png` — Persisted watchlist with score-delta badges

---

## Features

### 🌍 Location-Aware Intelligence (46 countries)
- **Country selector** in the header — Americas, Europe, Africa, Middle East, Asia, Oceania
- **Local vs Global trend scores** per product, with badges for `🌍 Local Hidden Gem` and `🚀 Untapped in [Country]`
- **PPP-adjusted pricing** — real purchasing-power translation (`$29.99 → ₦18,000 / ₹1,499 / R$89`), not raw FX
- **Local platform rankings** — country-specific marketplaces (Jumia, Noon, Trendyol, Shopee, Mercado Libre, Coupang, etc.)
- **Local competitor overrides** for India, Nigeria, Brazil, Indonesia, UAE and more
- **Landed cost calculator** — air vs sea freight, import duties, customs, lead times, all in local currency
- **Regulation flag** per category × country — 🟢 Clear / 🟡 Cert Required / 🔴 Restricted (FCC, CE, BIS, Anatel, NAFDAC, CCC, PSE …)

### 🧠 AI & Intelligence
- **AI Market Brief** — 1-page report with exec summary, opportunity, competition, ROI, risks, action items (Gemini 3 Flash Preview)
- **AI Niche Finder** — 5 untapped sub-niches per product with competition ratings
- **AI-refreshed trend scores** — the "Refresh Data" button re-scores products with fresh reasoning
- **"Why it's trending" AI explanation** on every card

### 📈 Sales & Sourcing
- **Trend velocity** with color-coded arrows (▲▲ surging / ▲ climbing / ▬ flat / ▼ declining)
- **Sales driver breakdown** (TikTok Shop, Meta Ads, influencer stacks, Shopify apps, PPC tools)
- **Verified suppliers** (Alibaba, AliExpress, DHgate, Faire, Spocket, Zendrop, CJ Dropshipping, Global Sources) with MOQ, price, lead time, rating
- **Channel recommender** — best marketplace to sell each product on with reasoning
- **Ad-spend estimator** — monthly budget & expected ROAS for TikTok, Meta, Amazon PPC, Google Shopping
- **Bundle opportunity detector** — smart product bundles with margin uplift
- **Interactive profit calculator** — sliders for budget, units, ad-spend %, platform-fee %; live ROI & break-even
- **Platform fees breakdown** — Amazon FBA, TikTok Shop, Shopify, Etsy, eBay, Walmart side by side
- **Seasonal demand calendar** — 12-month heatmap with peak/off-season labels
- **Top competitors** per market — revenue, platform mix, strength rating

### 🎯 UX & Productivity
- **Watchlist** — star products, persisted in localStorage, with score-delta badges (`↑ 15 pts`)
- **Side-by-side compare** — head-to-head table with per-metric winner pills, persisted selection
- **Overall Opportunity Score** — composite gauge combining trend, velocity, saturation-inverse, margin, first-mover
- **Search & category chips**, **Early-only filter**, **CSV export**
- **Dark mode default** with light-mode toggle; theme persisted
- **Recharts** trend, area, bar, radar visualisations
- **Sonner** toasts, staged AI-research progress feedback

---

## Tech Stack

| Layer | Choice |
|---|---|
| Frontend | React 19 + **TypeScript** (CRA + craco), Tailwind CSS, shadcn UI |
| Charts | Recharts |
| State | TanStack Query, React Context (theme / location / watchlist / compare) |
| Backend | **Python FastAPI**, Motor (async MongoDB), Pydantic v2 |
| Database | MongoDB |
| AI | Emergent Universal LLM Key → Gemini 3 Flash Preview |
| Live data | PyTrends (Google Trends), RestCountries |
| Pluggable | Rainforest, Jungle Scout, SerpAPI, TikTok Creative Center, AliExpress, Helium 10, Open Exchange Rates, ExchangeRate-API |

---

## Local Setup

### Prerequisites
- Python 3.11+
- Node.js 18+ and **Yarn** (not npm)
- MongoDB on `mongodb://localhost:27017`

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env         # then fill in only the keys you want
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

### Frontend

```bash
cd frontend
yarn install
# frontend/.env must contain: REACT_APP_BACKEND_URL=http://localhost:8001
yarn start
```

Open http://localhost:3000.

---

## API Integration Setup

All third-party integrations are **optional**. If a key isn't set, TrendSell falls back to AI-generated or seeded data with a visible label. Set any of these in `.env` using `.env.example` as a template.

| Integration | Free? | Env vars | Where to get a key |
|---|---|---|---|
| **PyTrends (Google Trends)** | ✅ Free, no key | — | Bundled |
| **RestCountries** | ✅ Free, no key | — | Bundled (may fall back if the upstream free tier is offline) |
| **Emergent LLM Key** | Included on Emergent | `EMERGENT_LLM_KEY` | Profile → Universal Key |
| Rainforest (Amazon) | 🔑 | `RAINFOREST_API_KEY` | https://www.rainforestapi.com/ |
| Jungle Scout | 🔑 | `JUNGLE_SCOUT_API_KEY`, `JUNGLE_SCOUT_API_NAME` | https://developer.junglescout.com/ |
| Open Exchange Rates | 🔑 (free tier) | `OPEN_EXCHANGE_RATES_APP_ID` | https://openexchangerates.org/ |
| ExchangeRate-API | 🔑 (free tier) | `EXCHANGERATE_API_KEY` | https://www.exchangerate-api.com/ |
| SerpAPI | 🔑 | `SERPAPI_KEY` | https://serpapi.com/ |
| TikTok Creative Center | 🔑 | `TIKTOK_ACCESS_TOKEN` | https://ads.tiktok.com/creative_center/ |
| AliExpress Open API | 🔑 | `ALIEXPRESS_APP_KEY`, `ALIEXPRESS_APP_SECRET` | https://open.aliexpress.com/ |
| Helium 10 | 🔑 | `HELIUM10_API_KEY` | https://www.helium10.com/tools/api/ |

Live integration health is exposed at `GET /api/integrations/status`.

---

## API Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /api/products?country=US&category=Beauty&search=&early_only=false` | Location-aware product list |
| `GET /api/products/{id}?country=US` | Single product with local pricing, landed cost, regulation |
| `POST /api/products/compare` | Batch fetch for side-by-side |
| `GET /api/categories` | Category list |
| `GET /api/countries` | 46 supported markets with flags, currencies, PPP, platforms |
| `GET /api/trends` | Dashboard aggregates + top-5 7-week series |
| `GET /api/suppliers` | Aggregated supplier index across all products |
| `GET /api/platform-fees` | Amazon / TikTok Shop / Shopify / Etsy / eBay / Walmart fee comparison |
| `POST /api/research/refresh` | LLM-powered trend re-scoring |
| `POST /api/products/{id}/brief` | AI 1-page market brief |
| `POST /api/products/{id}/niches` | AI niche mining |
| `GET /api/integrations/status` | Health of all 10 integrations |
| `GET /api/integrations/trending?country=NG` | Live Google Trends |
| `GET /api/integrations/keyword-interest?keyword=X&country=US` | Interest-over-time |

---

## Project Structure

```
/app
├── backend/
│   ├── server.py              # FastAPI app + all routes
│   ├── seed_data.py           # 12 seeded products across 7 categories
│   ├── enrichment.py          # Category templates + opportunity-score math
│   ├── locations.py           # 46 countries, PPP, regulations, landed cost
│   ├── services/              # Modular integration layer
│   │   ├── __init__.py        # with_fallback wrapper, status registry
│   │   ├── google_trends.py   # PyTrends (live, no key)
│   │   ├── restcountries.py   # (live, no key)
│   │   └── integrations.py    # Rainforest, JungleScout, SerpAPI, …
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── pages/             # Dashboard, ProductDetail, Watchlist, Compare, Fees, …
│   │   ├── components/        # ProductCard, CountrySelector, OpportunityGauge, …
│   │   ├── context/           # ThemeContext, LocationContext, AppState
│   │   ├── lib/               # api.ts, csv.ts, utils.js
│   │   └── types.ts
│   ├── tsconfig.json
│   └── package.json
├── .env.example               # All placeholder API keys documented
├── .gitignore
└── README.md
```

---

## Roadmap

- Real Alibaba/1688 supplier scraping via signed AliExpress Open API
- Multi-user accounts + saved research runs
- Voice narration of AI Market Briefs
- Slack / Email alerts when a watchlisted product crosses a threshold

---

## License

MIT © 2026 TrendSell contributors
