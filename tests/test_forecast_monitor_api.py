"""Owner-only ForecastStudio accuracy API and read-only PostgreSQL scope tests."""
from datetime import date, timedelta
from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend import demand_forecasting as api

A = "a0000000-0000-0000-0000-000000000001"
B = "a0000000-0000-0000-0000-000000000002"


def source_rows(tenant):
    n = 10 if tenant == A else 20
    return [
        (date.today() - timedelta(days=i), "Tea", "Beverages", n, Decimal(n * 5))
        for i in range(1, 130)
    ]


class Cursor:
    def __init__(self, tenant, calls):
        self.tenant = tenant
        self.calls = calls
        self.result = None

    def __enter__(self): return self
    def __exit__(self, *args): return False

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        if sql.strip().lower().startswith("set transaction"):
            assert "READ ONLY" in sql
        elif "FROM sales_line_items" in sql:
            assert "business_id = %s" in sql
            assert params[0] == self.tenant["id"]
            self.result = source_rows(self.tenant["id"])
        elif "FROM raw_csv_uploads" in sql:
            assert params == (self.tenant["id"],)
            self.result = (None,)
        else:
            raise AssertionError(f"Unexpected SQL: {sql}")

    def fetchall(self): return self.result
    def fetchone(self): return self.result


class Connection:
    def __init__(self, tenant, calls):
        self.tenant, self.calls = tenant, calls
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def cursor(self): return Cursor(self.tenant, self.calls)


def build_client(monkeypatch):
    app = FastAPI()
    app.include_router(api.router)
    calls = []
    tenant = {"id": A}
    app.dependency_overrides[api.current_owner] = lambda: {"business_id": tenant["id"]}
    monkeypatch.setattr(api, "get_connection", lambda: Connection(tenant, calls))
    return TestClient(app), tenant, calls


def test_tenant_scope_from_dependency_not_query(monkeypatch):
    client, tenant, calls = build_client(monkeypatch)
    r = client.get("/api/forecast/accuracy", params={"window": 7, "business_id": B})
    assert r.status_code == 200, r.text
    assert r.json()["accuracy"]["actual_net_units"] == 70
    tenant["id"] = B
    r = client.get("/api/forecast/accuracy", params={"window": 7, "business_id": A})
    assert r.status_code == 200, r.text
    assert r.json()["accuracy"]["actual_net_units"] == 140
    assert all("business_id = %s" in sql or "READ ONLY" in sql for sql, _ in calls)


def test_owner_required_without_dependency_override():
    app = FastAPI()
    app.include_router(api.router)
    response = TestClient(app).get("/api/forecast/accuracy")
    assert response.status_code in (401, 403)


def test_window_validation(monkeypatch):
    client, _, calls = build_client(monkeypatch)
    response = client.get("/api/forecast/accuracy", params={"window": 90})
    assert response.status_code == 422
    assert calls == []


def test_product_requires_category(monkeypatch):
    client, _, calls = build_client(monkeypatch)
    response = client.get("/api/forecast/accuracy", params={"product": "Tea"})
    assert response.status_code == 422
    assert calls == []


def test_valid_category_product_filter(monkeypatch):
    client, _, _ = build_client(monkeypatch)
    response = client.get("/api/forecast/accuracy", params={"window": 7, "category": "Beverages", "product": "Tea"})
    assert response.status_code == 200, response.text
    assert response.json()["accuracy"]["status"] == "evaluated"
    assert response.json()["read_only"] is True
