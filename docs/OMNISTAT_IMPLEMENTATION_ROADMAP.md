# OmniStat execution guide — from research to a credible product

**Baseline:** *OmniStat Competitive Intelligence & Advanced Product Architecture* (the 31-page research paper bundled under `docs/research`). The paper contains 129 proposed capabilities, 52 scoped backlog tasks, and a longer staged product vision. This guide intentionally does **not** claim those capabilities are already implemented.

## Product thesis

**Connect → Validate → Define → Analyze → Explain → Plan → Act (with human approval).** Compete by making operational numbers reliable, traceable and useful, not by claiming an unvalidated AI model can automate a restaurant.

## Do these things first, in order

| Sequence | Milestone | Why it precedes the next step | Deliverable / release gate |
|---|---|---|---|
| **0.1** | Protect data and metrics | No forecast should train on duplicated or mismatched reports | Signed net revenue, reporting day, refunds and owner isolation regression tests; read-only reconciliation proof |
| **0.2** | Confirm source completeness | A blank CSV day can mean zero sales **or** absent data | A daily source-coverage / upload-freshness contract. Until this exists, explicitly warn when assuming zero |
| **1.1 — IN THIS ZIP** | **ForecastStudio v1** | Establish a reproducible non-AI baseline | Rolling 7/30/90/365-day horizons, product/category filter, demand/revenue charts, date-range buckets, time-ordered holdouts, owner-only API |
| **1.2 — IN THIS ZIP** | **What-if purchase planner** | Turn demand estimates into a decision without editing inventory | Actual on-hand, supplier lead time, safety days, units per pack are mandatory operator inputs; read-only reorder scenario |
| **1.3 — IN THIS ZIP** | **Forecast alerts and evidence** | Make weak data visible before someone orders stock | Stale-source, insufficient history, high holdout-error warnings; model version and source dates in UI |
| **2.1** | Real catalog ↔ inventory mapping | Sold products are not raw ingredients | Canonical item IDs, recipe bill of materials, physical counts, unit conversions, vendor pack sizes |
| **2.2** | Cost and vendor connectors | Advice should reflect economics and sourcing | Verified ingredient costs, lead times, invoices and vendor minimums |
| **3.1** | Persistent planning snapshots | Users need saved, reproducible forecasts | Versioned forecast runs, training cutoff, source watermark, noneditable history |
| **3.2** | Action/alert inbox | Owners need an accountable workflow | Acknowledge, resolve, assign, deduplicate and audit suggestions; no auto purchasing |
| **4.1** | Forecast comparison and seasonality | 365-day forecasts require seasonal/event features | Multiple backtests by segment; explicit backtest improvement over baseline, actual-vs-forecast monitoring |
| **4.2** | Evidence-grounded assistant | Language models should never invent financial figures | Approved read-only metric API, source links, denial of unauthorized business access, evaluation set |
| **5** | Operational platform | Scale only after the early modules become trustworthy | CI, RBAC, multi-location permissions, background jobs, connectors, observability, SSO as justified |

## Today's release scope — implementable without new schema

**Backend:** `backend/forecast_engine.py` (pure, testable forecasting), `backend/demand_forecasting.py` (business-scoped, read-only owner API).

**Frontend:** `forecast-studio.html`, `forecast-studio.css`, `forecast-studio.js` (dedicated futuristic analytics cockpit), `forecast-preview.css`, `forecast-preview.js` (safe business overview entry point). The installer registers the router before the existing static mount and adds a preview section to `dashboard.html` without replacing existing sales-intelligence charts.

**Quality:** unit and API tests, deterministic synthetic demo, optional PostgreSQL EXPLAIN tool, README and this roadmap. **No new database migrations** or background forecast job in v1.

## Acceptance gates for the team to mark completed

1. On `main` or an approved feature branch, `python -m pytest tests/test_forecast_engine.py tests/test_forecast_api.py -q` passes, then `python -m pytest -q` passes.
2. `node --check forecast-studio.js` and `node --check forecast-preview.js` pass. API paths are registered in `app.openapi()["paths"]`.
3. A signed-in **owner** can open `forecast-studio.html`, switch all four horizons, select a category/product, and see a truthful insufficient-history state when data is short.
4. A non-owner cannot obtain forecasts or reorder scenarios from another business (API tests and a manual sign-in check).
5. A product reorder what-if scenario is **read-only**, requires the owner to supply a real stock value, and does not claim ingredient purchases.
6. Save one sanitized screenshot of the dashboard and one of the scenario, plus exact test result output. Do **not** commit secrets, `.env`, database dumps or real customer CSV data.
7. If historical data is insufficient, **do not** mark month/quarter/year forecast accuracy as validated. Use the synthetic demo only to verify UI behavior.

## Next engineering milestones (issues after the forecast PR)

- `feat(data-quality): record expected daily source coverage and upload gaps`
- `feat(catalog): map POS product IDs to inventory and recipe units`
- `feat(inventory): add movement ledger and verified physical on-hand balances`
- `feat(forecasting): persist training cutoff, source watermark and actual-vs-predicted errors`
- `feat(forecasting): evaluate weekly/monthly baseline versus holiday/calendar models`
- `feat(alerts): add owner alert inbox with acknowledgments and deduplication`
- `feat(purchasing): generate draft product/ingredient orders for operator approval`
- `test(security): expand endpoint tenant-isolation and role-negative tests`

## Engineering philosophy

Use **signed net revenue**, not gross profit. A `sales_line_items.quantity` forecast estimates **net sold-product units**, not purchases of ingredients. Negative refunds/returns affect historical aggregates. Converting a menu item such as Pad Thai into rice noodles, tofu and packaging requires an approved recipe and unit mapping, and converting that demand into purchase orders requires verified stock, spoilage, lead time and vendor constraints. Keep these boundaries explicit in every API response and user message.

The original research paper remains the strategy reference; change this execution plan as actual customers, data contracts and test evidence improve.

## Release update: DemandPulse replay and model trust

Phase 1 now includes **DemandPulse**, a read-only last-7-/30-completed-day forecast replay alongside ForecastStudio. It is an initial *model-monitoring workflow*, not a persisted forecast registry. Before using forecasts for automatic procurement, add (a) a verified reporting-day coverage table, (b) persisted forecast snapshots with model/version/created-at, (c) inventory and ingredient BOM mapping, (d) supplier constraints, and (e) calibrated forecast evaluation across multiple tenants and seasons. See `docs/DEMANDPULSE_TECHNICAL.md`.
