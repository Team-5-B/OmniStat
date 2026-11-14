"""OmniStat ForecastStudio v1: transparent, deterministic sales-history baselines.

Inputs: business_date, product_name, category, signed quantity, signed net revenue.
No order/ingredient demand, inventory levels, holiday features, or probability
coverage is invented. All backtests are strictly time-ordered.
"""

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, ROUND_CEILING
from math import ceil, sqrt
from statistics import mean

HORIZONS = {"week": 7, "month": 30, "quarter": 90, "year": 365}
# Calendar span, NOT verified sales-feed coverage.
MIN_HISTORY = {"week": 28, "month": 56, "quarter": 120, "year": 365}
MIN_ACTIVE = {"week": 4, "month": 8, "quarter": 18, "year": 45}
MODEL_VERSION = "weekday_baseline_v1"


def _date(value):
    return value.date() if hasattr(value, "date") else value


def _series(rows, *, category=None, product=None, today=None, metric="units"):
    today = today or date.today()
    series = defaultdict(float)
    earliest = None
    latest = None
    negatives = 0
    active_dates = set()
    seen = set()
    for day, name, group, quantity, revenue in rows:
        day = _date(day)
        if day > today:
            continue
        # Case-insensitive selection, but do not confuse category-product names.
        if category is not None and (group or "Uncategorized").strip().casefold() != category.strip().casefold():
            continue
        if product is not None and (name or "Unknown product").strip().casefold() != product.strip().casefold():
            continue
        amount = float(Decimal(str(revenue)))
        qty = int(quantity)
        series[day] += qty if metric == "units" else amount
        if qty < 0 or amount < 0:
            negatives += 1
        active_dates.add(day)
        earliest = day if earliest is None else min(earliest, day)
        latest = day if latest is None else max(latest, day)
        seen.add(((name or "Unknown product").strip(), (group or "Uncategorized").strip()))
    return dict(series), {
        "earliest": earliest,
        "latest": latest,
        "active_days": len(active_dates),
        "negative_rows": negatives,
        "products": seen,
    }


def _mean_recent(values, cutoff, window=28):
    start = cutoff - timedelta(days=window - 1)
    return sum(values.get(start + timedelta(days=n), 0.0) for n in range(window)) / window


def _estimate(values, target, cutoff, method):
    if method == "trailing_average":
        baseline = _mean_recent(values, cutoff)
    else:
        # The most recent eight matching weekdays; recent weeks receive more weight.
        weekday_samples = [
            values.get(cutoff - timedelta(days=offset), 0.0)
            for offset in range(55, -1, -1)
            if (cutoff - timedelta(days=offset)).weekday() == target.weekday()
        ]
        weighted = [(i + 1, value) for i, value in enumerate(weekday_samples)]
        baseline = (
            sum(weight * value for weight, value in weighted)
            / sum(weight for weight, _ in weighted)
            if weighted else _mean_recent(values, cutoff)
        )
    return max(0.0, baseline)


def _evaluate(values, earliest, today, method):
    """Four rolling-origin weekly holdouts. No future day in training window."""
    errors = []
    actuals = []
    origins = 0
    for weeks_back in (4, 3, 2, 1):
        cutoff = today - timedelta(days=7 * weeks_back)
        if (cutoff - earliest).days + 1 < 28:
            continue
        origins += 1
        for step in range(1, 8):
            target = cutoff + timedelta(days=step)
            actual = values.get(target, 0.0)
            predicted = _estimate(values, target, cutoff, method)
            errors.append(abs(predicted - actual))
            actuals.append(abs(actual))
    return {
        "origins": origins,
        "mae": round(mean(errors), 4) if errors else None,
        "wape_pct": round(100 * sum(errors) / sum(actuals), 1) if sum(actuals) > 0 else None,
        "absolute_errors": errors,
    }


def forecast_rows(rows, *, horizon="week", today=None, category=None, product=None, days=None):
    """Forecast net unit demand and signed-revenue proxy from observed sales.

    The default model selection is validated on rolling, past-only holdouts.
    Future values are non-negative: returns remain signed in training, but negative
    forecasted units are not treated as physical items to purchase.
    """
    today = today or date.today()
    if days is None:
        if horizon not in HORIZONS:
            raise ValueError("Unsupported forecast horizon")
        days = HORIZONS[horizon]
        minimum = MIN_HISTORY[horizon]
        minimum_active = MIN_ACTIVE[horizon]
    else:
        if not isinstance(days, int) or not 1 <= days <= 120:
            raise ValueError("Custom horizon must be between 1 and 120 days")
        minimum = 28 if days <= 7 else 56 if days <= 30 else 120
        minimum_active = 4 if days <= 7 else 8 if days <= 30 else 18

    units, info = _series(rows, category=category, product=product, today=today)
    revenue, _ = _series(rows, category=category, product=product, today=today, metric="revenue")
    span = (today - info["earliest"]).days + 1 if info["earliest"] else 0
    warnings = [
        "Calendar days without line items are treated as zero; the CSV source does not prove full daily coverage.",
        "Predicted net units are a sales proxy, not ingredient demand or a purchase order.",
    ]
    if info["negative_rows"]:
        warnings.append("Signed refunds/returns reduce training revenue and net quantities.")
    if info["latest"] and (today - info["latest"]).days > 2:
        warnings.append("Sales source is stale: the last recorded business day is over two days ago.")
    if span and info["active_days"] / span < 0.25:
        warnings.append("Sparse active days: observed data may be incomplete or the product may sell infrequently.")
    if days > 90:
        warnings.append("Year-scale outlook is a weekday-only baseline; annual seasonality, holidays, and events are not modeled.")

    base = {
        "status": "insufficient_history",
        "horizon": horizon if days == HORIZONS.get(horizon) else "custom",
        "days": days,
        "forecast_start": (today + timedelta(days=1)).isoformat(),
        "forecast_end": (today + timedelta(days=days)).isoformat(),
        "history_start": info["earliest"].isoformat() if info["earliest"] else None,
        "history_end": today.isoformat(),
        "latest_sales_day": info["latest"].isoformat() if info["latest"] else None,
        "history_span_days": span,
        "active_sales_days": info["active_days"],
        "minimum_history_days": minimum,
        "minimum_active_days": minimum_active,
        "model_version": MODEL_VERSION,
        "metric_basis": "Net signed quantity and net revenue from sales_line_items.business_date",
        "confidence": "unvalidated_baseline",
        "planning_range_disclaimer": "Heuristic scenario range, NOT a calibrated prediction or 95% confidence interval.",
        "warnings": warnings,
        "daily": [],
        "week_buckets": [],
        "month_buckets": [],
        "quarter_buckets": [],
        "totals": None,
        "backtest": None,
        "method": None,
    }
    if span < minimum or info["active_days"] < minimum_active:
        base["warnings"].insert(0, "Insufficient verified historical breadth for this horizon. Upload more dated sales records.")
        return base

    # Independent held-out validation for units and net revenue; select on units MAE.
    models = ("weekday_recent", "trailing_average")
    checked = {name: _evaluate(units, info["earliest"], today, name) for name in models}
    methods = sorted(models, key=lambda name: (checked[name]["mae"] if checked[name]["mae"] is not None else float("inf"), name))
    winner = methods[0] if checked[methods[0]]["mae"] is not None else "weekday_recent"
    evaluated = checked[winner]
    if evaluated["origins"] < 2:
        base["warnings"].append("Too few rolling-origin holdouts for reliable model evaluation.")
    elif evaluated["wape_pct"] is not None and evaluated["wape_pct"] > 50:
        base["warnings"].append("Historical forecast error exceeds 50% WAPE; treat projections as exploratory.")

    future = []
    for step in range(1, days + 1):
        day = today + timedelta(days=step)
        future.append({
            "date": day.isoformat(),
            "units": round(_estimate(units, day, today, winner), 3),
            "revenue": round(_estimate(revenue, day, today, winner), 2),
        })
    total_units = round(sum(x["units"] for x in future), 1)
    total_revenue = round(sum(x["revenue"] for x in future), 2)
    mae = evaluated["mae"]
    # Simple actionable range, explicitly not a probability interval.
    spread = max(total_units * 0.2, (mae or total_units / max(days, 1) * 0.35) * sqrt(days) * 1.5)
    lower = round(max(0.0, total_units - spread), 1)
    upper = round(total_units + spread, 1)

    def buckets(key_func):
        grouping = defaultdict(lambda: {"units": 0.0, "revenue": 0.0})
        for record in future:
            key = key_func(date.fromisoformat(record["date"]))
            grouping[key]["units"] += record["units"]
            grouping[key]["revenue"] += record["revenue"]
        return [{"period": key, "units": round(val["units"], 1), "revenue": round(val["revenue"], 2)}
                for key, val in sorted(grouping.items())]

    base.update({
        "status": "ready",
        "method": winner,
        "confidence": "historical_holdout_evaluated" if evaluated["origins"] >= 2 else "exploratory",
        "backtest": {k: v for k, v in evaluated.items() if k != "absolute_errors"},
        "totals": {
            "expected_net_units": total_units,
            "expected_net_revenue": total_revenue,
            "unit_planning_range_low": lower,
            "unit_planning_range_high": upper,
        },
        "daily": future,
        "week_buckets": buckets(lambda d: f"{d.isocalendar().year}-W{d.isocalendar().week:02d}"),
        "month_buckets": buckets(lambda d: d.strftime("%Y-%m")),
        "quarter_buckets": buckets(lambda d: f"{d.year}-Q{(d.month - 1) // 3 + 1}"),
    })
    return base


def reorder_scenario(forecast, *, on_hand, lead_time_days, safety_days, pack_size):
    """Non-persistent, operator-provided stock scenario in sold-product units.

    No implicit mapping to ingredient stock or inventory_items is attempted.
    """
    if forecast["status"] != "ready":
        return {"status": "insufficient_history", "reason": "Cannot recommend purchases without a usable demand forecast."}
    if on_hand < 0 or lead_time_days < 0 or safety_days < 0 or pack_size < 1:
        raise ValueError("Invalid stock planning inputs")
    exposure_days = lead_time_days + safety_days
    if exposure_days < 1 or exposure_days > forecast["days"]:
        raise ValueError("Forecast must include the entire lead-time and safety window")
    demand = sum(row["units"] for row in forecast["daily"][:exposure_days])
    required = max(0, ceil(demand - on_hand - 1e-9))
    packs = ceil(required / pack_size)
    return {
        "status": "scenario_only",
        "product_unit_basis": "net unit demand; excludes recipes, waste, vendor packs beyond the supplied pack size",
        "on_hand_units_supplied": on_hand,
        "lead_time_days": lead_time_days,
        "safety_days": safety_days,
        "planning_days": exposure_days,
        "forecast_units_during_protection": round(demand, 1),
        "pack_size_units": pack_size,
        "suggested_packs": packs,
        "suggested_product_units": packs * pack_size,
        "stock_alert": "review_reorder" if packs else "no_reorder_indicated",
        "requires_human_review": True,
        "no_inventory_writes": True,
    }
