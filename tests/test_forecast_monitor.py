"""Deterministic cutoff-safe comparison between projected and observed sales."""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from backend.forecast_monitor import evaluate_replay

NOW = date(2026, 11, 13)


def history(units=10, actual_units=None, length=130):
    result = []
    for days_ago in range(1, length + 1):
        day = NOW - timedelta(days=days_ago)
        qty = units if days_ago > 7 or actual_units is None else actual_units
        result.append((day, "Thai Tea", "Beverages", qty, Decimal(qty * 5)))
    return result


def test_perfect_week_replay():
    result = evaluate_replay(history(), window=7, today=NOW)
    assert result["status"] == "evaluated"
    assert result["training_cutoff"] == (NOW - timedelta(days=8)).isoformat()
    assert result["holdout_end"] == (NOW - timedelta(days=1)).isoformat()
    assert result["actual_net_units"] == 70
    assert result["expected_units"] == 70
    assert result["signed_unit_difference"] == 0
    assert result["unit_wape_pct"] == 0
    assert result["observed_activity_days"] == 7


def test_replay_30_day_window():
    result = evaluate_replay(history(), window=30, today=NOW)
    assert result["status"] == "evaluated"
    assert result["actual_net_units"] == 300
    assert result["expected_units"] == 300
    assert len(result["daily"]) == 30


def test_refund_reduces_signed_actuals_and_revenue():
    rows = history()
    rows.append((NOW - timedelta(days=1), "Thai Tea", "Beverages", -2, Decimal("-10.00")))
    result = evaluate_replay(rows, window=7, today=NOW)
    assert result["status"] == "evaluated"
    assert result["expected_units"] == 70
    assert result["actual_net_units"] == 68
    assert result["signed_unit_difference"] == -2
    assert result["actual_net_revenue"] == 340.0
    assert result["net_refund_revenue"] == -10.0
    assert any(a["type"] == "refund_activity" for a in result["alerts"])


def test_current_day_and_future_cannot_enter_holdout():
    rows = history()
    rows.extend([
        (NOW, "Thai Tea", "Beverages", 9999, Decimal("9999")),
        (NOW + timedelta(days=1), "Thai Tea", "Beverages", 9999, Decimal("9999")),
    ])
    result = evaluate_replay(rows, window=7, today=NOW)
    assert result["actual_net_units"] == 70
    assert result["expected_units"] == 70


def test_category_product_scope_case_insensitive():
    rows = history()
    rows.extend((d, "Croissant", "Bakery", 20, Decimal("100")) for d, *_ in history())
    result = evaluate_replay(rows, window=7, today=NOW, category=" beverages ", product="THAI TEA")
    assert result["actual_net_units"] == 70
    assert result["expected_units"] == 70


def test_detects_demand_above_baseline():
    result = evaluate_replay(history(actual_units=20), window=7, today=NOW)
    assert result["actual_net_units"] == 140
    assert any(a["type"] == "above_baseline" for a in result["alerts"])


def test_detects_demand_below_baseline():
    result = evaluate_replay(history(actual_units=3), window=7, today=NOW)
    assert result["actual_net_units"] == 21
    assert any(a["type"] == "below_baseline" for a in result["alerts"])


def test_no_observed_days_does_not_claim_accuracy():
    rows = [r for r in history() if r[0] < NOW - timedelta(days=7)]
    result = evaluate_replay(rows, window=7, today=NOW)
    assert result["status"] == "limited_observation"
    assert result["unit_wape_pct"] is None
    assert any(a["type"] == "limited_observation" for a in result["alerts"])


def test_not_enough_training_history():
    rows = history(length=10)
    result = evaluate_replay(rows, window=7, today=NOW)
    assert result["status"] == "insufficient_history"
    assert result["expected_units"] is None
    assert result["daily"] == []


def test_training_forecast_does_not_depend_on_holdout_values():
    base = evaluate_replay(history(actual_units=10), window=7, today=NOW)
    changed = evaluate_replay(history(actual_units=50), window=7, today=NOW)
    assert base["expected_units"] == changed["expected_units"]
    assert base["actual_net_units"] != changed["actual_net_units"]


def test_invalid_window_rejected():
    with pytest.raises(ValueError, match="7 or 30"):
        evaluate_replay(history(), window=90, today=NOW)


def test_product_without_category_rejected():
    with pytest.raises(ValueError, match="category"):
        evaluate_replay(history(), window=7, today=NOW, product="Tea")
