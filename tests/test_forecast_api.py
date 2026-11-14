"""FastAPI authorization, SQL scope and read-only scenario contract tests."""
from datetime import date, timedelta
from decimal import Decimal

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from backend import demand_forecasting as api

TODAY = date.today()
TENANT_A = "a0000000-0000-0000-0000-000000000001"
TENANT_B = "a0000000-0000-0000-0000-000000000002"


def history(tenant):
    units = 3 if tenant == TENANT_A else 20
    return [(TODAY - timedelta(days=d), "Tea", "Beverages", units, Decimal(units * 5)) for d in range(420)]


class Cursor:
    def __init__(self, scoped, calls):
        self.scoped, self.calls = scoped, calls
        self.answer = []

    def __enter__(self): return self
    def __exit__(self, *args): return False

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        if sql.strip().lower().startswith("set transaction"):
            assert "READ ONLY" in sql
        elif "FROM sales_line_items" in sql:
            assert "business_id = %s" in sql
            assert params[0] == self.scoped["id"]
            self.answer = history(self.scoped["id"])
        elif "FROM raw_csv_uploads" in sql:
            assert "business_id = %s" in sql
            assert params == (self.scoped["id"],)
            self.answer = [None]
        else:
            raise AssertionError(sql)

    def fetchall(self): return self.answer
    def fetchone(self): return self.answer


class Connection:
    def __init__(self, scoped, calls): self.scoped, self.calls = scoped, calls
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def cursor(self): return Cursor(self.scoped, self.calls)


def client_for(monkeypatch, tenant):
    app = FastAPI()
    app.include_router(api.router)
    calls = []
    scoped = {"id": tenant}
    app.dependency_overrides[api.current_owner] = lambda: {"business_id": scoped["id"], "role": "owner"}
    monkeypatch.setattr(api, "get_connection", lambda: Connection(scoped, calls))
    return TestClient(app), calls, scoped


def test_api_only_uses_authorized_business(monkeypatch):
    client, calls, scoped = client_for(monkeypatch, TENANT_A)
    response = client.get("/api/forecast/overview", params={"horizon": "week", "business_id": TENANT_B})
    assert response.status_code == 200, response.text
    first = response.json()["forecast"]["totals"]["expected_net_units"]
    scoped["id"] = TENANT_B
    second = client.get("/api/forecast/overview", params={"horizon": "week", "business_id": TENANT_A})
    assert second.status_code == 200, second.text
    assert second.json()["forecast"]["totals"]["expected_net_units"] > first
    assert {p[0] for _, p in calls if p and len(p) > 1} == {TENANT_A, TENANT_B}
    assert all("business_id = %s" in sql for sql, params in calls if params)


def test_api_rejects_invalid_horizon(monkeypatch):
    client, _, _ = client_for(monkeypatch, TENANT_A)
    assert client.get("/api/forecast/overview", params={"horizon": "century"}).status_code == 422
    assert client.get("/api/forecast/overview", params={"product": "Tea"}).status_code == 422


def test_reorder_is_only_a_nonpersistent_scenario(monkeypatch):
    client, calls, _ = client_for(monkeypatch, TENANT_A)
    response = client.post("/api/forecast/reorder-scenario", json={
        "category": "Beverages", "product": "Tea", "on_hand": 0,
        "lead_time_days": 6, "safety_days": 2, "pack_size": 4
    })
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["scenario"]["suggested_product_units"] > 0
    assert payload["scenario"]["suggested_product_units"] % 4 == 0
    assert payload["scenario"]["no_inventory_writes"]
    assert not any("UPDATE " in sql or "INSERT " in sql or "DELETE " in sql for sql, _ in calls)


def test_business_owner_permission_is_enforced(monkeypatch):
    app = FastAPI()
    app.include_router(api.router)
    def deny(): raise HTTPException(status_code=403, detail="Business owner access required")
    app.dependency_overrides[api.current_owner] = deny
    response = TestClient(app).get("/api/forecast/overview")
    assert response.status_code == 403


def test_reorder_invalid_arguments(monkeypatch):
    client, _, _ = client_for(monkeypatch, TENANT_A)
    bad = client.post("/api/forecast/reorder-scenario", json={
        "category": "Beverages", "product": "Tea", "on_hand": -1,
        "lead_time_days": 4, "safety_days": 2, "pack_size": 0
    })
    assert bad.status_code == 422
