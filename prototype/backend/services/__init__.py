"""Common integration-service scaffolding: status registry, timing, graceful fallback."""
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional
import os
import logging

logger = logging.getLogger("trendsell.services")

# In-memory registry of integration status/telemetry per key.
_STATUS: Dict[str, Dict[str, Any]] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def register(
    key: str,
    name: str,
    description: str,
    env_vars: list,
    docs_url: str,
    icon: str = "plug",
    always_on: bool = False,
) -> None:
    _STATUS[key] = {
        "key": key,
        "name": name,
        "description": description,
        "env_vars": env_vars,
        "docs_url": docs_url,
        "icon": icon,
        "always_on": always_on,
        "status": "unconfigured",  # unconfigured | connected | fallback | error
        "last_fetch_at": None,
        "last_error": None,
        "last_latency_ms": None,
    }


def key_configured(env_var: str) -> bool:
    v = os.environ.get(env_var, "")
    return bool(v and not v.startswith("your_"))


def all_keys_configured(env_vars: list) -> bool:
    return all(key_configured(v) for v in env_vars)


def mark(key: str, status: str, latency_ms: Optional[int] = None, error: Optional[str] = None) -> None:
    if key not in _STATUS:
        return
    _STATUS[key]["status"] = status
    _STATUS[key]["last_fetch_at"] = _now_iso()
    _STATUS[key]["last_latency_ms"] = latency_ms
    _STATUS[key]["last_error"] = error


def snapshot() -> list:
    """Return list of all integration status entries (public API-safe)."""
    out = []
    for entry in _STATUS.values():
        e = dict(entry)
        e["configured"] = all_keys_configured(entry["env_vars"]) if entry["env_vars"] else True
        out.append(e)
    return out


async def with_fallback(key: str, live_fn: Callable, fallback_fn: Callable, timeout_s: float = 8.0) -> Dict[str, Any]:
    """Run live_fn; on failure or timeout, run fallback_fn. Returns {'data', 'source', 'freshness'}."""
    import asyncio
    entry = _STATUS.get(key, {})
    env_vars = entry.get("env_vars", [])
    always_on = entry.get("always_on", False)

    if not always_on and env_vars and not all_keys_configured(env_vars):
        mark(key, "unconfigured")
        data = fallback_fn()
        return {"data": data, "source": "fallback", "integration": key, "freshness": _now_iso()}

    start = datetime.now(timezone.utc)
    try:
        result = await asyncio.wait_for(asyncio.to_thread(live_fn), timeout=timeout_s)
        latency = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
        mark(key, "connected", latency_ms=latency)
        return {"data": result, "source": "live", "integration": key, "freshness": _now_iso()}
    except Exception as e:
        logger.warning(f"[{key}] fallback triggered: {e}")
        mark(key, "fallback", error=str(e)[:200])
        data = fallback_fn()
        return {"data": data, "source": "fallback", "integration": key, "freshness": _now_iso()}
