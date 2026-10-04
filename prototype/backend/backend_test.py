"""TrendSell backend API tests (products, categories, trends, research refresh)."""
import os

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")

REQUIRED_FIELDS = [
    "id", "name", "category", "description", "trend_score", "demand_level",
    "image_url", "trending_platforms", "price_range", "estimated_monthly_revenue",
    "growth_rate", "sales_drivers", "market_opportunity_score", "why_trending",
    "date_added", "trend_history",
]


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---------- root ----------
class TestRoot:
    def test_root(self, api):
        r = api.get(f"{BASE_URL}/api/")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


# ---------- /api/products ----------
class TestProducts:
    def test_list_products(self, api):
        r = api.get(f"{BASE_URL}/api/products", timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) == 12, f"expected 12 products, got {len(data)}"
        for p in data:
            for f in REQUIRED_FIELDS:
                assert f in p, f"missing field {f} in {p.get('name')}"
            assert "_id" not in p
            assert isinstance(p["trend_score"], int)
            assert 0 <= p["trend_score"] <= 100
            assert isinstance(p["sales_drivers"], list) and len(p["sales_drivers"]) > 0
            assert isinstance(p["trend_history"], list) and len(p["trend_history"]) >= 7
            assert p["image_url"].startswith("http")
        # default sort by trend_score desc
        scores = [p["trend_score"] for p in data]
        assert scores == sorted(scores, reverse=True)

    def test_filter_by_category(self, api):
        r = api.get(f"{BASE_URL}/api/products", params={"category": "Beauty"}, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert len(data) > 0
        assert all(p["category"] == "Beauty" for p in data)

    def test_category_all(self, api):
        r = api.get(f"{BASE_URL}/api/products", params={"category": "all"}, timeout=30)
        assert r.status_code == 200
        assert len(r.json()) == 12

    def test_search(self, api):
        r = api.get(f"{BASE_URL}/api/products", params={"search": "stanley"}, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 1
        assert any("stanley" in p["name"].lower() or "stanley" in p["description"].lower() for p in data)

    def test_search_no_match(self, api):
        r = api.get(f"{BASE_URL}/api/products", params={"search": "zzzznotarealthing"}, timeout=30)
        assert r.status_code == 200
        assert r.json() == []

    def test_sort_growth_rate(self, api):
        r = api.get(f"{BASE_URL}/api/products", params={"sort": "growth_rate"}, timeout=30)
        assert r.status_code == 200
        rates = [p["growth_rate"] for p in r.json()]
        assert rates == sorted(rates, reverse=True)

    def test_get_single_product(self, api):
        lst = api.get(f"{BASE_URL}/api/products", timeout=30).json()
        pid = lst[0]["id"]
        r = api.get(f"{BASE_URL}/api/products/{pid}", timeout=30)
        assert r.status_code == 200
        p = r.json()
        assert p["id"] == pid
        assert p["name"] == lst[0]["name"]
        assert len(p["sales_drivers"]) > 0
        d = p["sales_drivers"][0]
        for k in ("name", "type", "description", "impact_score"):
            assert k in d
        assert len(p["trend_history"]) >= 7

    def test_invalid_product_404(self, api):
        r = api.get(f"{BASE_URL}/api/products/invalid-id", timeout=30)
        assert r.status_code == 404
        assert "detail" in r.json()


# ---------- /api/categories ----------
class TestCategories:
    def test_categories(self, api):
        r = api.get(f"{BASE_URL}/api/categories", timeout=30)
        assert r.status_code == 200
        cats = r.json()["categories"]
        assert isinstance(cats, list) and len(cats) > 0
        assert len(cats) == len(set(cats))
        assert cats == sorted(cats)
        assert "Beauty" in cats


# ---------- /api/trends ----------
class TestTrends:
    def test_trends(self, api):
        r = api.get(f"{BASE_URL}/api/trends", timeout=30)
        assert r.status_code == 200
        d = r.json()
        for k in ("total_products", "avg_opportunity", "top_velocity_platform",
                  "active_drivers", "categories", "platforms", "trend_series", "top_products"):
            assert k in d, f"missing {k}"
        assert d["total_products"] == 12
        assert isinstance(d["avg_opportunity"], int) and d["avg_opportunity"] > 0
        assert isinstance(d["top_velocity_platform"], str) and d["top_velocity_platform"]
        assert d["active_drivers"] > 0
        assert len(d["categories"]) > 0
        assert all({"category", "count", "avg_score"} <= set(c) for c in d["categories"])
        assert all({"platform", "count"} <= set(p) for p in d["platforms"])
        assert len(d["trend_series"]) == 7
        assert all("week" in row for row in d["trend_series"])
        # each trend_series row should have data for top products
        assert len(d["trend_series"][0]) > 1, "trend_series rows contain no product data"
        assert len(d["top_products"]) == 5


# ---------- /api/research/refresh (LLM) ----------
class TestResearchRefresh:
    def test_refresh(self, api):
        before = {p["id"]: p["trend_score"] for p in api.get(f"{BASE_URL}/api/products", timeout=30).json()}
        r = api.post(f"{BASE_URL}/api/research/refresh", timeout=180)
        assert r.status_code == 200, r.text[:500]
        d = r.json()
        assert d["status"] == "ok"
        assert d["count"] > 0
        assert d["source"] in ("gemini-3-flash-preview", "seed_refresh")
        assert d["generated_at"]
        print(f"refresh source={d['source']} count={d['count']}")
        after = {p["id"]: p["trend_score"] for p in api.get(f"{BASE_URL}/api/products", timeout=30).json()}
        assert set(after) == set(before)
        # history should have grown / scores updated
        hist = api.get(f"{BASE_URL}/api/products", timeout=30).json()[0]["trend_history"]
        assert len(hist) <= 8
