# OmniStat — Siddartha Sales Intelligence Enhancement

## Scope and ownership

Personal development branch: `siddartha/sales-intelligence`.
Target merge branch: `integration/team-work-sprint2`.

Additive, responsive Sales Intelligence dashboard modeled after the approved
OmniStat mockup, reusing the existing login, upload, team and account features.

## New feature

- **Live reporting**: `GET /api/dashboard/analytics?days=7|30|90`, authorized via
  existing business membership verification. No business identifier can be
  supplied by the browser.
- **KPIs**: net sales, net units sold, distinct products with positive net
  units, revenue growth relative to the preceding equal-length time window.
- **Revenue trend**: daily/monthly net sales with zero-sales days retained.
- **Product mix**: category-level net sales and proportional donut slices.
- **Category comparison**: category net sales, units, prior-period sales, and growth where defined.
- **Weekday performance**: average net revenue by weekday, including zero-sales dates.
- **Product rankings**: top 10 by net revenue or units, with revenue share
  and period comparisons when a meaningful prior baseline is available.
- **Review list**: least units among items *actually observed in uploaded
  data*, not a claim of inventory overstock.
- **Business insights**: deterministic summaries of category share,
  high-volume products, growth, and refund impact; no invented AI assertions.
- **Filters**: last 7, 30, or 90 calendar days.
- **Existing CSV upload and account navigation** stay in place.

## Terminology

- **Net sales:** sum of signed revenue values from uploaded CSV rows. Includes
  refunds when rows include them. Not equal to profit.
- **Net units sold:** signed quantity sum; returns may reduce units.
- **Revenue growth:** `(current - previous)/previous * 100` for equal-length
  periods; *N/A* if the previous period has zero or negative revenue.
- **Category mix:** percentage of positive category net revenue. Category
  totals that are negative are visible in API data but excluded from donut
  slices, because a negative slice has no meaningful circular proportion.
- **Products sold:** distinct product/category combinations with positive
  net units during the selected period. It is NOT current inventory size.
- **Top sellers:** ranking from records in the uploaded data, not a forecast.

## Assumptions and limitations

- `migrations/003_siddartha_sprint2.sql` must already have been applied in the
  database used for uploads; never run `initialschema.sql` as a migration.
- Existing CSV uploader writes to `sales_line_items`. This feature reads only
  that table and the processed upload timestamp.
- If the sample CSV records are outside the selected time window, the
  dashboard correctly shows an empty state; choose a longer period or upload
  a CSV with dates in the current window.
- No order or receipt IDs, cost of goods sold, current stock, or customer IDs
  are available in this CSV format. Therefore order count, AOV, margins,
  reordering and retention cannot be calculated reliably.
- Code may return *N/A* for growth and omit donut proportions when revenue
  is zero or negative. This is expected, not a parser error.
- Tests with mock DB responses verify data transformations, security scoping
  and HTTP responses; they do not independently establish that the local
  PostgreSQL database and browser integration work.

## Testing

Run from the repo root with the existing `.venv` activated:

```bash
python -m pytest tests/test_sales_intelligence.py -v
python -m pytest -v
node --check sales-intelligence.js
python scripts/record_sales_intelligence_tests.py
```

End-to-end manual acceptance:

1. Start the FastAPI app and sign in as a test owner.
2. Upload a CSV with recent dates; confirm import and reload.
3. See four KPIs, trends, category mix, product ranking and insights.
4. Compare seven-day and 30-day periods, and verify they change according
   to uploaded dates.
5. Check the same dashboard on a narrow mobile screen.
6. Sign in as a different business and verify no cross-business sales appear.
7. Confirm account settings, team management and employee invites still work.

## Deployment order

1. Create branch `siddartha/sales-intelligence` from latest integration branch.
2. Run the installer from the cloned repository's root.
3. Run unit tests and browser/database acceptance checks.
4. Commit and push the personal feature branch.
5. Merge the personal branch into `integration/team-work-sprint2` only after
   tests and conflict review, then push the integration branch.
