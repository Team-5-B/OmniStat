"""Tests for OmniStat's owner-only sales data quality API.

Uses a fake database so tests cannot modify real PostgreSQL data.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from backend import data_quality
from backend import siddartha_sprint2
from backend.main import app
from backend.security import create_access_token


OWNER = "11111111-1111-1111-1111-111111111111"
EMPLOYEE = "22222222-2222-2222-2222-222222222222"
BUSINESS = "44444444-4444-4444-4444-444444444444"


class FakeCursor:
    def __init__(self, state):
        self.state = state
        self.result = None
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params=()):
        sql = " ".join(query.lower().split())
        self.state["queries"].append((sql, params))

        if "select m.role from memberships as m" in sql:
            roles = {
                (OWNER, BUSINESS): "owner",
                (EMPLOYEE, BUSINESS): "employee",
            }
            role = roles.get(tuple(params))
            self.result = (role,) if role else None

        elif "from raw_csv_uploads" in sql:
            assert params == (BUSINESS,)
            self.result = (
                3, 2, 1, 0,
                datetime(2026, 11, 4, tzinfo=timezone.utc),
            )

        elif sql.startswith("select") and "from sales_line_items" in sql and "sum(quantity)" in sql:
            assert params[0] == BUSINESS
            self.result = (8, 20, Decimal("120.50"))

        elif "with line_days as" in sql:
            assert params[0] == BUSINESS
            assert params[3] == BUSINESS
            self.rows = self.state["mismatches"]

        else:
            raise AssertionError(f"Unexpected SQL: {query}")

    def fetchone(self):
        return self.result

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, state):
        self.state = state

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return FakeCursor(self.state)


@pytest.fixture
def api(monkeypatch):
    state = {"queries": [], "mismatches": []}

    monkeypatch.setenv(
        "JWT_SECRET_KEY",
        "omnistat-test-secret-with-more-than-32-characters",
    )

    monkeypatch.setattr(
        data_quality,
        "get_connection",
        lambda: FakeConnection(state),
    )

    monkeypatch.setattr(
        siddartha_sprint2,
        "get_connection",
        lambda: FakeConnection(state),
    )

    previous_overrides = dict(app.dependency_overrides)
    app.dependency_overrides.clear()

    client = TestClient(app)

    owner_headers = {
        "Authorization": "Bearer " + create_access_token(
            OWNER, BUSINESS
        )
    }

    employee_headers = {
        "Authorization": "Bearer " + create_access_token(
            EMPLOYEE, BUSINESS
        )
    }

    try:
        yield client, state, owner_headers, employee_headers
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


def test_correct_sales_totals(api):
    """Matching sales totals should produce an OK status."""
    client, state, owner, _ = api

    response = client.get(
        "/api/business/data-quality",
        headers=owner,
    )

    assert response.status_code == 200

    result = response.json()

    assert result["status"] == "ok"
    assert result["mismatch_days"] == 0
    assert result["line_items"]["net_sales"] == 120.50
    assert result["line_items"]["net_units"] == 20
    assert result["uploads"]["processed"] == 2

    # Verify the audit never writes to the database.
    assert all(
        sql.startswith(("select", "with"))
        for sql, _ in state["queries"]
    )


def test_reject_unauthorized_users(api):
    """Only authenticated business owners can view the audit."""
    client, _, owner, employee = api

    response = client.get("/api/business/data-quality")
    assert response.status_code == 401

    response = client.get(
        "/api/business/data-quality",
        headers=employee,
    )
    assert response.status_code == 403

    response = client.get(
        "/api/business/data-quality",
        headers=owner,
    )
    assert response.status_code == 200


def test_detect_incorrect_dashboard_totals(api):
    """Detect missing summaries and mismatched revenue."""
    client, state, owner, _ = api

    today = date.today()

    state["mismatches"] = [
        (
            today,
            2,
            4,
            Decimal("25.00"),
            None,
            None,
            True,
            False,
        ),
        (
            today - timedelta(days=1),
            1,
            2,
            Decimal("10.00"),
            1,
            Decimal("8.00"),
            True,
            True,
        ),
    ]

    response = client.get(
        "/api/business/data-quality",
        headers=owner,
    )

    assert response.status_code == 200

    result = response.json()

    assert result["status"] == "needs_review"
    assert result["mismatch_days"] == 2
    assert result["issues"][0]["issue"] == "missing_daily_summary"
    assert result["issues"][1]["issue"] == "totals_mismatch"


def test_supported_reporting_periods(api):
    """The endpoint must support 7, 30, and 90 days."""
    client, _, owner, _ = api

    for days in (7, 30, 90):
        response = client.get(
            f"/api/business/data-quality?days={days}",
            headers=owner,
        )

        assert response.status_code == 200
        assert response.json()["period"]["days"] == days


def test_invalid_reporting_periods(api):
    """Reject unsupported reporting periods."""
    client, _, owner, _ = api

    for days in (0, -1, 8, 365):
        response = client.get(
            f"/api/business/data-quality?days={days}",
            headers=owner,
        )

        assert response.status_code == 422
