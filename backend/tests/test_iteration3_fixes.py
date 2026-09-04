"""Iteration-3 certification: urllib3 pin (google_trends), restcountries hardening, integration status resilience."""
import os

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")

STUBS = [
    "rainforest", "jungle_scout", "openexchange", "exchangerate_api",
    "serpapi", "tiktok_creative", "aliexpress", "helium10",
]


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---------- NEW FIX 1: urllib3<2 pin / google trends ----------
class TestGoogleTrendsFix:
    def test_trending_endpoint_no_500(self, api):
        r = api.get(f"{BASE_URL}/api/integrations/trending?country=US", timeout=60)
        assert r.status_code == 200, r.text[:500]
        body = r.json()
        assert body.get("source") in ("live", "fallback"), body
        assert "method_whitelist" not in r.text

    def test_status_no_method_whitelist(self, api):
        r = api.get(f"{BASE_URL}/api/integrations/status", timeout=60)
        assert r.status_code == 200
        data = r.json()
        items = data if isinstance(data, list) else data.get("integrations", data.get("data", []))
        gt = [i for i in items if i.get("key") == "google_trends"]
        assert gt, f"google_trends not in status: {items}"
        last_error = gt[0].get("last_error") or ""
        assert "method_whitelist" not in str(last_error), last_error


# ---------- NEW FIX 2: restcountries hardening ----------
class TestRestCountriesFix:
    def test_restcountries_no_500(self, api):
        r = api.get(f"{BASE_URL}/api/integrations/restcountries", timeout=60)
        assert r.status_code == 200, r.text[:500]
        body = r.json()
        assert isinstance(body.get("data"), list)
        assert body.get("source") in ("live", "fallback"), body

    def test_status_no_str_attr_error(self, api):
        r = api.get(f"{BASE_URL}/api/integrations/status", timeout=60)
        data = r.json()
        items = data if isinstance(data, list) else data.get("integrations", data.get("data", []))
        rc = [i for i in items if i.get("key") == "restcountries"]
        assert rc, "restcountries missing from status"
        err = str(rc[0].get("last_error") or "")
        assert "has no attribute 'get'" not in err, err


# ---------- Missing-key resilience ----------
class TestStubResilience:
    def test_stubs_unconfigured(self, api):
        r = api.get(f"{BASE_URL}/api/integrations/status", timeout=60)
        assert r.status_code == 200
        data = r.json()
        items = data if isinstance(data, list) else data.get("integrations", data.get("data", []))
        by_key = {i.get("key"): i for i in items}
        for key in STUBS:
            assert key in by_key, f"{key} missing from status"
            assert by_key[key].get("status") == "unconfigured", (key, by_key[key])
