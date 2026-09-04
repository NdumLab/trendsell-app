"""TrendSell: countries, integrations (placeholder-key resilience), suppliers, fees, compare, brief, niches."""
import os

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def products(api):
    r = api.get(f"{BASE_URL}/api/products", timeout=60)
    assert r.status_code == 200
    return r.json()


# ---------- /api/countries ----------
class TestCountries:
    def test_countries(self, api):
        r = api.get(f"{BASE_URL}/api/countries", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["total"] == len(d["countries"])
        assert d["total"] >= 46, f"expected >=46 countries, got {d['total']}"
        codes = [c["code"] for c in d["countries"]]
        assert "US" in codes and "NG" in codes and "IN" in codes
        for c in d["countries"]:
            for k in ("code", "name"):
                assert k in c


# ---------- /api/platform-fees ----------
class TestPlatformFees:
    def test_fees(self, api):
        r = api.get(f"{BASE_URL}/api/platform-fees", timeout=30)
        assert r.status_code == 200
        plats = r.json()["platforms"]
        assert len(plats) >= 6, f"expected >=6 platforms, got {len(plats)}"


# ---------- /api/integrations/* (all keys placeholder -> must never 500) ----------
class TestIntegrations:
    def test_status(self, api):
        r = api.get(f"{BASE_URL}/api/integrations/status", timeout=60)
        assert r.status_code == 200
        ints = r.json()["integrations"]
        assert len(ints) >= 10, f"expected >=10 integrations, got {len(ints)}"
        print("integrations:", [(i.get("name") or i.get("key"), i.get("status") or i.get("mode")) for i in ints]
              if isinstance(ints, list) else ints)

    @pytest.mark.parametrize("country", ["US", "NG", "IN"])
    def test_trending_never_500(self, api, country):
        r = api.get(f"{BASE_URL}/api/integrations/trending", params={"country": country}, timeout=90)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d["integration"] == "google_trends"
        assert "data" in d
        assert d["source"] in ("live", "fallback", "unavailable", "error", "cache"), d["source"]
        assert d["source"] not in ("error", "unavailable"), f"trending degraded: {d['source']}"
        print(f"trending {country}: source={d['source']} items={len(d['data'])}")

    def test_keyword_interest(self, api):
        r = api.get(f"{BASE_URL}/api/integrations/keyword-interest",
                    params={"keyword": "stanley cup", "country": "US"}, timeout=90)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert "data" in d and "source" in d
        print(f"keyword-interest source={d['source']}")

    def test_restcountries(self, api):
        r = api.get(f"{BASE_URL}/api/integrations/restcountries", timeout=90)
        assert r.status_code == 200
        d = r.json()
        assert "data" in d and "source" in d
        print(f"restcountries source={d['source']} n={len(d['data'])}")


# ---------- /api/suppliers ----------
class TestSuppliers:
    def test_suppliers(self, api):
        r = api.get(f"{BASE_URL}/api/suppliers", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["total"] == len(d["suppliers"])
        assert d["total"] > 0
        s = d["suppliers"][0]
        for k in ("name", "platform", "rating", "product_count", "categories"):
            assert k in s, f"supplier missing {k}"
        ratings = [x["rating"] for x in d["suppliers"]]
        assert ratings == sorted(ratings, reverse=True)


# ---------- country-aware products ----------
class TestCountryAware:
    @pytest.mark.parametrize("country", ["US", "NG", "IN"])
    def test_products_by_country(self, api, country):
        r = api.get(f"{BASE_URL}/api/products", params={"country": country}, timeout=60)
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 12
        p = data[0]
        for k in ("local_score", "global_score", "saturation_score", "velocity_pct"):
            assert k in p, f"missing {k} for {country}"
        assert "_id" not in p

    def test_local_scores_differ_between_countries(self, api):
        us = {p["id"]: p["local_score"] for p in api.get(
            f"{BASE_URL}/api/products", params={"country": "US"}, timeout=60).json()}
        ng = {p["id"]: p["local_score"] for p in api.get(
            f"{BASE_URL}/api/products", params={"country": "NG"}, timeout=60).json()}
        assert set(us) == set(ng)
        assert any(us[k] != ng[k] for k in us), "local_score identical for US and NG (country recalibration no-op)"

    def test_early_only_filter(self, api):
        r = api.get(f"{BASE_URL}/api/products", params={"early_only": "true", "country": "US"}, timeout=60)
        assert r.status_code == 200
        assert all(p.get("is_early_opportunity") for p in r.json())

    def test_single_product_with_country(self, api, products):
        pid = products[0]["id"]
        r = api.get(f"{BASE_URL}/api/products/{pid}", params={"country": "NG"}, timeout=30)
        assert r.status_code == 200
        assert r.json()["id"] == pid
        assert "local_score" in r.json()


# ---------- /api/products/compare ----------
class TestCompare:
    def test_compare_order_preserved(self, api, products):
        ids = [products[2]["id"], products[0]["id"]]
        r = api.post(f"{BASE_URL}/api/products/compare", json={"ids": ids, "country": "US"}, timeout=30)
        assert r.status_code == 200
        out = r.json()
        assert [p["id"] for p in out] == ids

    def test_compare_empty_400(self, api):
        r = api.post(f"{BASE_URL}/api/products/compare", json={"ids": []}, timeout=30)
        assert r.status_code == 400


# ---------- AI endpoints (must not 500 with placeholder 3rd-party keys) ----------
class TestAIEndpoints:
    def test_brief(self, api, products):
        pid = products[0]["id"]
        r = api.post(f"{BASE_URL}/api/products/{pid}/brief", params={"force": "true"}, timeout=180)
        assert r.status_code == 200, r.text[:500]
        d = r.json()
        for k in ("executive_summary", "market_opportunity", "competition_level",
                  "recommended_platforms", "estimated_roi", "key_risks", "action_items", "model"):
            assert k in d and d[k] not in (None, "", []), f"brief field empty: {k}"
        print(f"brief model={d['model']}")

    def test_brief_cached(self, api, products):
        pid = products[0]["id"]
        r = api.post(f"{BASE_URL}/api/products/{pid}/brief", timeout=120)
        assert r.status_code == 200
        assert r.json()["executive_summary"]

    def test_brief_404(self, api):
        r = api.post(f"{BASE_URL}/api/products/nope-123/brief", timeout=60)
        assert r.status_code == 404

    def test_niches(self, api, products):
        pid = products[1]["id"]
        r = api.post(f"{BASE_URL}/api/products/{pid}/niches", params={"force": "true"}, timeout=180)
        assert r.status_code == 200, r.text[:500]
        d = r.json()
        assert isinstance(d["niches"], list) and len(d["niches"]) > 0
        assert all("name" in n and "competition" in n for n in d["niches"])
        print(f"niches source={d['source']} n={len(d['niches'])}")
