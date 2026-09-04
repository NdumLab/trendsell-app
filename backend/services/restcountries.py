"""RestCountries — LIVE, no key required."""
from typing import Any, Dict, List
import time
import requests
from . import register, with_fallback

register(
    key="restcountries",
    name="RestCountries",
    description="Country metadata, currencies, regions — free public API.",
    env_vars=[],
    docs_url="https://restcountries.com/",
    icon="globe",
    always_on=True,
)

_cache: Dict[str, Any] = {"ts": 0, "data": None}
_TTL = 3600 * 6  # 6 hours


def _fetch_sync() -> List[Dict[str, Any]]:
    if _cache["data"] and time.time() - _cache["ts"] < _TTL:
        return _cache["data"]
    r = requests.get(
        "https://restcountries.com/v3.1/all",
        timeout=10,
        headers={"Accept": "application/json", "User-Agent": "TrendSell/1.0"},
        allow_redirects=True,
    )
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, list):
        raise ValueError(f"restcountries returned non-list payload (type={type(data).__name__})")
    slim = []
    for c in data:
        if not isinstance(c, dict):
            continue
        curr_map = c.get("currencies") or {}
        curr_code = next(iter(curr_map.keys()), None) if curr_map else None
        curr_symbol = curr_map.get(curr_code, {}).get("symbol") if curr_code else None
        slim.append({
            "code": c.get("cca2"),
            "name": (c.get("name") or {}).get("common"),
            "official_name": (c.get("name") or {}).get("official"),
            "flag": c.get("flag"),
            "region": c.get("region"),
            "subregion": c.get("subregion"),
            "currency_code": curr_code,
            "currency_symbol": curr_symbol,
            "population": c.get("population"),
            "capital": (c.get("capital") or [None])[0],
        })
    slim.sort(key=lambda x: (x.get("name") or "zz"))
    _cache["data"] = slim
    _cache["ts"] = time.time()
    return slim


async def all_countries() -> Dict[str, Any]:
    return await with_fallback(
        "restcountries",
        live_fn=_fetch_sync,
        fallback_fn=lambda: [],
    )
