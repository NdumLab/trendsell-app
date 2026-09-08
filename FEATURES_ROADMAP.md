# TrendSell — Features Roadmap

> Historical prototype backlog. Superseded for execution on 8 September 2026 by the
> [detailed action plan](docs/ACTION_PLAN.md). The priorities and capability descriptions below
> describe the retired prototype; they are not the active application's implementation order or
> verified capabilities. Sales-driver and supplier intelligence remain in the current plan.

Curated backlog of features to borrow / adapt from successful e-commerce
sourcing & intelligence platforms, plus original TrendSell-only ideas.

---

## 🚀 Next Build Cycle — Top 3 Priorities

### 1. Viral Video Spy
Click any product → see the top-performing TikTok / Reels / Shorts videos driving
it, with view counts, engagement rate, creator handle, and publish date. Highest
"wow-per-feature" ratio and makes TrendSell feel alive versus static-catalog
competitors. Ties directly into our existing sales-driver breakdown.

### 2. Store Spy
Paste any Shopify / TikTok Shop URL → surface their traffic, top-selling
products, ad library snapshots, and installed Shopify apps. Turns TrendSell
from a browser into an *active* competitor-intelligence tool that operators
open every morning.

### 3. RFQ Generator
One click drafts a Request-For-Quote email to the top matched suppliers with
the user's MOQ, ship-to country, target price, and delivery date. Converts
insight into revenue by removing sourcing friction. Naturally reuses our
existing supplier data + Emergent LLM Key.

---

## Full Backlog by Inspiration Source

### From Helium 10 / Jungle Scout (Amazon-first research)
- **Reverse-ASIN keyword extraction** — user pastes competitor URL/ASIN → get every keyword it ranks for
- **Estimated units-sold per month** with confidence interval (BSR-based lookup)
- **Review-velocity chart** — new-reviews-per-day time series as a leading virality signal
- **Sentiment / negative-review keyword clouds** — mine reviews for pain points → product-improvement ideas
- **Historical price + BSR tracker** — Keepa-style time-series overlay

### From Sell The Trend / Dropship.io / EcomHunt
- **Winning-product feed** — curated daily stream of new hits (vs static grid)
- **"Test with $X ad spend" playbook** — literal creative + audience recipe per product
- **Store-Spy** (see Top 3 above)
- **Ad-library integration** — live Facebook / TikTok creatives per product

### From PPSPY / PiPiADS / Kalodata (TikTok Shop specialists)
- **Viral video spy** (see Top 3 above)
- **Creator affiliate ranking** — which creators are moving the most units for this SKU (essential for outreach)
- **Product-age indicator** — how long has the SKU been live on TikTok Shop (younger = less saturated)

### From Minea / AliShark / AutoDS
- **One-click AliExpress import** — from URL → auto-populate the full product-detail page
- **Auto-order routing** — hook for "when I sell, auto-purchase from supplier" workflow
- **Advanced ad-spy filters** — filter by spend > $X, running > N days, targeting country Y

### From Alibaba RFQ / Faire Wholesale
- **RFQ generator** (see Top 3 above)
- **Supplier verification signals** — years in business, gold-supplier badge, trade-assurance status
- **Sample-order tracker** — timeline: sample requested → shipped → received → reviewed

### From Shopify Winning Products / Zik Analytics (eBay)
- **Product-lifecycle stage** — Emerging / Growing / Peak / Declining / Evergreen (more actionable than raw trend score)
- **Auction-insights equivalent** — impression-share vs top-5 competitors
- **Retail arbitrage checker** — cross-reference Walmart / Costco / Target vs target sell price

---

## Original TrendSell-only Ideas (defensible moat)

- **"Ship-to-me" viability score** — combines landed cost + regulation + local competition into a single go/no-go per market, not US-centric
- **PPP-aware profit calculator matrix** — show margin curves across all 46 markets simultaneously
- **Regulation-change alerts** — notify watchlisted products when FCC / CE / BIS / NAFDAC rules shift for their category
- **Regional creator directory** — TikTok / Instagram creators sorted by market (top Beauty creators in Nigeria vs Indonesia vs Brazil), because local-language creators drive local-language sales
- **Cross-market arbitrage finder** — surface products that are `🌍 Local Hidden Gem` in one market and `🚀 Untapped` in another, ranked by profit delta
- **Landed-cost optimizer** — auto-suggest best air-vs-sea threshold based on projected order velocity
- **Compliance auto-brief** — LLM-generated 1-pager on what certifications a product needs to enter a given market

---

## Nice-to-Haves (post top-3)

- Voice narration of AI Market Briefs (ElevenLabs / OpenAI TTS)
- Slack / Email / WhatsApp alerts when a watchlisted product crosses a threshold
- Multi-user accounts + saved research runs
- Shareable public briefs (`/brief/{id}` route with OG image preview)
- Chrome extension: "TrendSell-ify this Amazon page"
- Mobile app wrapper (React Native)
