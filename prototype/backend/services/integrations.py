"""Stub integration services — all fall back gracefully when keys are missing."""
from typing import Any, Dict, List
import os
import time
import requests
from . import register, with_fallback, key_configured


# ------- Rainforest (Amazon Best Sellers) -------
register(
    key="rainforest",
    name="Rainforest API",
    description="Real Amazon Best Sellers, ASINs, prices, ratings, review counts.",
    env_vars=["RAINFOREST_API_KEY"],
    docs_url="https://www.rainforestapi.com/",
    icon="package",
)


def _rainforest_sync(category: str, country: str) -> List[Dict[str, Any]]:
    key = os.environ["RAINFOREST_API_KEY"]
    r = requests.get(
        "https://api.rainforestapi.com/request",
        params={"api_key": key, "type": "bestsellers", "category_id": "electronics", "amazon_domain": "amazon.com"},
        timeout=8,
    )
    r.raise_for_status()
    return r.json().get("bestsellers", [])


async def amazon_bestsellers(category: str = "Home", country: str = "US") -> Dict[str, Any]:
    return await with_fallback(
        "rainforest",
        live_fn=lambda: _rainforest_sync(category, country),
        fallback_fn=lambda: [],
    )


# ------- Jungle Scout (Competitor Intelligence) -------
register(
    key="jungle_scout",
    name="Jungle Scout",
    description="Real competitor revenue estimates & market-share by Amazon niche.",
    env_vars=["JUNGLE_SCOUT_API_KEY", "JUNGLE_SCOUT_API_NAME"],
    docs_url="https://developer.junglescout.com/",
    icon="trophy",
)


def _js_sync(keyword: str, country: str) -> Dict[str, Any]:
    key = os.environ["JUNGLE_SCOUT_API_KEY"]
    key_name = os.environ["JUNGLE_SCOUT_API_NAME"]
    r = requests.get(
        "https://developer.junglescout.com/api/keywords/keywords_by_asin_query",
        headers={"Authorization": f"{key_name}:{key}", "Accept": "application/vnd.junglescout.v1+json"},
        params={"marketplace": country.lower(), "sort": "-monthly_search_volume_exact"},
        timeout=8,
    )
    r.raise_for_status()
    return r.json()


async def js_competitors(keyword: str, country: str = "US") -> Dict[str, Any]:
    return await with_fallback(
        "jungle_scout",
        live_fn=lambda: _js_sync(keyword, country),
        fallback_fn=lambda: {"competitors": []},
    )


# ------- Open Exchange Rates -------
register(
    key="openexchange",
    name="Open Exchange Rates",
    description="Live FX rates for PPP-adjusted pricing.",
    env_vars=["OPEN_EXCHANGE_RATES_APP_ID"],
    docs_url="https://openexchangerates.org/",
    icon="dollar-sign",
)

_fx_cache = {"ts": 0, "data": None}


def _oxr_sync() -> Dict[str, float]:
    if _fx_cache["data"] and time.time() - _fx_cache["ts"] < 3600:
        return _fx_cache["data"]
    app_id = os.environ["OPEN_EXCHANGE_RATES_APP_ID"]
    r = requests.get(
        "https://openexchangerates.org/api/latest.json",
        params={"app_id": app_id},
        timeout=6,
    )
    r.raise_for_status()
    rates = r.json().get("rates", {})
    _fx_cache["data"] = rates
    _fx_cache["ts"] = time.time()
    return rates


async def fx_rates() -> Dict[str, Any]:
    return await with_fallback(
        "openexchange",
        live_fn=_oxr_sync,
        fallback_fn=lambda: {},
    )


# ------- ExchangeRate-API (backup) -------
register(
    key="exchangerate_api",
    name="ExchangeRate-API",
    description="Free tier FX fallback (1500 requests/mo).",
    env_vars=["EXCHANGERATE_API_KEY"],
    docs_url="https://www.exchangerate-api.com/",
    icon="repeat",
)


def _er_sync() -> Dict[str, float]:
    key = os.environ["EXCHANGERATE_API_KEY"]
    r = requests.get(f"https://v6.exchangerate-api.com/v6/{key}/latest/USD", timeout=6)
    r.raise_for_status()
    return r.json().get("conversion_rates", {})


async def exchangerate_api() -> Dict[str, Any]:
    return await with_fallback(
        "exchangerate_api",
        live_fn=_er_sync,
        fallback_fn=lambda: {},
    )


# ------- SerpAPI (Google Keyword Planner) -------
register(
    key="serpapi",
    name="SerpAPI",
    description="Search volume & CPC benchmarks by keyword and country.",
    env_vars=["SERPAPI_KEY"],
    docs_url="https://serpapi.com/",
    icon="search",
)


def _serp_sync(keyword: str, gl: str) -> Dict[str, Any]:
    key = os.environ["SERPAPI_KEY"]
    r = requests.get(
        "https://serpapi.com/search",
        params={"engine": "google", "q": keyword, "gl": gl.lower(), "api_key": key},
        timeout=8,
    )
    r.raise_for_status()
    return r.json()


async def keyword_data(keyword: str, country: str = "US") -> Dict[str, Any]:
    return await with_fallback(
        "serpapi",
        live_fn=lambda: _serp_sync(keyword, country),
        fallback_fn=lambda: {"organic_results": []},
    )


# ------- TikTok Creative Center -------
register(
    key="tiktok_creative",
    name="TikTok Creative Center",
    description="Trending TikTok Shop products, viral hashtags & videos.",
    env_vars=["TIKTOK_ACCESS_TOKEN"],
    docs_url="https://ads.tiktok.com/creative_center/",
    icon="music",
)


def _tt_sync() -> Dict[str, Any]:
    token = os.environ["TIKTOK_ACCESS_TOKEN"]
    r = requests.get(
        "https://business-api.tiktok.com/open_api/v1.3/creative/hashtag/trending/",
        headers={"Access-Token": token},
        timeout=8,
    )
    r.raise_for_status()
    return r.json()


async def tiktok_trending() -> Dict[str, Any]:
    return await with_fallback(
        "tiktok_creative",
        live_fn=_tt_sync,
        fallback_fn=lambda: {"trending": []},
    )


# ------- AliExpress / Alibaba -------
register(
    key="aliexpress",
    name="AliExpress Open API",
    description="Real supplier listings — MOQ, price, ratings.",
    env_vars=["ALIEXPRESS_APP_KEY", "ALIEXPRESS_APP_SECRET"],
    docs_url="https://open.aliexpress.com/",
    icon="factory",
)


def _ali_sync(product_name: str) -> Dict[str, Any]:
    # Real implementation would sign requests; stub raises to trigger fallback
    raise NotImplementedError("AliExpress signed request stub — implement when credentials arrive")


async def aliexpress_suppliers(product_name: str) -> Dict[str, Any]:
    return await with_fallback(
        "aliexpress",
        live_fn=lambda: _ali_sync(product_name),
        fallback_fn=lambda: {"suppliers": []},
    )


# ------- Helium 10 -------
register(
    key="helium10",
    name="Helium 10",
    description="Amazon keyword volume, competitor tracking, review analysis.",
    env_vars=["HELIUM10_API_KEY"],
    docs_url="https://www.helium10.com/tools/api/",
    icon="bar-chart-3",
)


def _h10_sync(keyword: str) -> Dict[str, Any]:
    key = os.environ["HELIUM10_API_KEY"]
    r = requests.get(
        "https://api.helium10.com/api/keywords/search",
        headers={"Authorization": f"Bearer {key}"},
        params={"keyword": keyword},
        timeout=8,
    )
    r.raise_for_status()
    return r.json()


async def h10_keyword(keyword: str) -> Dict[str, Any]:
    return await with_fallback(
        "helium10",
        live_fn=lambda: _h10_sync(keyword),
        fallback_fn=lambda: {"keyword": keyword, "volume": None},
    )
