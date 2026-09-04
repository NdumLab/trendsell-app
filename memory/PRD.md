# TrendSell — PRD

## Problem
Global product & sales intelligence dashboard: what's trending, why it's selling, where to source it, calibrated to any of 46 markets.

## Architecture
- Backend: FastAPI + Motor MongoDB + Emergent LLM Key (Gemini 3 Flash Preview)
- Frontend: React 19 + TypeScript (CRA + craco), Tailwind, Recharts, TanStack Query, Sonner, shadcn UI
- Integration layer: `services/` with unified `with_fallback()` wrapper + status registry (10 integrations)

## Implemented (through Feb 2026)
- 46-country location system with PPP pricing, local platforms, regulations, landed cost, local competitors
- Local vs Global trend scores, `Local Hidden Gem` / `Untapped in [Country]` / `Early Opportunity` badges
- 12 seeded products across 7 categories, all enriched (competitors, channel recs, ad spend, bundles, niches, seasonal, opportunity score)
- Watchlist (persisted), Compare (persisted), CSV export, dark/light theme
- AI Market Brief, AI Niche Finder, AI-driven refresh
- 10 integrations wired with graceful fallback; PyTrends & RestCountries live-attempted
- Full 4-tab ProductDetail: Overview / Sales & Ads / Sourcing & Profit / Intelligence
- Profit calculator, seasonal calendar, opportunity gauge, market-brief printable view
- 8-page frontend: Dashboard, ProductDetail, Watchlist, Compare, Drivers, Suppliers, Fees, Analytics, Research

## Certification (iteration_3.json)
- Backend 38/38 pytest passing (100%)
- Frontend: 0 console errors, 0 page errors, all 8 routes render, compare persistence + country switching verified
- No critical or minor blocking issues

## Repo hygiene
- .gitignore excludes .env, node_modules, __pycache__, build/, dist/, .venv/
- .env.example lists all 10 placeholder API keys with docs URLs
- README.md documents features, tech stack, local setup, API endpoints, project structure
- FEATURES_ROADMAP.md preserves next-cycle top 3 (Viral Video Spy, Store Spy, RFQ Generator)

## Ready for GitHub push
- Target: https://github.com/NdumLab/trendsell-app.git → main
- User will click "Save to GitHub" (agent cannot auth to user's GitHub from sandbox)
