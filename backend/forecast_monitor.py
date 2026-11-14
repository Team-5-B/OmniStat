"""DemandPulse: leakage-safe historical replay of ForecastStudio unit forecasts.

The replay is computed when requested, not a previously stored forecast. The
comparison period includes only fully completed business dates and preserves
signed refund quantities and revenue. No inventory or alert rows are written.
"""
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from backend.forecast_engine import forecast_rows

ALLOWED_WINDOWS = (7, 30)


def _matches(value, requested, fallback):
    return requested is None or (value or fallback).strip().casefold() == requested.strip().casefold()


def evaluate_replay(rows, *, window=7, today=None, category=None, product=None):
    """Compare a cutoff-only forecast with observed signed sales afterward.

    The holdout is the last 7 or 30 *completed* business days (yesterday is
    the latest). A date without source rows is an unverified gap, not an
    established day of zero transactions.
    """
    if window not in ALLOWED_WINDOWS:
        raise ValueError("Replay window must be 7 or 30 days")
    if product is not None and (category is None or not category.strip()):
        raise ValueError("Product comparison requires category scope")

    today = today or date.today()
    end = today - timedelta(days=1)
    start = end - timedelta(days=window - 1)
    training_end = start - timedelta(days=1)

    baseline = forecast_rows(
        rows,
        days=window,
        today=training_end,
        category=category,
        product=product,
    )
    actual_units = defaultdict(int)
    actual_revenue = defaultdict(lambda: Decimal("0"))
    observed_days = set()
    refund_rows = 0
    refund_revenue = Decimal("0")

    for business_day, name, group, quantity, revenue in rows:
        if hasattr(business_day, "date"):
            business_day = business_day.date()
        if not start <= business_day <= end:
            continue
        if not _matches(group, category, "Uncategorized"):
            continue
        if not _matches(name, product, "Unknown product"):
            continue
        units = int(quantity)
        amount = Decimal(str(revenue))
        actual_units[business_day] += units
        actual_revenue[business_day] += amount
        observed_days.add(business_day)
        if units < 0 or amount < 0:
            refund_rows += 1
            if amount < 0:
                refund_revenue += amount

    common = {
        "window_days": window,
        "holdout_start": start.isoformat(),
        "holdout_end": end.isoformat(),
        "training_cutoff": training_end.isoformat(),
        "category": category,
        "product": product,
        "forecast_method": baseline["method"],
        "model_version": baseline["model_version"],
        "observed_activity_days": len(observed_days),
        "coverage_note": (
            "Dates without sales rows cannot be distinguished from missing POS uploads. "
            "This is a historical replay, not a forecast saved before the period."
        ),
        "refund_rows": refund_rows,
        "net_refund_revenue": round(float(refund_revenue), 2),
        "read_only": True,
        "alerts": [],
        "daily": [],
    }

    if baseline["status"] != "ready":
        return {
            **common,
            "status": "insufficient_history",
            "reason": "Historical records before the evaluation window are insufficient for a replay.",
            "minimum_history_days": baseline["minimum_history_days"],
            "expected_units": None,
            "actual_net_units": sum(actual_units.values()),
            "signed_unit_difference": None,
            "expected_revenue": None,
            "actual_net_revenue": round(float(sum(actual_revenue.values(), Decimal("0"))), 2),
            "signed_revenue_difference": None,
            "unit_wape_pct": None,
            "unit_mae": None,
            "unit_bias_pct": None,
        }

    projected = {date.fromisoformat(item["date"]): item for item in baseline["daily"]}
    daily = []
    for i in range(window):
        day = start + timedelta(days=i)
        item = projected[day]
        daily.append({
            "day": day.isoformat(),
            "observed": day in observed_days,
            "expected_units": item["units"],
            "actual_net_units": actual_units.get(day, 0),
            "expected_revenue": item["revenue"],
            "actual_net_revenue": round(float(actual_revenue.get(day, Decimal("0"))), 2),
        })

    expected_units = sum(x["expected_units"] for x in daily)
    actual_total_units = sum(x["actual_net_units"] for x in daily)
    expected_revenue = sum(x["expected_revenue"] for x in daily)
    actual_total_revenue = sum(actual_revenue.values(), Decimal("0"))

    min_observed = 3 if window == 7 else 10
    observed_enough = len(observed_days) >= min_observed
    # Error metrics are withheld if we lack enough observed dates.
    # Otherwise a missing CSV could masquerade as a large demand collapse.
    abs_error = sum(abs(x["expected_units"] - x["actual_net_units"]) for x in daily)
    denominator = sum(abs(x["actual_net_units"]) for x in daily)
    status = "evaluated" if observed_enough else "limited_observation"
    alerts = []
    if not observed_enough:
        alerts.append({
            "type": "limited_observation", "level": "warning",
            "message": f"Only {len(observed_days)} of {window} dates contain sales rows. Confirm POS coverage before acting.",
        })
    else:
        deviation = actual_total_units - expected_units
        if expected_units >= 5 and deviation >= max(3, expected_units * 0.3):
            alerts.append({
                "type": "above_baseline", "level": "review",
                "message": "Observed net unit demand exceeded the historical baseline. Review future stock assumptions.",
            })
        elif expected_units >= 5 and -deviation >= max(3, expected_units * 0.3):
            alerts.append({
                "type": "below_baseline", "level": "review",
                "message": "Observed net unit demand fell below the historical baseline. Review sales coverage and demand changes.",
            })
        if denominator > 0 and 100 * abs_error / denominator > 50:
            alerts.append({
                "type": "high_replay_error", "level": "warning",
                "message": "Weekly/monthly replay error exceeds 50% WAPE; do not rely on this baseline for automatic purchasing.",
            })
    if refund_rows:
        alerts.append({
            "type": "refund_activity", "level": "info",
            "message": f"{refund_rows} refund/negative sale row(s) contributed to net totals during the evaluation window.",
        })

    return {
        **common,
        "status": status,
        "reason": "Historical replay is available." if observed_enough else "Source-day activity is too sparse to evaluate reliability.",
        "expected_units": round(expected_units, 2),
        "actual_net_units": actual_total_units,
        "signed_unit_difference": round(actual_total_units - expected_units, 2),
        "expected_revenue": round(expected_revenue, 2),
        "actual_net_revenue": round(float(actual_total_revenue), 2),
        "signed_revenue_difference": round(float(actual_total_revenue) - expected_revenue, 2),
        "unit_mae": round(abs_error / window, 2) if observed_enough else None,
        "unit_wape_pct": round(100 * abs_error / denominator, 1) if observed_enough and denominator > 0 else None,
        "unit_bias_pct": round(100 * (actual_total_units - expected_units) / expected_units, 1) if observed_enough and expected_units > 0 else None,
        "alerts": alerts,
        "daily": daily,
    }
