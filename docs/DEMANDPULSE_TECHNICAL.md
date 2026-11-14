# DemandPulse — forecast replay and operator variance signals

## What it answers

- *How many product units did OmniStat expect last week or month using only information available before that period?*
- *How many net units and how much signed revenue appeared in the actual POS sales records?*
- *Which direction did demand move from the baseline, and how large were the daily errors?*
- *Which deviations or refunds should a business owner review before adjusting purchasing assumptions?*

## API and business authorization

`GET /api/forecast/accuracy?window=7|30&category=optional&product=optional`

The FastAPI route is defined in `backend/demand_forecasting.py`, depends on `current_owner`, and calls `_read_sales(owner["business_id"], today)`. Its SQL filters **`sales_line_items.business_id = %s`** with an authorized owner-derived ID. User-supplied `business_id` query parameters are ignored. It is read-only; source queries are executed in a `SET TRANSACTION READ ONLY` transaction. Product filters require a category. Signed refund rows are not discarded.

## Calculations, leakage control, and provenance

For `today=T` and `window=W`:

- Last fully closed reporting day: **T − 1**. Current partial day is excluded.
- Evaluation start: **T − W**. Training cutoff: **T − W − 1**.
- Reconstruct a forecast with `forecast_rows(rows, today=cutoff, days=W, ...)`. The engine excludes every sales line after the cutoff when estimating the baseline and selecting its model.
- Actual observations are signed sums of `quantity` and `revenue` for `business_date BETWEEN start AND T−1`, filtered by the same category/product scope.
- **Signed unit difference = actual net units − reconstructed expected net units.** Revenue difference is defined identically.
- **Unit MAE = sum over days of |expected units − actual net units| / W.**
- **Unit WAPE = 100 × sum daily absolute errors / sum of |actual daily net units|**, where the denominator is positive.
- A WAPE result is withheld if fewer than **3 active days (7-day replay)** or **10 active days (30-day replay)** contain source rows. This is a *heuristic* gate, not proof of complete POS coverage.
- If training history is insufficient, no fictitious expected totals or WAPE are returned.
- Returned daily rows contain the activity flag, signed actual units/revenue, and baseline units/revenue; refunds are counted separately.

**Never call this a previously stored forecast or a production-calibrated model.** Missing reporting dates may be legitimate zero-sales days, closures or an unuploaded POS batch. The feature cannot distinguish these scenarios yet.

## Signals

- `above_baseline`: actual unit demand > forecast by at least **30% and 3 units** where expected ≥ 5.
- `below_baseline`: analogous downside deviation.
- `high_replay_error`: unit WAPE > 50%, if the observation gate was met.
- `limited_observation`: too few dates with source rows to interpret accuracy reliably.
- `refund_activity`: signed negative quantity or net revenue row in the observed period.

Signals are **threshold-based review suggestions**. They do not establish stockouts, overstock, fraud, supplier shortages, or financial loss.

## Data model and code map

- `backend/forecast_engine.py` — cutoff-safe forecast baselines and historic rolling-origin selection.
- `backend/forecast_monitor.py` — DemandPulse replay/accuracy/alert logic.
- `backend/demand_forecasting.py` — owner-only FastAPI routes and business-scoped PostgreSQL queries.
- `forecast-studio.html`, `forecast-accuracy.js`, `forecast-accuracy.css` — accessible comparison controls, chart and alerts, connected to existing category/product selections.
- `tests/test_forecast_monitor.py`, `tests/test_forecast_monitor_api.py` — deterministic boundaries, signed refunds, tenant isolation and auth.

## Engineering decisions and limitations

1. **Historical replay rather than persisted forecast versions** keeps this increment read-only and deployable without migrations. Later releases should persist signed forecast snapshots with model/feature versions to audit what was actually visible to a user at a prior date.
2. **Business-day date, not upload timestamp** is used for both training and evaluation; this retains OmniStat's original reporting date policy.
3. **WAPE on signed net units** can appear large around refunds or zero demand. The UI shows the observed total and refund signals, instead of hiding those cases.
4. The baseline is **not ingredient-level**. Actual purchasing recommendations need verified recipes, inventory balances, yield/waste, vendor lead times and case-size units.
5. CSV coverage gaps, holiday closures and promotions are not modeled. Add a daily ingestion coverage table and explicit close-of-business cutoff before alerts influence operations.

## Tests and demonstration

```bash
./.venv/bin/python -m pytest -v tests/test_forecast_monitor.py tests/test_forecast_monitor_api.py
./.venv/bin/python -m pytest -q
node --check forecast-accuracy.js
```

An optional EXPLAIN is supplied by `scripts/forecast_pg_plan.py` for the shared tenant-scoped sales aggregation, but **there is no published query-plan timing for your local database until you run it**. The feature adds no new index and does not claim a speedup.
