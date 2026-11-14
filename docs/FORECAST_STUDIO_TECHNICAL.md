# ForecastStudio v1 — technical specification and verification

## Scope

ForecastStudio is an **experimental, read-only planning feature**. Unlike an ML marketing demo, it does not claim statistically calibrated future accuracy or guaranteed stock needs. It reuses the OmniStat signed sales contract and business_date policy. User-facing forecasts are gated on historical span and active sales days.

### API

- `GET /api/forecast/overview?horizon=week|month|quarter|year&category=...&product=...&top=12`
  - Owner-only, business ID from verified membership, never supplied by URL.
  - `forecast` contains `status`, `method`, `totals`, `daily`, grouped week/month/quarter buckets, backtest errors, warnings, and source horizon.
  - `products` contains up to 30 category/product forecast summaries; all are derived from the authorized tenant's data.
  - `alerts` describe insufficient history, data staleness, high backtest WAPE and the need for verified stock inputs.
- `POST /api/forecast/reorder-scenario` JSON body:
  ```json
  {"category":"Beverages","product":"Thai Tea","on_hand":25,"lead_time_days":7,"safety_days":2,"pack_size":12}
  ```
  - Read-only calculation with no purchase order, inventory update, or persisted changes.
  - Suggested product units = ceil(max(0, expected net units over lead-time + safety days − user-entered stock) / pack size) × pack size.
  - An insufficient forecast returns `insufficient_history` rather than fabricated order units.

### Source contract

```sql
SELECT business_date, product_name, category,
       COALESCE(SUM(quantity), 0) AS net_units,
       COALESCE(SUM(revenue), 0) AS net_revenue
FROM sales_line_items
WHERE business_id = %s AND business_date BETWEEN %s AND %s
GROUP BY business_date, product_name, category
ORDER BY business_date, product_name, category
```

The filter for `business_id` is bound to `current_owner`. Historical net revenue is signed `NUMERIC` in PostgreSQL and converted to JSON-friendly chart numbers at the reporting boundary. Forecast output is a heuristic prediction and **not a ledger amount**; rounding is for presentation only. Refund rows reduce net unit demand and net revenue. Reporting dates use `business_date`; upload timestamps are used solely as data-freshness evidence.

**Known data-quality gap:** Without a complete daily ingestion coverage map, dates with no line items are treated as zero in time-series features. Such zero imputation may be wrong when a file was not uploaded; the API and UI explicitly warn. Before production planning decisions, implement source coverage / missing-day detection.

### Forecast algorithm

1. Read up to 540 calendar days of date/category/product-aggregated sales for the signed-in business.
2. For each series (net units and net revenue), compare a weekday recent-history mean and a trailing-28-day mean.
3. Select the model with lower absolute error over four rolling-origin seven-day holdout periods, only using data **on or before each holdout cutoff**. If there are too few holdouts, use the weekday baseline and label the result exploratory.
4. Predict the next 7, 30, 90 or 365 days. Model output is nonnegative because a negative number is not a physical quantity to prepare or purchase. Historical negatives remain signed.
5. Summarize by ISO week, calendar month and quarter. Report a heuristic ±20%-minimum planning band derived in part from holdout MAE and square-root horizon scaling. **Do not describe this as a statistical 95% prediction interval.**
6. Return historical WAPE only when the holdout actuals are positive; otherwise use `null`/N/A rather than zero.

Minimum calendar/active history thresholds: 7-day = 28/4; 30-day = 56/8; 90-day = 120/18; 365-day = 365/45. These are conservative **engineering heuristics**, not validated business-quality thresholds. Annual forecasts cannot capture annual seasonality in this baseline; the UI warns.

### Implementation files

- `backend/forecast_engine.py`: **revenue/units calculations, cutoff-safe holdouts, planning range, reorder formula**.
- `backend/demand_forecasting.py`: **business isolation, owner dependency, SQL scope, freshness, API response**.
- `forecast-studio.html`, `forecast-studio.css`, `forecast-studio.js`: navigation, filters, SVG chart, tables, scenarios and alerts.
- `forecast-preview.js`, `forecast-preview.css`: additive main dashboard preview.
- `install_forecaststudio.py`: idempotent route/HTML insertion, conflict prevention and backup of existing files.
- `tests/test_forecast_engine.py` and `tests/test_forecast_api.py`: deterministic regression suite.
- `scripts/forecast_demo.py`: 400-day synthetic, non-database demo.
- `scripts/forecast_pg_plan.py`: optional real PostgreSQL read-only query plan for one tenant.

### Exact verification commands

Run from repo root (in `OmniStat-2`, create `.venv` if needed):

```bash
./.venv/bin/python -m pytest -q tests/test_forecast_engine.py tests/test_forecast_api.py
./.venv/bin/python -m pytest -q
node --check forecast-studio.js
node --check forecast-preview.js
./.venv/bin/python - <<'PY'
from backend.main import app
paths=app.openapi()["paths"]
for path in ("/api/forecast/overview", "/api/forecast/reorder-scenario"):
    assert path in paths, path
    print("Registered:",path)
PY
./.venv/bin/python -m scripts.forecast_demo
```

Optional **real PostgreSQL evidence** (requires a known local development business UUID and a running database):

```bash
DB_NAME=omnistat ./.venv/bin/python -m scripts.forecast_pg_plan --business-id YOUR_BUSINESS_UUID
```

This runs five `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` executions on the **same data** and saves measured times/plan to `docs/FORECAST_STUDIO_POSTGRES_PLAN.md`. No index is changed, so it is **not** a before/after optimization claim. Do not run against production without approval; EXPLAIN ANALYZE executes the read-only SELECT.

### Suggested local browser demo

```bash
./.venv/bin/python -m uvicorn backend.main:app --env-file .env --reload --port 8010
```

Open `http://127.0.0.1:8010/dashboard.html` and click **ForecastStudio**. Sign in as owner. Try week/month/quarter/year and compare sufficient-history with insufficient-history states. Under one product, enter genuine on-hand stock + lead time + safety days + pack size; confirm the result says **review**, not **order placed**. With only 30 days of uploaded data, long horizons must show insufficient history.

### Tradeoff to review

A transparent weekday baseline can be audited and backtested without a heavyweight ML dependency. It cannot model holidays, promotions, inflation, closures, sudden menu changes, or annual seasonality. It also cannot distinguish true zero-sale days from missing source coverage. Improve coverage instrumentation and real rolling backtests across multiple businesses **before** deploying more complex models or automated purchasing.

## DemandPulse v1 addition

The updated release also includes `GET /api/forecast/accuracy?window=7|30`. It reconstructs a *historical* baseline with a hard training cutoff preceding the observed period and compares signed net units and revenue with completed reporting days. The dashboard displays signed variance, WAPE only when enough observed days exist, refund signals and explicitly limited data-coverage evidence. No past forecast is claimed to have been persisted. Consult `docs/DEMANDPULSE_TECHNICAL.md` for formulas, security checks, thresholds and tradeoffs.
