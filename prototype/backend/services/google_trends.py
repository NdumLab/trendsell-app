"""Google Trends via pytrends — LIVE, no key required."""
from typing import Any, Dict, List
import time
from . import register, with_fallback, mark

register(
    key="google_trends",
    name="Google Trends",
    description="Live trending searches, velocity, related queries — powered by pytrends.",
    env_vars=[],
    docs_url="https://pypi.org/project/pytrends/",
    icon="line-chart",
    always_on=True,
)

_pytrends_client = None
_cache: Dict[str, Dict[str, Any]] = {}
_CACHE_TTL_S = 900  # 15 min


def _client():
    global _pytrends_client
    if _pytrends_client is None:
        from pytrends.request import TrendReq
        _pytrends_client = TrendReq(hl="en-US", tz=0, timeout=(4, 8), retries=1, backoff_factor=0.3)
    return _pytrends_client


def _cache_get(key: str):
    entry = _cache.get(key)
    if entry and time.time() - entry["ts"] < _CACHE_TTL_S:
        return entry["data"]
    return None


def _cache_set(key: str, data: Any):
    _cache[key] = {"ts": time.time(), "data": data}


def _daily_trending_sync(country_code: str = "united_states") -> List[Dict[str, Any]]:
    cache_key = f"daily::{country_code}"
    cached = _cache_get(cache_key)
    if cached:
        return cached
    df = _client().trending_searches(pn=country_code)
    # df is a single-column DataFrame of trending queries
    queries = df.iloc[:, 0].astype(str).tolist()[:20]
    result = [{"query": q, "rank": i + 1} for i, q in enumerate(queries)]
    _cache_set(cache_key, result)
    return result


def _interest_sync(keyword: str, geo: str = "") -> Dict[str, Any]:
    cache_key = f"interest::{keyword}::{geo}"
    cached = _cache_get(cache_key)
    if cached:
        return cached
    pt = _client()
    pt.build_payload([keyword], cat=0, timeframe="today 3-m", geo=geo)
    iot = pt.interest_over_time()
    if iot is None or iot.empty:
        result = {"keyword": keyword, "series": [], "avg": 0, "delta_pct": 0}
    else:
        series = [{"date": str(idx.date()), "value": int(row[keyword])} for idx, row in iot.iterrows()]
        values = [s["value"] for s in series if isinstance(s["value"], int)]
        avg = sum(values) / max(len(values), 1)
        delta = 0
        if len(values) >= 8:
            first_avg = sum(values[:4]) / 4
            last_avg = sum(values[-4:]) / 4
            if first_avg > 0:
                delta = int(((last_avg - first_avg) / first_avg) * 100)
        result = {"keyword": keyword, "series": series, "avg": round(avg, 1), "delta_pct": delta}
    _cache_set(cache_key, result)
    return result


# Country code (ISO-2) → pytrends 'pn' (used by trending_searches) and 'geo' (used by build_payload)
COUNTRY_TO_PYTRENDS = {
    "US": ("united_states", "US"), "GB": ("united_kingdom", "GB"), "CA": ("canada", "CA"),
    "AU": ("australia", "AU"), "NZ": ("new_zealand", "NZ"), "IN": ("india", "IN"),
    "JP": ("japan", "JP"), "KR": ("south_korea", "KR"), "SG": ("singapore", "SG"),
    "HK": ("hong_kong", "HK"), "TW": ("taiwan", "TW"), "MY": ("malaysia", "MY"),
    "PH": ("philippines", "PH"), "TH": ("thailand", "TH"), "ID": ("indonesia", "ID"),
    "VN": ("vietnam", "VN"), "DE": ("germany", "DE"), "FR": ("france", "FR"),
    "IT": ("italy", "IT"), "ES": ("spain", "ES"), "NL": ("netherlands", "NL"),
    "PL": ("poland", "PL"), "SE": ("sweden", "SE"), "NO": ("norway", "NO"),
    "IE": ("ireland", "IE"), "PT": ("portugal", "PT"), "TR": ("turkey", "TR"),
    "BR": ("brazil", "BR"), "MX": ("mexico", "MX"), "AR": ("argentina", "AR"),
    "CO": ("colombia", "CO"), "CL": ("chile", "CL"), "ZA": ("south_africa", "ZA"),
    "EG": ("egypt", "EG"), "NG": ("nigeria", "NG"), "KE": ("kenya", "KE"),
    "SA": ("saudi_arabia", "SA"), "AE": ("united_arab_emirates", "AE"), "IL": ("israel", "IL"),
}


async def daily_trending(country_code: str = "US") -> Dict[str, Any]:
    pn, _ = COUNTRY_TO_PYTRENDS.get(country_code.upper(), ("united_states", "US"))
    return await with_fallback(
        "google_trends",
        live_fn=lambda: _daily_trending_sync(pn),
        fallback_fn=lambda: [
            {"query": "stanley tumbler", "rank": 1},
            {"query": "protein ice cream maker", "rank": 2},
            {"query": "snail mucin essence", "rank": 3},
            {"query": "weighted bangles", "rank": 4},
            {"query": "activewear dress", "rank": 5},
            {"query": "airtag 4-pack", "rank": 6},
            {"query": "gan charger", "rank": 7},
        ],
    )


async def keyword_interest(keyword: str, country_code: str = "US") -> Dict[str, Any]:
    _, geo = COUNTRY_TO_PYTRENDS.get(country_code.upper(), ("united_states", "US"))
    return await with_fallback(
        "google_trends",
        live_fn=lambda: _interest_sync(keyword, geo),
        fallback_fn=lambda: {"keyword": keyword, "series": [], "avg": 0, "delta_pct": 0},
    )
