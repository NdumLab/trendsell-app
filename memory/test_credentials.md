# TrendSell Test Credentials

No authentication required — this is a public dashboard.

## Public URLs
- Frontend: https://market-trends-59.preview.emergentagent.com
- Backend API: https://market-trends-59.preview.emergentagent.com/api

## Notes for Testing
- All third-party integration keys (Rainforest, Jungle Scout, SerpAPI, etc.) are intentionally left as `your_..._here` placeholders — the app MUST fall back gracefully.
- Emergent LLM Key is set for /api/research/refresh, /api/products/{id}/brief, /api/products/{id}/niches.
- PyTrends is live and needs no key (may occasionally rate-limit; fallback expected).
- 12 seeded products across 7 categories (Home, Beauty, Fitness, Fashion, Electronics, Kitchen, Pet).
