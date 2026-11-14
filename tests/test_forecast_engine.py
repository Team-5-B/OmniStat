"""Deterministic unit tests; no database or external ML services required."""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from backend.forecast_engine import forecast_rows, reorder_scenario, HORIZONS

TODAY = date(2026, 11, 12)


def example(days=400):
    rows = []
    for days_back in range(days):
        day = TODAY - timedelta(days=days_back)
        tea = 16 if day.weekday() >= 5 else 8
        rows.append((day, "Thai Tea", "Beverages", tea, Decimal(tea * 5)))
        rows.append((day, "Croissant", "Bakery", 4, Decimal("16.00")))
    rows.append((TODAY, "Thai Tea", "Beverages", -2, Decimal("-10.00")))
    return rows


@pytest.mark.parametrize("horizon,days", list(HORIZONS.items()))
def test_horizons_generate_daily_and_buckets(horizon, days):
    result = forecast_rows(example(), horizon=horizon, today=TODAY)
    assert result["status"] == "ready"
    assert len(result["daily"]) == days
    assert result["days"] == days
    assert result["daily"][0]["date"] == (TODAY + timedelta(days=1)).isoformat()
    assert result["daily"][-1]["date"] == (TODAY + timedelta(days=days)).isoformat()
    assert result["totals"]["expected_net_units"] > 0
    assert result["week_buckets"] and result["month_buckets"] and result["quarter_buckets"]


def test_sparse_history_fails_closed():
    result = forecast_rows(example(7), horizon="week", today=TODAY)
    assert result["status"] == "insufficient_history"
    assert result["totals"] is None
    assert not result["daily"]


def test_one_month_history_not_sufficient_for_annual_forecast():
    assert forecast_rows(example(30), horizon="year", today=TODAY)["status"] == "insufficient_history"


def test_product_category_filter_is_case_insensitive():
    tea = forecast_rows(example(), horizon="week", today=TODAY, category=" beverages ", product="thai TEA")
    bread = forecast_rows(example(), horizon="week", today=TODAY, category="bakery", product="Croissant")
    assert tea["status"] == bread["status"] == "ready"
    assert tea["totals"]["expected_net_units"] > bread["totals"]["expected_net_units"]
    assert tea["totals"]["expected_net_revenue"] > 0


def test_future_records_cannot_leak_into_training_or_backtest():
    old = example()
    projected = forecast_rows(old, horizon="week", today=TODAY)
    old.append((TODAY + timedelta(days=1), "Thai Tea", "Beverages", 1_000_000, Decimal("9000000")))
    assert forecast_rows(old, horizon="week", today=TODAY) == projected


def test_refunds_are_signed_in_history_and_explained():
    result = forecast_rows(example(), horizon="week", today=TODAY, category="Beverages")
    assert any("refund" in warning.lower() for warning in result["warnings"])
    assert result["metric_basis"].startswith("Net signed")


def test_holdout_validation_is_time_ordered():
    result = forecast_rows(example(), horizon="month", today=TODAY)
    assert result["backtest"]["origins"] == 4
    assert result["backtest"]["mae"] is not None
    assert result["confidence"] == "historical_holdout_evaluated"
    assert 0 <= result["backtest"]["wape_pct"] < 100


def test_reorder_rounds_to_product_pack_and_never_purchases_negative():
    forecast = forecast_rows(example(), days=8, today=TODAY, category="Beverages", product="Thai Tea")
    result = reorder_scenario(forecast, on_hand=2, lead_time_days=5, safety_days=3, pack_size=6)
    assert result["status"] == "scenario_only"
    assert result["suggested_packs"] >= 1
    assert result["suggested_product_units"] % 6 == 0
    assert result["requires_human_review"]
    assert result["no_inventory_writes"]
    no_order = reorder_scenario(forecast, on_hand=99999, lead_time_days=5, safety_days=3, pack_size=6)
    assert no_order["suggested_product_units"] == 0


def test_reorder_rejects_invalid_protection_period():
    forecast = forecast_rows(example(), days=7, today=TODAY)
    with pytest.raises(ValueError):
        reorder_scenario(forecast, on_hand=0, lead_time_days=8, safety_days=1, pack_size=1)


def test_stale_history_alert():
    cutoff_rows = [(d, p, c, q, r) for d, p, c, q, r in example() if d <= TODAY - timedelta(days=7)]
    report = forecast_rows(cutoff_rows, horizon="week", today=TODAY)
    assert any("stale" in w for w in report["warnings"])


def test_custom_horizon_validation():
    with pytest.raises(ValueError):
        forecast_rows(example(), days=121, today=TODAY)
    with pytest.raises(ValueError):
        forecast_rows(example(), horizon="decade", today=TODAY)


def test_empty_sales_returns_no_fake_forecast():
    result = forecast_rows([], horizon="week", today=TODAY)
    assert result["status"] == "insufficient_history"
    assert result["totals"] is None
