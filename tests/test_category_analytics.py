"""Automated tests for category drill-down analytics."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from backend import category_analytics
from backend.main import app


TODAY = date.today()
BUSINESS = "44444444-4444-4444-4444-444444444444"


def sale(days_ago, product, category, units, revenue):
    return (
        TODAY - timedelta(days=days_ago),
        product,
        category,
        units,
        Decimal(revenue),
    )


ROWS = [
    sale(0, "Thai Iced Tea", "Beverages", 3, "18.00"),
    sale(1, "Croissant", "Bakery", 2, "10.00"),
    sale(7, "Thai Iced Tea", "Beverages", 1, "6.00"),
]


def test_category_revenue_and_product_mix():
    result = category_analytics.build_category_report(
        ROWS, "Beverages", days=7, today=TODAY
    )

    assert result["kpis"]["net_sales"] == 18.0
    assert result["kpis"]["units_sold"] == 3
    assert result["kpis"]["growth_pct"] == 200.0
    assert result["kpis"]["category_share_pct"] == 64.3
    assert result["top_products"][0]["product"] == "Thai Iced Tea"
    assert len(result["revenue_trend"]) == 7


def test_category_matching_ignores_case_and_spaces():
    result = category_analytics.build_category_report(
        ROWS, " beverages ", days=7, today=TODAY
    )

    assert result["category"] == "Beverages"
    assert result["kpis"]["net_sales"] == 18.0


def test_empty_category_has_no_invented_sales():
    result = category_analytics.build_category_report(
        ROWS, "Soups", days=7, today=TODAY
    )

    assert result["has_data"] is False
    assert result["kpis"]["net_sales"] == 0.0
    assert result["top_products"] == []
    assert len(result["revenue_trend"]) == 7


def test_refunds_reduce_category_revenue():
    rows = [
        sale(0, "Coffee", "Beverages", 4, "20.00"),
        sale(0, "Coffee", "Beverages", -1, "-5.00"),
    ]

    result = category_analytics.build_category_report(
        rows, "Beverages", days=7, today=TODAY
    )

    assert result["kpis"]["net_sales"] == 15.0
    assert result["kpis"]["units_sold"] == 3


class FakeCursor:
    def __init__(self, state):
        self.state = state

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params):
        # The business must come from the verified membership.
        assert params[0] == BUSINESS
        assert "business_id = %s" in sql
        self.state["queries"].append((sql, params))

    def fetchall(self):
        return ROWS


class FakeConnection:
    def __init__(self, state):
        self.state = state

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return FakeCursor(self.state)


def test_category_api_scoped_to_business(monkeypatch):
    state = {"queries": []}

    original = dict(app.dependency_overrides)

    app.dependency_overrides[
        category_analytics.current_member
    ] = lambda: {
        "business_id": BUSINESS,
        "role": "owner",
        "user_id": "test-user",
    }

    monkeypatch.setattr(
        category_analytics,
        "get_connection",
        lambda: FakeConnection(state),
    )

    try:
        response = TestClient(app).get(
            "/api/dashboard/category-analytics",
            params={"category": "Beverages", "days": 7},
        )

        assert response.status_code == 200, response.text
        assert response.json()["kpis"]["net_sales"] == 18.0
        assert len(state["queries"]) == 1

    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original)


def test_category_api_requires_login():
    original = dict(app.dependency_overrides)
    app.dependency_overrides.clear()

    try:
        response = TestClient(app).get(
            "/api/dashboard/category-analytics",
            params={"category": "Beverages"},
        )

        assert response.status_code == 401

    finally:
        app.dependency_overrides.update(original)


def test_invalid_reporting_period():
    with pytest.raises(ValueError):
        category_analytics.build_category_report(
            ROWS, "Beverages", days=365, today=TODAY
        )
