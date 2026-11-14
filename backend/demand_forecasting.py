"""Read-only, owner-scoped ForecastStudio endpoints for OmniStat."""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator

from backend.database import get_connection
from backend.siddartha_sprint2 import current_owner
from backend.forecast_engine import HORIZONS, forecast_rows, reorder_scenario
from backend.forecast_monitor import evaluate_replay

router = APIRouter(prefix="/api/forecast", tags=["ForecastStudio"])

# Only approved, signed POS sales are forecast; never use inventory as sales.
FORECAST_SOURCE_SQL = """
SELECT business_date, product_name, category,
       COALESCE(SUM(quantity), 0) AS net_units,
       COALESCE(SUM(revenue), 0) AS net_revenue
FROM sales_line_items
WHERE business_id = %s
  AND business_date BETWEEN %s AND %s
GROUP BY business_date, product_name, category
ORDER BY business_date, product_name, category
"""

FRESHNESS_SQL = """
SELECT MAX(processed_at) FROM raw_csv_uploads
WHERE business_id = %s AND status = 'processed'
"""


def _read_sales(business_id, today):
    """Business identity comes from current_owner, never request parameters."""
    since = today - timedelta(days=539)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute(FORECAST_SOURCE_SQL, (business_id, since, today))
            rows = cur.fetchall()
            cur.execute(FRESHNESS_SQL, (business_id,))
            record = cur.fetchone()
    uploaded_at = record[0].isoformat() if record and record[0] else None
    return rows, uploaded_at


def _labels(rows):
    # Group case-insensitively but display the original CSV names.
    found = {}
    for _, product, category, _, _ in rows:
        product = (product or "Unknown product").strip()
        category = (category or "Uncategorized").strip()
        found[(category.casefold(), product.casefold())] = (category, product)
    return sorted(found.values(), key=lambda x: (x[0].casefold(), x[1].casefold()))


@router.get("/overview")
def forecast_overview(
    horizon: str = Query("week", description="week, month, quarter or year"),
    category: str | None = Query(None, max_length=255),
    product: str | None = Query(None, max_length=255),
    top: int = Query(12, ge=1, le=30),
    owner: dict = Depends(current_owner),
):
    if horizon not in HORIZONS:
        raise HTTPException(422, detail="Choose week, month, quarter or year")
    if product and not category:
        raise HTTPException(422, detail="Select a category before selecting a product")
    today = date.today()
    rows, uploaded_at = _read_sales(owner["business_id"], today)
    # Filters are performed AFTER the tenant filter in PostgreSQL.
    result = forecast_rows(rows, horizon=horizon, today=today, category=category, product=product)
    candidates = _labels(rows)
    if category:
        candidates = [p for p in candidates if p[0].casefold() == category.strip().casefold()]
    if product:
        candidates = [p for p in candidates if p[1].casefold() == product.strip().casefold()]
    forecasts = []
    # Prioritize recent product demand; avoid wasting work on a huge historical catalog.
    recent_start = today - timedelta(days=89)
    recent_units = {}
    for day, name, group, qty, _ in rows:
        key = ((group or "Uncategorized").strip().casefold(), (name or "Unknown product").strip().casefold())
        if day >= recent_start:
            recent_units[key] = recent_units.get(key, 0) + int(qty)
    candidates.sort(key=lambda p: (-recent_units.get((p[0].casefold(), p[1].casefold()), 0), p[0], p[1]))
    for group, name in candidates[:top]:
        output = forecast_rows(rows, horizon=horizon, today=today, category=group, product=name)
        forecasts.append({
            "category": group,
            "product": name,
            "status": output["status"],
            "expected_net_units": output["totals"]["expected_net_units"] if output["totals"] else None,
            "unit_planning_range_high": output["totals"]["unit_planning_range_high"] if output["totals"] else None,
            "expected_net_revenue": output["totals"]["expected_net_revenue"] if output["totals"] else None,
            "history_span_days": output["history_span_days"],
        })
    alerts = []
    if result["status"] != "ready":
        alerts.append({"level": "warning", "type": "insufficient_history", "message": "More dated sales history is needed before this horizon can be forecast."})
    if result["latest_sales_day"] and (today - date.fromisoformat(result["latest_sales_day"])).days > 2:
        alerts.append({"level": "warning", "type": "stale_data", "message": "Last observed business day is more than two days old; refresh the POS uploads."})
    if result["backtest"] and result["backtest"]["wape_pct"] is not None and result["backtest"]["wape_pct"] > 50:
        alerts.append({"level": "warning", "type": "high_backtest_error", "message": "Forecast error on historical holdouts is high; review before purchasing."})
    alerts.append({"level": "info", "type": "stock_inputs_required", "message": "Enter actual on-hand stock, supplier lead time and pack size to calculate a tentative reorder scenario."})
    return {
        "scope": "authorized_business_only",
        "source_last_processed_at": uploaded_at,
        "filters": {"horizon": horizon, "category": category, "product": product},
        "forecast": result,
        "products": forecasts,
        "alerts": alerts,
        "read_only": True,
    }


class ReorderScenario(BaseModel):
    category: str = Field(min_length=1, max_length=255)
    product: str = Field(min_length=1, max_length=255)
    on_hand: float = Field(ge=0, le=1_000_000)
    lead_time_days: int = Field(ge=0, le=90)
    safety_days: int = Field(ge=0, le=30)
    pack_size: int = Field(ge=1, le=100_000)

    @model_validator(mode="after")
    def validate_window(self):
        if not self.category.strip() or not self.product.strip():
            raise ValueError("Category and product cannot be blank")
        if self.lead_time_days + self.safety_days < 1:
            raise ValueError("Lead time plus safety days must be at least one")
        return self


@router.post("/reorder-scenario")
def calculate_reorder_scenario(
    body: ReorderScenario,
    owner: dict = Depends(current_owner),
):
    """POST is used for parameters, but never changes inventory or purchases."""
    today = date.today()
    rows, uploaded_at = _read_sales(owner["business_id"], today)
    needed = body.lead_time_days + body.safety_days
    forecast = forecast_rows(rows, today=today, category=body.category, product=body.product, days=needed)
    scenario = reorder_scenario(
        forecast,
        on_hand=body.on_hand,
        lead_time_days=body.lead_time_days,
        safety_days=body.safety_days,
        pack_size=body.pack_size,
    )
    return {
        "category": body.category,
        "product": body.product,
        "source_last_processed_at": uploaded_at,
        "scenario": scenario,
        "forecast": {
            "status": forecast["status"],
            "history_span_days": forecast["history_span_days"],
            "backtest": forecast["backtest"],
            "warnings": forecast["warnings"],
        },
        "read_only": True,
    }


@router.get("/accuracy")
def forecast_accuracy(
    window: int = Query(7, description="Completed reporting days: 7 or 30"),
    category: str | None = Query(None, max_length=255),
    product: str | None = Query(None, max_length=255),
    owner: dict = Depends(current_owner),
):
    """Owner-only read-only historical replay; no stored forecasts are implied."""
    if window not in (7, 30):
        raise HTTPException(422, detail="Choose a 7- or 30-day accuracy window")
    if product and not category:
        raise HTTPException(422, detail="Select a category before a product")
    today = date.today()
    rows, uploaded_at = _read_sales(owner["business_id"], today)
    return {
        "scope": "authorized_business_only",
        "source_last_processed_at": uploaded_at,
        "accuracy": evaluate_replay(
            rows, window=window, today=today, category=category, product=product,
        ),
        "read_only": True,
    }
