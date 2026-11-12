"""Regression tests for the daily revenue investigation."""

from datetime import date
from decimal import Decimal

import pytest

from backend import data_quality


DAY = date(2026, 11, 10)
BEFORE = date(2026, 11, 9)
AFTER = date(2026, 11, 11)

BUSINESS_A = "11111111-1111-1111-1111-111111111111"
BUSINESS_B = "22222222-2222-2222-2222-222222222222"


def record(number, day, amount, units=1):
    return (
        str(number),
        day,
        f"Product {number}",
        "Beverages",
        units,
        Decimal(amount),
        "33333333-3333-3333-3333-333333333333",
        "sales_import.csv",
    )


class FakeCursor:
    def __init__(self, state):
        self.state = state
        self.one = None
        self.many = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        sql = " ".join(sql.lower().split())
        self.state["queries"].append((sql, params))

        if sql.startswith("set transaction"):
            assert "read only" in sql
            return

        assert "business_id = %s" in sql

        business_id, day = params[:2]

        records = self.state["records"].get(
            (business_id, day), []
        )

        if "from daily_sales_aggregates" in sql:
            self.one = self.state["summaries"].get(
                (business_id, day)
            )

        elif "left join raw_csv_uploads" in sql:
            assert "u.business_id = s.business_id" in sql

            limit, offset = params[2:]
            self.many = records[offset:offset + limit]

        elif "from sales_line_items" in sql:
            self.one = (
                len(records),
                sum(
                    (row[5] for row in records),
                    Decimal("0"),
                ),
                sum(row[4] for row in records),
            )

        else:
            raise AssertionError(f"Unexpected SQL: {sql}")

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.many


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
def database(monkeypatch):
    state = {
        "queries": [],
        "summaries": {
            (BUSINESS_A, DAY): (Decimal("150.00"), 2),
            (BUSINESS_B, DAY): (Decimal("999.00"), 1),
        },
        "records": {
            (BUSINESS_A, DAY): [
                record(1, DAY, "120.00", 2),
                record(2, DAY, "-20.00", -1),
                record(3, DAY, "50.00", 1),
            ],
            (BUSINESS_A, BEFORE): [
                record(4, BEFORE, "500.00"),
            ],
            (BUSINESS_A, AFTER): [
                record(5, AFTER, "300.00"),
            ],
            (BUSINESS_B, DAY): [
                record(6, DAY, "999.00"),
            ],
        },
    }

    monkeypatch.setattr(
        data_quality,
        "get_connection",
        lambda: FakeConnection(state),
    )

    return state


def investigate(business_id=BUSINESS_A, day=DAY,
                page=1, page_size=25):
    return data_quality.daily_sales_discrepancy(
        day=day,
        page=page,
        page_size=page_size,
        owner={"business_id": business_id},
    )


def test_matching_totals(database):
    result = investigate()

    assert result["status"] == "matching"
    assert result["stored"]["net_revenue"] == 150.0
    assert result["recomputed"]["net_revenue"] == 150.0
    assert result["difference"]["net_revenue"] == 0.0


def test_mismatched_totals(database):
    database["summaries"][(BUSINESS_A, DAY)] = (
        Decimal("170.00"), 2
    )

    result = investigate()

    assert result["status"] == "mismatch"
    assert result["recomputed"]["net_revenue"] == 150.0
    assert result["difference"]["net_revenue"] == -20.0


def test_missing_daily_summary(database):
    del database["summaries"][(BUSINESS_A, DAY)]

    result = investigate()

    assert result["status"] == "missing_summary"
    assert result["stored"]["net_revenue"] is None
    assert result["recomputed"]["net_revenue"] == 150.0
    assert result["difference"]["net_revenue"] is None


def test_refunds_are_signed(database):
    result = investigate()

    assert result["recomputed"]["net_revenue"] == 150.0
    assert result["recomputed"]["net_units"] == 2

    refund = result["records"][1]

    assert refund["net_revenue"] == -20.0
    assert refund["quantity"] == -1


def test_reporting_day_boundaries(database):
    result = investigate(day=DAY)

    assert result["recomputed"]["record_count"] == 3
    assert all(
        item["business_date"] == DAY.isoformat()
        for item in result["records"]
    )

    before = investigate(day=BEFORE)
    after = investigate(day=AFTER)

    assert before["recomputed"]["net_revenue"] == 500.0
    assert after["recomputed"]["net_revenue"] == 300.0


def test_pagination(database):
    first = investigate(page=1, page_size=2)
    second = investigate(page=2, page_size=2)

    assert len(first["records"]) == 2
    assert len(second["records"]) == 1

    assert first["pagination"]["has_next"] is True
    assert second["pagination"]["has_next"] is False

    assert first["records"][0]["id"] != second["records"][0]["id"]


def test_business_isolation(database):
    business_a = investigate(BUSINESS_A)
    business_b = investigate(BUSINESS_B)

    assert business_a["recomputed"]["net_revenue"] == 150.0
    assert business_b["recomputed"]["net_revenue"] == 999.0

    for sql, params in database["queries"]:
        if sql.startswith("set transaction"):
            continue

        assert params[0] in (BUSINESS_A, BUSINESS_B)
        assert "business_id = %s" in sql


def test_no_sales_empty_state(database):
    result = investigate(
        day=date(2026, 11, 1)
    )

    assert result["status"] == "no_data"
    assert result["records"] == []
    assert result["pagination"]["total_records"] == 0


def test_quantity_discrepancy(database):
    database["summaries"][(BUSINESS_A, DAY)] = (
        Decimal("150.00"), 5
    )

    result = investigate()

    assert result["status"] == "mismatch"
    assert result["difference"]["net_revenue"] == 0.0
    assert result["difference"]["net_units"] == -3


def test_source_upload_reference(database):
    result = investigate()

    assert result["records"][0]["upload_filename"] == (
        "sales_import.csv"
    )
    assert result["records"][0]["upload_id"] is not None
