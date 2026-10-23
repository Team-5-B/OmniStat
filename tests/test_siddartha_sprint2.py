"""Siddartha Sprint 2 API tests, using a simulated PostgreSQL connection.

Run from repo root: python -m pytest -v tests/test_siddartha_sprint2.py
Requires project dependencies; does NOT mutate a real database.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend import main
from backend import siddartha_sprint2 as s2
from backend.security import create_access_token

OWNER = "11111111-1111-1111-1111-111111111111"
EMPLOYEE = "22222222-2222-2222-2222-222222222222"
OTHER = "33333333-3333-3333-3333-333333333333"
BUSINESS = "44444444-4444-4444-4444-444444444444"
OTHER_BUSINESS = "55555555-5555-5555-5555-555555555555"


class Cursor:
    def __init__(self, state):
        self.state = state
        self.row = None
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params=()):
        q = " ".join(query.lower().split())
        self.row = None
        self.rows = []
        state = self.state
        if "select m.role from memberships as m" in q:
            member = state["memberships"].get((str(params[0]), str(params[1])))
            self.row = (member,) if member else None
        elif "from generate_series(" in q:
            assert params == (BUSINESS,), "Must be scoped to authenticated business"
            self.rows = [
                (date.today() - timedelta(days=29-i), Decimal("13.50") if i == 29 else Decimal("0"),
                 Decimal("6.25") if i == 29 else Decimal("0"), 3 if i == 29 else 0,
                 state["sales"] and i == 29)
                for i in range(30)
            ]
        elif "select u.id, u.name, u.email, m.role" in q:
            assert params == (BUSINESS,)
            self.rows = [(OWNER, "Owner", "owner@example.com", "owner")]
            if (EMPLOYEE, BUSINESS) in state["memberships"]:
                self.rows.append((EMPLOYEE, "Worker", "worker@example.com", "employee"))
        elif q.startswith("update businesses set name"):
            state["business_name"] = params[0]
            self.row = (BUSINESS, params[0]) if params[1] == BUSINESS else None
        elif q.startswith("insert into invites"):
            code = params[2]
            expiry = datetime.now(timezone.utc) + timedelta(days=params[3])
            state["invites"][code] = [state["business_name"], "employee", expiry, None]
            self.row = (expiry,)
        elif "select b.name, i.role, i.expires_at, i.used_at" in q:
            value = state["invites"].get(params[0])
            self.row = tuple(value) if value else None
        elif "select role from memberships" in q and "for update" in q:
            val = state["memberships"].get((str(params[0]), str(params[1])))
            self.row = (val,) if val else None
        elif q.startswith("delete from memberships"):
            state["memberships"].pop((str(params[0]), str(params[1])), None)
        else:
            raise AssertionError(f"Unexpected SQL: {query}")

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows


class Connection:
    def __init__(self, state):
        self.state = state

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return Cursor(self.state)


@pytest.fixture
def api(monkeypatch):
    state = {
        "memberships": {(OWNER, BUSINESS): "owner", (EMPLOYEE, BUSINESS): "employee",
                        (OTHER, OTHER_BUSINESS): "owner"},
        "business_name": "Demo Restaurant", "sales": True, "invites": {},
    }
    monkeypatch.setenv("JWT_SECRET_KEY", "sprint2-test-key-for-local-testing-only-123456")
    monkeypatch.setattr(s2, "get_connection", lambda: Connection(state))
    http = TestClient(main.app)
    headers_owner = {"Authorization": "Bearer " + create_access_token(OWNER, BUSINESS)}
    headers_worker = {"Authorization": "Bearer " + create_access_token(EMPLOYEE, BUSINESS)}
    headers_other = {"Authorization": "Bearer " + create_access_token(OTHER, OTHER_BUSINESS)}
    return http, state, headers_owner, headers_worker, headers_other


def test_dashboard_kpis_and_30_days(api):
    http, state, owner, *_ = api
    response = http.get("/api/dashboard/summary", headers=owner)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["has_data"] is True
    assert data["kpis"] == {"total_revenue": 13.5, "total_profit": 6.25, "items_sold_count": 3}
    assert len(data["revenue_30_days"]) == 30
    assert data["revenue_30_days"][-1]["revenue"] == 13.5


def test_dashboard_empty_state(api):
    http, state, owner, *_ = api
    state["sales"] = False
    response = http.get("/api/dashboard/summary", headers=owner)
    assert response.status_code == 200
    assert response.json()["has_data"] is False


def test_dashboard_requires_auth_and_active_membership(api):
    http, state, owner, worker, other = api
    assert http.get("/api/dashboard/summary").status_code == 401
    assert http.get("/api/dashboard/summary", headers=worker).status_code == 200
    del state["memberships"][(EMPLOYEE, BUSINESS)]
    assert http.get("/api/dashboard/summary", headers=worker).status_code == 403


def test_only_owner_can_list_team_and_update_business(api):
    http, state, owner, worker, other = api
    assert http.get("/api/business/team", headers=worker).status_code == 403
    data = http.get("/api/business/team", headers=owner).json()
    assert {m["role"] for m in data["members"]} == {"owner", "employee"}
    assert http.patch("/api/business", headers=worker, json={"name": "Other"}).status_code == 403
    renamed = http.patch("/api/business", headers=owner, json={"name": "New Name"})
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "New Name"
    assert http.patch("/api/business", headers=owner, json={"name": "   "}).status_code == 422


def test_invite_creation_lookup_and_expiry(api):
    http, state, owner, worker, *_ = api
    assert http.post("/api/invites", headers=worker, json={}).status_code == 403
    assert http.post("/api/invites", headers=owner, json={"role": "owner"}).status_code == 422
    response = http.post("/api/invites", headers=owner, json={})
    assert response.status_code == 201, response.text
    code = response.json()["code"]
    assert response.json()["invite_url"] == f"signup.html?invite={code}"
    lookup = http.get("/api/invites/" + code)
    assert lookup.status_code == 200
    assert lookup.json()["business_name"] == "Demo Restaurant"
    assert http.get("/api/invites/missing-code").status_code == 404
    state["invites"][code][3] = datetime.now(timezone.utc)
    assert http.get("/api/invites/" + code).status_code == 410


def test_employee_removal_is_business_scoped_and_revokes_access(api):
    http, state, owner, worker, *_ = api
    assert http.delete("/api/business/team/" + EMPLOYEE, headers=worker).status_code == 403
    assert http.delete("/api/business/team/" + OWNER, headers=owner).status_code == 403
    assert http.delete("/api/business/team/" + OTHER, headers=owner).status_code == 404
    result = http.delete("/api/business/team/" + EMPLOYEE, headers=owner)
    assert result.status_code == 204, result.text
    assert (EMPLOYEE, BUSINESS) not in state["memberships"]
    assert (OTHER, OTHER_BUSINESS) in state["memberships"]
    assert http.get("/api/dashboard/summary", headers=worker).status_code == 403


def test_frontend_mount_does_not_publish_project_secrets(api):
    http, *_ = api
    assert http.get("/.gitignore").status_code == 404
    assert http.get("/backend/security.py").status_code == 404
    assert http.get("/initialschema.sql").status_code == 404
    assert http.get("/signin.html").status_code == 200


def test_expired_invite_is_rejected(api):
    http, state, owner, *_ = api
    response = http.post("/api/invites", headers=owner, json={})
    code = response.json()["code"]
    state["invites"][code][2] = datetime.now(timezone.utc) - timedelta(minutes=1)
    assert http.get("/api/invites/" + code).status_code == 410
