"""Sales Intelligence tests: calculations, authorization, business-scoped SQL.

Run: python -m pytest tests/test_sales_intelligence.py -v
Mocked PostgreSQL; a live database upload/browser check remains necessary.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import sales_intelligence as intelligence

TODAY = date.today()
BUSINESS = "44444444-4444-4444-4444-444444444444"


def sale(days_ago, product, category, qty, revenue):
    return (TODAY - timedelta(days=days_ago), product, category, qty, Decimal(revenue))


def test_sales_metrics_and_category_mix():
    rows = [
        sale(0, "Latte", "Coffee", 3, "15.00"),
        sale(1, "Croissant", "Pastries", 2, "8.00"),
        sale(1, "Latte", "Coffee", -1, "-5.00"),
        sale(30, "Latte", "Coffee", 2, "10.00"),
    ]
    result = intelligence.analyze_sales(rows, days=30, today=TODAY)
    assert result["has_data"] is True
    assert result["kpis"] == {
        "net_sales": 18.0,
        "units_sold": 4,
        "unique_products": 2,
        "growth_pct": 80.0,
        "previous_net_sales": 10.0,
    }
    assert result["category_mix"][0]["category"] == "Coffee"
    assert result["category_mix"][0]["revenue"] == 10.0
    assert result["category_mix"][0]["mix_pct"] == 55.6
    assert result["product_performance"][0]["product"] == "Latte"
    assert result["product_performance"][0]["units_sold"] == 2
    assert len(result["revenue_trend"]) == 30
    assert result["revenue_trend"][-1]["revenue"] == 15.0
    assert sum(d["revenue"] for d in result["revenue_trend"]) == pytest.approx(18.0)


def test_equal_length_previous_period_and_no_hardcoded_growth():
    rows = [sale(0, "Tea", "Drinks", 1, "4.00")]
    result = intelligence.analyze_sales(rows, days=7, today=TODAY)
    assert result["kpis"]["growth_pct"] is None
    assert result["period"]["previous_end_date"] == (TODAY - timedelta(days=7)).isoformat()
    assert result["period"]["previous_start_date"] == (TODAY - timedelta(days=13)).isoformat()
    assert result["revenue_trend"][0]["revenue"] == 0.0
    assert result["revenue_trend"][-1]["revenue"] == 4.0


def test_empty_period_has_all_zero_days_and_clear_message():
    data = intelligence.analyze_sales([], days=90, today=TODAY)
    assert data["has_data"] is False
    assert data["kpis"]["net_sales"] == 0.0
    assert data["category_mix"] == []
    assert data["product_performance"] == []
    assert len(data["revenue_trend"]) == 90
    assert data["insights"][0]["kind"] == "empty"


def test_negative_category_not_drawn_as_negative_pie():
    result = intelligence.analyze_sales([
        sale(0,"Tea","Drinks",4,"20.00"),
        sale(0,"Refund","Refunds",-1,"-5.00"),
    ],days=7,today=TODAY)
    categories = {x["category"]: x for x in result["category_mix"]}
    assert categories["Drinks"]["mix_pct"] == 100.0
    assert categories["Refunds"]["mix_pct"] == 0.0
    assert any(i["kind"] == "returns" for i in result["insights"])


def test_slow_movers_include_only_products_present_in_sales():
    result = intelligence.analyze_sales([
        sale(0,"Latte","Coffee",20,"100.00"),
        sale(1,"Tea","Drinks",1,"4.00"),
        sale(0,"Refund","Drinks",-3,"-12.00"),
    ],days=30,today=TODAY)
    assert [p["product"] for p in result["slow_movers"]] == ["Tea", "Latte"]



def test_monthly_trend_and_weekday_average_use_real_sales():
    rows = [sale(0,"Coffee","Drinks",2,"10.00"), sale(1,"Tea","Drinks",1,"5.00")]
    result = intelligence.analyze_sales(rows,days=7,today=TODAY)
    assert sum(m["revenue"] for m in result["monthly_revenue"]) == pytest.approx(15.0)
    assert sum(d["days_observed"] for d in result["weekday_performance"]) == 7
    assert sum(d["total_revenue"] for d in result["weekday_performance"]) == pytest.approx(15.0)
    assert all(d["days_observed"] == 1 for d in result["weekday_performance"])


def test_category_period_change_is_real_not_hardcoded():
    rows = [sale(0,"Tea","Drinks",2,"10.00"), sale(7,"Tea","Drinks",1,"4.00")]
    data = intelligence.analyze_sales(rows,days=7,today=TODAY)
    assert data["category_mix"][0]["previous_revenue"] == 4.0
    assert data["category_mix"][0]["growth_pct"] == 150.0


def test_invalid_reporting_window_rejected():
    with pytest.raises(ValueError):
        intelligence.analyze_sales([], days=365, today=TODAY)


class FakeCursor:
    def __init__(self, state):
        self.state = state
        self.last = None
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def execute(self, sql, params):
        low = " ".join(sql.lower().split())
        self.state["statements"].append((low, params))
        assert params[0] == BUSINESS, "All database access must be scoped to the verified business"
        if "from sales_line_items" in low:
            assert "group by" in low
            assert "business_id = %s" in low
            assert params[1] == date.today() - timedelta(days=2 * self.state["days"] - 1)
            assert params[2] == date.today()
            self.last = self.state["rows"]
        elif "from raw_csv_uploads" in low:
            assert "business_id = %s" in low
            self.last = [(datetime(2026, 11, 5, 14, tzinfo=timezone.utc),)]
        else:
            raise AssertionError("Unexpected SQL: " + low)
    def fetchall(self): return self.last
    def fetchone(self): return self.last[0]


class FakeConnection:
    def __init__(self, state): self.state = state
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def cursor(self): return FakeCursor(self.state)


@pytest.fixture
def api(monkeypatch):
    from backend.main import app
    state = {"rows": [sale(0,"Coffee","Drinks",2,"12.00")], "days": 30, "statements": []}
    original = dict(app.dependency_overrides)
    app.dependency_overrides[intelligence.current_member] = lambda: {"business_id": BUSINESS, "role": "owner", "user_id": "user"}
    monkeypatch.setattr(intelligence, "get_connection", lambda: FakeConnection(state))
    try:
        yield TestClient(app), state
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original)


def test_analytics_http_endpoint_scoped_to_business(api):
    client, state = api
    result = client.get("/api/dashboard/analytics")
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["kpis"]["net_sales"] == 12.0
    assert body["last_upload_at"] is not None
    assert len(state["statements"]) == 2


def test_analytics_supports_7_and_90_days(api):
    client, state = api
    for days in (7,90):
        state["days"] = days
        result = client.get(f"/api/dashboard/analytics?days={days}")
        assert result.status_code == 200, result.text
        assert len(result.json()["revenue_trend"]) == days


def test_analytics_invalid_days_rejected(api):
    client, state = api
    for days in (0,8,365):
        assert client.get(f"/api/dashboard/analytics?days={days}").status_code == 422
    assert state["statements"] == []


def test_analytics_requires_login_without_dependency_override():
    from backend.main import app
    original = dict(app.dependency_overrides)
    try:
        app.dependency_overrides.clear()
        assert TestClient(app).get("/api/dashboard/analytics").status_code == 401
    finally:
        app.dependency_overrides.update(original)


def test_dashboard_additive_integration_and_assets():
    root = Path(__file__).resolve().parents[1]
    html = (root / "dashboard.html").read_text()
    main = (root / "backend/main.py").read_text()
    assert 'id="sales-intelligence"' in html
    assert 'sales-intelligence.css' in html
    assert 'sales-intelligence.js' in html
    assert 'fetch("/api/uploads"' in html
    assert main.index("app.include_router(sales_intelligence_router)") < main.index('app.mount("/",')
    assert (root / "sales-intelligence.js").exists()
    assert (root / "sales-intelligence.css").exists()
