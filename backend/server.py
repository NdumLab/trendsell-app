from fastapi import FastAPI, APIRouter, HTTPException, Query
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import json
import logging
import asyncio
import uuid
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from datetime import datetime, timezone

from seed_data import get_seed_products, get_categories
from enrichment import enrich as _enrich, PLATFORM_FEES, _CATEGORY_NICHES
from locations import COUNTRIES, apply_country

# Integration services — import defensively so any missing dep doesn't crash the app
try:
    from services import snapshot as integrations_snapshot
    from services import google_trends, restcountries, integrations as _int  # noqa: F401 registers services
    _SERVICES_OK = True
except Exception as _e:
    logging.getLogger("trendsell").warning(f"Integrations module unavailable: {_e}")
    integrations_snapshot = lambda: []
    google_trends = None
    restcountries = None
    _SERVICES_OK = False

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI(title="TrendSell API")
api_router = APIRouter(prefix="/api")

logger = logging.getLogger("trendsell")


# ---------- Models ----------
class SalesDriver(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    type: str
    description: str
    impact_score: int


class Supplier(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    platform: str
    moq: int
    unit_price: str
    lead_time_days: int
    rating: float
    url: str


class MarketBrief(BaseModel):
    model_config = ConfigDict(extra="ignore")
    executive_summary: str
    market_opportunity: str
    competition_level: str
    recommended_platforms: List[str]
    estimated_roi: str
    key_risks: List[str]
    action_items: List[str]
    generated_at: str
    model: str


class Product(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str
    category: str
    description: str
    trend_score: int
    demand_level: str
    image_url: str
    trending_platforms: List[str]
    price_range: str
    estimated_monthly_revenue: str
    growth_rate: int
    sales_drivers: List[SalesDriver]
    market_opportunity_score: int
    why_trending: str
    date_added: str
    trend_history: List[int] = Field(default_factory=list)
    suppliers: List[Supplier] = Field(default_factory=list)
    saturation_score: int = 50
    saturation_label: str = "Medium"
    is_early_opportunity: bool = False
    velocity_pct: int = 0
    velocity_label: str = "flat"
    opportunity_score: int = 0
    opportunity_breakdown: dict = Field(default_factory=dict)
    seasonal_demand: List[int] = Field(default_factory=list)
    competitors: List[dict] = Field(default_factory=list)
    channel_recommendations: List[dict] = Field(default_factory=list)
    ad_spend_estimates: List[dict] = Field(default_factory=list)
    bundle_suggestions: List[dict] = Field(default_factory=list)
    regions: List[dict] = Field(default_factory=list)
    niches: List[dict] = Field(default_factory=list)
    market_brief: Optional[MarketBrief] = None


class RefreshResponse(BaseModel):
    status: str
    count: int
    generated_at: str
    source: str


# ---------- Helpers ----------
async def ensure_seeded():
    """Seed the products collection on first run, and backfill new fields into existing docs."""
    # Category-based saturation defaults (deterministic per product name)
    def _saturation_for(name: str, platforms: list) -> int:
        base = 50
        if "Amazon" in platforms:
            base += 25
        if "Sephora" in platforms or "Costco" in platforms or "Best Buy" in platforms:
            base += 8
        if "TikTok Shop" in platforms and "Amazon" not in platforms:
            base -= 22
        if "Instagram Shop" in platforms and "Amazon" not in platforms:
            base -= 15
        # Deterministic jitter based on name length
        base += (len(name) % 7) - 3
        return max(15, min(95, base))

    count = await db.products.count_documents({})
    if count == 0:
        products = get_seed_products()
        for p in products:
            p["saturation_score"] = _saturation_for(p["name"], p.get("trending_platforms", []))
        await db.products.insert_many(products)
        logger.info(f"Seeded {len(products)} products")
        return

    # Backfill suppliers on any docs missing that field (idempotent)
    from seed_data import _SUPPLIER_TEMPLATES
    missing_sup = await db.products.find({"suppliers": {"$exists": False}}, {"_id": 0, "id": 1, "name": 1, "category": 1}).to_list(500)
    for doc in missing_sup:
        cat = doc.get("category", "Home")
        templates = _SUPPLIER_TEMPLATES.get(cat, _SUPPLIER_TEMPLATES["Home"])
        suppliers = [
            {
                "name": t["name"],
                "platform": t["platform"],
                "moq": t["moq"],
                "unit_price": t["unit_price"],
                "lead_time_days": t["lead_time_days"],
                "rating": t["rating"],
                "url": f"https://www.google.com/search?q={t['platform'].replace(' ', '+')}+{doc['name'].replace(' ', '+')}",
            }
            for t in templates
        ]
        await db.products.update_one({"id": doc["id"]}, {"$set": {"suppliers": suppliers}})
    if missing_sup:
        logger.info(f"Backfilled suppliers for {len(missing_sup)} products")

    # Backfill saturation_score on any docs missing it
    missing_sat = await db.products.find({"saturation_score": {"$exists": False}}, {"_id": 0, "id": 1, "name": 1, "trending_platforms": 1}).to_list(500)
    for doc in missing_sat:
        sat = _saturation_for(doc.get("name", ""), doc.get("trending_platforms", []))
        await db.products.update_one({"id": doc["id"]}, {"$set": {"saturation_score": sat}})
    if missing_sat:
        logger.info(f"Backfilled saturation_score for {len(missing_sat)} products")


def _strip_mongo(doc: dict) -> dict:
    doc.pop("_id", None)
    return doc


# ---------- Routes ----------
@api_router.get("/")
async def root():
    return {"message": "TrendSell API", "status": "ok"}


@api_router.get("/platform-fees")
async def platform_fees():
    return {"platforms": PLATFORM_FEES}


@api_router.get("/countries")
async def list_countries():
    return {"countries": COUNTRIES, "total": len(COUNTRIES)}


@api_router.get("/integrations/status")
async def integrations_status():
    return {"integrations": integrations_snapshot()}


@api_router.get("/integrations/trending")
async def integrations_trending(country: str = Query("US")):
    """Live Google Trends daily searches for the selected country."""
    if google_trends is None:
        return {"data": [], "source": "unavailable", "integration": "google_trends", "freshness": None}
    try:
        return await google_trends.daily_trending(country)
    except Exception as e:
        logger.warning(f"trending fetch failed: {e}")
        return {"data": [], "source": "error", "integration": "google_trends", "freshness": None}


@api_router.get("/integrations/keyword-interest")
async def integrations_keyword(keyword: str = Query(...), country: str = Query("US")):
    """Google Trends interest-over-time for a keyword in a country."""
    if google_trends is None:
        return {"data": {"keyword": keyword, "series": [], "avg": 0, "delta_pct": 0}, "source": "unavailable"}
    try:
        return await google_trends.keyword_interest(keyword, country)
    except Exception as e:
        logger.warning(f"keyword interest failed: {e}")
        return {"data": {"keyword": keyword, "series": [], "avg": 0, "delta_pct": 0}, "source": "error"}


@api_router.get("/integrations/restcountries")
async def integrations_restcountries():
    if restcountries is None:
        return {"data": [], "source": "unavailable"}
    try:
        return await restcountries.all_countries()
    except Exception as e:
        logger.warning(f"restcountries failed: {e}")
        return {"data": [], "source": "error"}


@api_router.get("/products", response_model=None)
async def list_products(
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort: str = Query("trend_score"),
    early_only: bool = Query(False),
    country: str = Query("US"),
):
    query = {}
    if category and category.lower() != "all":
        query["category"] = category
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}},
            {"category": {"$regex": search, "$options": "i"}},
        ]

    sort_field = sort if sort in {"trend_score", "growth_rate", "market_opportunity_score", "date_added"} else "trend_score"
    cursor = db.products.find(query).sort(sort_field, -1)
    docs = await cursor.to_list(200)
    enriched = [apply_country(_enrich(_strip_mongo(d)), country) for d in docs]
    if early_only:
        enriched = [d for d in enriched if d.get("is_early_opportunity")]
    return enriched


@api_router.get("/products/{product_id}", response_model=None)
async def get_product(product_id: str, country: str = Query("US")):
    doc = await db.products.find_one({"id": product_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Product not found")
    return apply_country(_enrich(_strip_mongo(doc)), country)


@api_router.post("/products/compare", response_model=None)
async def compare_products(payload: dict):
    """Fetch a batch of products by id list for side-by-side comparison."""
    ids = payload.get("ids") or []
    country = payload.get("country") or "US"
    if not isinstance(ids, list) or not ids:
        raise HTTPException(status_code=400, detail="ids list required")
    docs = await db.products.find({"id": {"$in": ids}}).to_list(10)
    ordered = []
    for pid in ids:
        for d in docs:
            if d.get("id") == pid:
                ordered.append(apply_country(_enrich(_strip_mongo(d)), country))
                break
    return ordered


@api_router.get("/categories")
async def list_categories():
    cats = await db.products.distinct("category")
    return {"categories": sorted(cats) if cats else get_categories()}


@api_router.get("/suppliers")
async def list_suppliers():
    """Aggregate suppliers across all tracked products (deduped by name + platform)."""
    docs = await db.products.find({}, {"_id": 0, "suppliers": 1, "name": 1, "category": 1}).to_list(500)
    bucket: dict = {}
    for d in docs:
        for s in d.get("suppliers", []) or []:
            key = f"{s['name']}::{s['platform']}"
            if key not in bucket:
                bucket[key] = {**s, "products": [], "categories": set()}
            bucket[key]["products"].append(d["name"])
            bucket[key]["categories"].add(d.get("category", ""))
    out = []
    for v in bucket.values():
        v["categories"] = sorted([c for c in v["categories"] if c])
        v["product_count"] = len(v["products"])
        out.append(v)
    out.sort(key=lambda x: (-x["rating"], -x["product_count"]))
    return {"suppliers": out, "total": len(out)}


@api_router.get("/trends")
async def get_trends():
    """Aggregate trend + platform data for dashboard charts."""
    docs = await db.products.find({}, {"_id": 0}).to_list(500)
    docs = [_enrich(d) for d in docs]

    # Category demand summary
    cat_map: dict = {}
    plat_map: dict = {}
    total_score = 0
    early_count = 0
    for d in docs:
        cat = d.get("category", "Other")
        cat_map.setdefault(cat, {"category": cat, "count": 0, "avg_score": 0, "total": 0})
        cat_map[cat]["count"] += 1
        cat_map[cat]["total"] += d.get("trend_score", 0)
        total_score += d.get("trend_score", 0)
        if d.get("is_early_opportunity"):
            early_count += 1
        for p in d.get("trending_platforms", []):
            plat_map[p] = plat_map.get(p, 0) + 1

    categories = []
    for c in cat_map.values():
        c["avg_score"] = round(c["total"] / max(c["count"], 1))
        categories.append({"category": c["category"], "count": c["count"], "avg_score": c["avg_score"]})
    categories.sort(key=lambda x: -x["avg_score"])

    platforms = [{"platform": k, "count": v} for k, v in sorted(plat_map.items(), key=lambda kv: -kv[1])]

    # Top-5 products trend history for line chart
    top = sorted(docs, key=lambda x: -x.get("trend_score", 0))[:5]
    weeks = ["W1", "W2", "W3", "W4", "W5", "W6", "W7"]
    trend_series = []
    for i, w in enumerate(weeks):
        row = {"week": w}
        for p in top:
            hist = p.get("trend_history", [])
            if i < len(hist):
                # Short unique label: first 2 words truncated, unique per product
                short = " ".join(p["name"].split()[:2])[:20].rstrip()
                row[short] = hist[i]
        trend_series.append(row)

    return {
        "total_products": len(docs),
        "avg_opportunity": round(total_score / max(len(docs), 1)),
        "top_velocity_platform": platforms[0]["platform"] if platforms else "TikTok Shop",
        "active_drivers": sum(len(d.get("sales_drivers", [])) for d in docs),
        "early_opportunities": early_count,
        "categories": categories,
        "platforms": platforms,
        "trend_series": trend_series,
        "top_products": [{"name": p["name"], "trend_score": p["trend_score"], "growth_rate": p["growth_rate"]} for p in top],
    }


@api_router.post("/research/refresh", response_model=RefreshResponse)
async def refresh_research():
    """Trigger AI-powered research to update trend scores / add new insights."""
    llm_key = os.environ.get("EMERGENT_LLM_KEY")
    source = "seed_refresh"

    updated = 0

    if llm_key:
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage

            docs = await db.products.find({}, {"_id": 0}).to_list(200)
            # Ask LLM to re-score current products and produce a fresh trend delta
            payload_products = [
                {"id": d["id"], "name": d["name"], "category": d["category"], "current_score": d["trend_score"]}
                for d in docs
            ]

            system_msg = (
                "You are TrendSell's AI research engine. You analyze current e-commerce trends "
                "across TikTok Shop, Amazon, Meta ads, Shopify, and viral consumer categories. "
                "You output STRICT JSON only, no prose, no code fences."
            )
            chat = LlmChat(
                api_key=llm_key,
                session_id=f"trendsell-refresh-{uuid.uuid4()}",
                system_message=system_msg,
            ).with_model("gemini", "gemini-3-flash-preview")

            prompt = (
                "For each product below, produce an updated trend_score (0-100) reflecting the "
                "most recent 30-day trajectory, a growth_rate (integer % between -20 and 220), "
                "and a short 1-sentence why_trending update. Return ONLY a JSON array of objects "
                'with keys: id, trend_score, growth_rate, why_trending. Products:\n'
                + json.dumps(payload_products)
            )

            resp = await chat.send_message(UserMessage(text=prompt))
            text = resp if isinstance(resp, str) else str(resp)
            # Try to locate JSON substring
            start = text.find("[")
            end = text.rfind("]")
            if start != -1 and end != -1 and end > start:
                arr = json.loads(text[start:end + 1])
                for item in arr:
                    pid = item.get("id")
                    if not pid:
                        continue
                    update = {
                        "trend_score": int(max(0, min(100, item.get("trend_score", 0)))),
                        "growth_rate": int(item.get("growth_rate", 0)),
                        "why_trending": item.get("why_trending", "")[:400],
                    }
                    # Append new trend history point
                    existing = await db.products.find_one({"id": pid}, {"trend_history": 1, "_id": 0})
                    if existing:
                        hist = existing.get("trend_history", []) + [update["trend_score"]]
                        update["trend_history"] = hist[-8:]
                    await db.products.update_one({"id": pid}, {"$set": update})
                    updated += 1
                source = "gemini-3-flash-preview"
        except Exception as e:
            logger.warning(f"LLM refresh failed, falling back to shuffle: {e}")

    if updated == 0:
        # Fallback: small random jitter so UI shows visible change
        import random
        docs = await db.products.find({}, {"_id": 0, "id": 1, "trend_score": 1, "trend_history": 1, "growth_rate": 1}).to_list(200)
        for d in docs:
            new_score = max(30, min(100, d["trend_score"] + random.randint(-4, 5)))
            new_growth = max(-20, min(220, d.get("growth_rate", 50) + random.randint(-10, 15)))
            hist = (d.get("trend_history") or []) + [new_score]
            await db.products.update_one(
                {"id": d["id"]},
                {"$set": {"trend_score": new_score, "growth_rate": new_growth, "trend_history": hist[-8:]}},
            )
            updated += 1

    return RefreshResponse(
        status="ok",
        count=updated,
        generated_at=datetime.now(timezone.utc).isoformat(),
        source=source,
    )


@api_router.post("/products/{product_id}/brief", response_model=MarketBrief)
async def generate_market_brief(product_id: str, force: bool = Query(False)):
    """Generate a 1-page AI market brief for a product. Cached on the product doc unless force=true."""
    doc = await db.products.find_one({"id": product_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Product not found")

    existing = doc.get("market_brief")
    if existing and not force:
        return existing

    enriched = _enrich(dict(doc))
    llm_key = os.environ.get("EMERGENT_LLM_KEY")
    brief_dict: dict = {}

    if llm_key:
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage

            system_msg = (
                "You are TrendSell's senior e-commerce analyst. You produce concise, actionable "
                "1-page market briefs for trending products. You output STRICT JSON only — no prose, "
                "no code fences."
            )
            chat = LlmChat(
                api_key=llm_key,
                session_id=f"trendsell-brief-{product_id}",
                system_message=system_msg,
            ).with_model("gemini", "gemini-3-flash-preview")

            context = {
                "name": enriched["name"],
                "category": enriched["category"],
                "description": enriched["description"],
                "trend_score": enriched["trend_score"],
                "velocity_pct": enriched.get("velocity_pct"),
                "saturation_score": enriched.get("saturation_score"),
                "market_opportunity_score": enriched["market_opportunity_score"],
                "price_range": enriched["price_range"],
                "estimated_monthly_revenue": enriched["estimated_monthly_revenue"],
                "trending_platforms": enriched["trending_platforms"],
                "sales_drivers": [{"name": s["name"], "type": s["type"], "impact": s["impact_score"]} for s in enriched.get("sales_drivers", [])],
                "why_trending": enriched.get("why_trending", ""),
            }

            prompt = (
                "Produce a 1-page market brief for the product below. Return ONLY a JSON object with keys:\n"
                "- executive_summary (2-3 sentence overview)\n"
                "- market_opportunity (paragraph on demand, TAM, growth trajectory)\n"
                "- competition_level (one of: 'Low', 'Moderate', 'High', 'Saturated' + 1 sentence rationale)\n"
                "- recommended_platforms (list of 3-5 platform names ranked)\n"
                "- estimated_roi (short quantitative estimate like '2.8x - 4.2x in 90 days')\n"
                "- key_risks (list of 3 concise risks)\n"
                "- action_items (list of 4 concrete next steps a seller should take)\n\n"
                "Product context:\n" + json.dumps(context)
            )

            resp = await chat.send_message(UserMessage(text=prompt))
            text = resp if isinstance(resp, str) else str(resp)
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                parsed = json.loads(text[start:end + 1])
                brief_dict = {
                    "executive_summary": str(parsed.get("executive_summary", ""))[:600],
                    "market_opportunity": str(parsed.get("market_opportunity", ""))[:800],
                    "competition_level": str(parsed.get("competition_level", ""))[:200],
                    "recommended_platforms": [str(x)[:60] for x in (parsed.get("recommended_platforms") or [])][:6],
                    "estimated_roi": str(parsed.get("estimated_roi", ""))[:120],
                    "key_risks": [str(x)[:200] for x in (parsed.get("key_risks") or [])][:6],
                    "action_items": [str(x)[:200] for x in (parsed.get("action_items") or [])][:8],
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "model": "gemini-3-flash-preview",
                }
        except Exception as e:
            logger.warning(f"LLM brief failed: {e}")

    if not brief_dict:
        # Deterministic fallback so the feature always renders something useful
        sat = enriched.get("saturation_score", 50)
        comp_level = "Saturated" if sat >= 80 else "High" if sat >= 60 else "Moderate" if sat >= 40 else "Low"
        brief_dict = {
            "executive_summary": (
                f"{enriched['name']} is a {enriched['category']} product currently scoring "
                f"{enriched['trend_score']}/100 on TrendSell's trend index, with velocity "
                f"{enriched.get('velocity_pct', 0):+d}% over the tracked window."
            ),
            "market_opportunity": (
                f"Estimated {enriched['estimated_monthly_revenue']} monthly category revenue with a "
                f"market opportunity score of {enriched['market_opportunity_score']}/100. "
                f"{enriched.get('why_trending', '')}"
            ),
            "competition_level": f"{comp_level} — saturation score {sat}/100 across major platforms.",
            "recommended_platforms": (enriched.get("trending_platforms") or [])[:5],
            "estimated_roi": (
                "1.8x - 3.4x in 90 days assuming 15% ad spend and standard marketplace fees."
                if sat < 55
                else "1.3x - 2.1x in 90 days — margins tighter due to competitive ad costs."
            ),
            "key_risks": [
                "Category saturation may accelerate as more sellers enter",
                "Ad costs on TikTok / Meta rising 8-12% QoQ",
                "Supplier lead times can slip during peak retail windows",
            ],
            "action_items": [
                "Lock in supplier MOQ within 14 days to secure Q-window pricing",
                "Test 3 creative angles on TikTok Spark Ads with $500 daily budget",
                "Set up Amazon PPC on top 5 category keywords with 1.8x break-even ACOS",
                "Build email capture with 10% first-order discount to compound LTV",
            ],
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "model": "fallback-heuristic",
        }

    await db.products.update_one({"id": product_id}, {"$set": {"market_brief": brief_dict}})
    return brief_dict


@api_router.post("/products/{product_id}/niches")
async def generate_niches(product_id: str, force: bool = Query(False)):
    """Generate 3-5 sub-niches for a product using the LLM (cached on the doc)."""
    doc = await db.products.find_one({"id": product_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Product not found")

    if doc.get("niches") and not force:
        return {"niches": doc["niches"], "source": doc.get("niches_source", "cached")}

    llm_key = os.environ.get("EMERGENT_LLM_KEY")
    niches: list = []
    source = "template"

    if llm_key:
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage

            system_msg = (
                "You are TrendSell's niche-mining analyst. You identify untapped sub-niches "
                "for trending e-commerce products. You output STRICT JSON only."
            )
            chat = LlmChat(
                api_key=llm_key,
                session_id=f"trendsell-niches-{product_id}",
                system_message=system_msg,
            ).with_model("gemini", "gemini-3-flash-preview")

            prompt = (
                f"For the product '{doc['name']}' (category: {doc['category']}), suggest 5 "
                "specific, untapped sub-niches. For each niche, output an object with keys 'name' "
                "(concrete niche description, 6-12 words) and 'competition' (one of 'Very Low', "
                "'Low', 'Medium', 'High'). Return ONLY a JSON array of 5 objects."
            )
            resp = await chat.send_message(UserMessage(text=prompt))
            text = resp if isinstance(resp, str) else str(resp)
            start = text.find("[")
            end = text.rfind("]")
            if start != -1 and end != -1:
                arr = json.loads(text[start:end + 1])
                for item in arr[:5]:
                    if isinstance(item, dict) and "name" in item:
                        niches.append({
                            "name": str(item.get("name", ""))[:120],
                            "competition": str(item.get("competition", "Medium"))[:20],
                        })
                if niches:
                    source = "gemini-3-flash-preview"
        except Exception as e:
            logger.warning(f"LLM niche generation failed: {e}")

    if not niches:
        niches = _CATEGORY_NICHES.get(doc.get("category", "Home"), [])

    await db.products.update_one({"id": product_id}, {"$set": {"niches": niches, "niches_source": source}})
    return {"niches": niches, "source": source}


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


@app.on_event("startup")
async def on_startup():
    await ensure_seeded()


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
