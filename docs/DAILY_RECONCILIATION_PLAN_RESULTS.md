# Daily Revenue Reconciliation — PostgreSQL Evidence

Database: `omnistat_recon_test`
Dataset: **20,008 records** across 2 businesses.
Reporting day: **2026-11-09**

Both aggregation queries use the same business and date.
The dataset was unchanged between measurements.
Each query was measured five times.
No new index was introduced.

## Existing date-range reconciliation

Median execution time: **0.0230 ms**
Execution times: `[0.025, 0.031, 0.023, 0.02, 0.019]`

```sql
SELECT COUNT(*),
           COALESCE(SUM(revenue),0),
           COALESCE(SUM(quantity),0)
    FROM sales_line_items
    WHERE business_id=%s
      AND business_date BETWEEN %s AND %s
```

```json
{
  "Plan": {
    "Node Type": "Aggregate",
    "Strategy": "Plain",
    "Partial Mode": "Simple",
    "Parallel Aware": false,
    "Async Capable": false,
    "Startup Cost": 527.19,
    "Total Cost": 527.2,
    "Plan Rows": 1,
    "Plan Width": 48,
    "Actual Startup Time": 0.007,
    "Actual Total Time": 0.007,
    "Actual Rows": 1,
    "Actual Loops": 1,
    "Shared Hit Blocks": 3,
    "Shared Read Blocks": 0,
    "Shared Dirtied Blocks": 0,
    "Shared Written Blocks": 0,
    "Local Hit Blocks": 0,
    "Local Read Blocks": 0,
    "Local Dirtied Blocks": 0,
    "Local Written Blocks": 0,
    "Temp Read Blocks": 0,
    "Temp Written Blocks": 0,
    "Plans": [
      {
        "Node Type": "Bitmap Heap Scan",
        "Parent Relationship": "Outer",
        "Parallel Aware": false,
        "Async Capable": false,
        "Relation Name": "sales_line_items",
        "Alias": "sales_line_items",
        "Startup Cost": 84.09,
        "Total Cost": 489.66,
        "Plan Rows": 5004,
        "Plan Width": 9,
        "Actual Startup Time": 0.003,
        "Actual Total Time": 0.004,
        "Actual Rows": 3,
        "Actual Loops": 1,
        "Recheck Cond": "((business_id = 'a0000000-0000-0000-0000-000000000001'::uuid) AND (business_date >= '2026-11-09'::date) AND (business_date <= '2026-11-09'::date))",
        "Rows Removed by Index Recheck": 0,
        "Exact Heap Blocks": 1,
        "Lossy Heap Blocks": 0,
        "Shared Hit Blocks": 3,
        "Shared Read Blocks": 0,
        "Shared Dirtied Blocks": 0,
        "Shared Written Blocks": 0,
        "Local Hit Blocks": 0,
        "Local Read Blocks": 0,
        "Local Dirtied Blocks": 0,
        "Local Written Blocks": 0,
        "Temp Read Blocks": 0,
        "Temp Written Blocks": 0,
        "Plans": [
          {
            "Node Type": "Bitmap Index Scan",
            "Parent Relationship": "Outer",
            "Parallel Aware": false,
            "Async Capable": false,
            "Index Name": "idx_sales_line_items_business_date",
            "Startup Cost": 0.0,
            "Total Cost": 82.84,
            "Plan Rows": 5004,
            "Plan Width": 0,
            "Actual Startup Time": 0.002,
            "Actual Total Time": 0.002,
            "Actual Rows": 3,
            "Actual Loops": 1,
            "Index Cond": "((business_id = 'a0000000-0000-0000-0000-000000000001'::uuid) AND (business_date >= '2026-11-09'::date) AND (business_date <= '2026-11-09'::date))",
            "Shared Hit Blocks": 2,
            "Shared Read Blocks": 0,
            "Shared Dirtied Blocks": 0,
            "Shared Written Blocks": 0,
            "Local Hit Blocks": 0,
            "Local Read Blocks": 0,
            "Local Dirtied Blocks": 0,
            "Local Written Blocks": 0,
            "Temp Read Blocks": 0,
            "Temp Written Blocks": 0
          }
        ]
      }
    ]
  },
  "Planning": {
    "Shared Hit Blocks": 0,
    "Shared Read Blocks": 0,
    "Shared Dirtied Blocks": 0,
    "Shared Written Blocks": 0,
    "Local Hit Blocks": 0,
    "Local Read Blocks": 0,
    "Local Dirtied Blocks": 0,
    "Local Written Blocks": 0,
    "Temp Read Blocks": 0,
    "Temp Written Blocks": 0
  },
  "Planning Time": 0.041,
  "Triggers": [],
  "Execution Time": 0.019
}
```

## New daily reconciliation

Median execution time: **0.0180 ms**
Execution times: `[0.019, 0.019, 0.018, 0.018, 0.018]`

```sql
SELECT COUNT(*), COALESCE(SUM(revenue), 0),
       COALESCE(SUM(quantity), 0)
FROM sales_line_items
WHERE business_id = %s AND business_date = %s
```

```json
{
  "Plan": {
    "Node Type": "Aggregate",
    "Strategy": "Plain",
    "Partial Mode": "Simple",
    "Parallel Aware": false,
    "Async Capable": false,
    "Startup Cost": 502.17,
    "Total Cost": 502.18,
    "Plan Rows": 1,
    "Plan Width": 48,
    "Actual Startup Time": 0.006,
    "Actual Total Time": 0.007,
    "Actual Rows": 1,
    "Actual Loops": 1,
    "Shared Hit Blocks": 3,
    "Shared Read Blocks": 0,
    "Shared Dirtied Blocks": 0,
    "Shared Written Blocks": 0,
    "Local Hit Blocks": 0,
    "Local Read Blocks": 0,
    "Local Dirtied Blocks": 0,
    "Local Written Blocks": 0,
    "Temp Read Blocks": 0,
    "Temp Written Blocks": 0,
    "Plans": [
      {
        "Node Type": "Bitmap Heap Scan",
        "Parent Relationship": "Outer",
        "Parallel Aware": false,
        "Async Capable": false,
        "Relation Name": "sales_line_items",
        "Alias": "sales_line_items",
        "Startup Cost": 71.58,
        "Total Cost": 464.64,
        "Plan Rows": 5004,
        "Plan Width": 9,
        "Actual Startup Time": 0.003,
        "Actual Total Time": 0.003,
        "Actual Rows": 3,
        "Actual Loops": 1,
        "Recheck Cond": "((business_id = 'a0000000-0000-0000-0000-000000000001'::uuid) AND (business_date = '2026-11-09'::date))",
        "Rows Removed by Index Recheck": 0,
        "Exact Heap Blocks": 1,
        "Lossy Heap Blocks": 0,
        "Shared Hit Blocks": 3,
        "Shared Read Blocks": 0,
        "Shared Dirtied Blocks": 0,
        "Shared Written Blocks": 0,
        "Local Hit Blocks": 0,
        "Local Read Blocks": 0,
        "Local Dirtied Blocks": 0,
        "Local Written Blocks": 0,
        "Temp Read Blocks": 0,
        "Temp Written Blocks": 0,
        "Plans": [
          {
            "Node Type": "Bitmap Index Scan",
            "Parent Relationship": "Outer",
            "Parallel Aware": false,
            "Async Capable": false,
            "Index Name": "idx_sales_line_items_business_date",
            "Startup Cost": 0.0,
            "Total Cost": 70.33,
            "Plan Rows": 5004,
            "Plan Width": 0,
            "Actual Startup Time": 0.002,
            "Actual Total Time": 0.002,
            "Actual Rows": 3,
            "Actual Loops": 1,
            "Index Cond": "((business_id = 'a0000000-0000-0000-0000-000000000001'::uuid) AND (business_date = '2026-11-09'::date))",
            "Shared Hit Blocks": 2,
            "Shared Read Blocks": 0,
            "Shared Dirtied Blocks": 0,
            "Shared Written Blocks": 0,
            "Local Hit Blocks": 0,
            "Local Read Blocks": 0,
            "Local Dirtied Blocks": 0,
            "Local Written Blocks": 0,
            "Temp Read Blocks": 0,
            "Temp Written Blocks": 0
          }
        ]
      }
    ]
  },
  "Planning": {
    "Shared Hit Blocks": 0,
    "Shared Read Blocks": 0,
    "Shared Dirtied Blocks": 0,
    "Shared Written Blocks": 0,
    "Local Hit Blocks": 0,
    "Local Read Blocks": 0,
    "Local Dirtied Blocks": 0,
    "Local Written Blocks": 0,
    "Temp Read Blocks": 0,
    "Temp Written Blocks": 0
  },
  "Planning Time": 0.034,
  "Triggers": [],
  "Execution Time": 0.018
}
```

## Paginated source evidence

Median execution time: **5.4870 ms**
Execution times: `[14.645, 7.228, 5.487, 4.644, 4.228]`

```sql
SELECT s.id, s.business_date, s.product_name, s.category,
       s.quantity, s.revenue, s.upload_id,
       u.original_filename
FROM sales_line_items s
LEFT JOIN raw_csv_uploads u
  ON u.id = s.upload_id AND u.business_id = s.business_id
WHERE s.business_id = %s AND s.business_date = %s
ORDER BY s.id
LIMIT %s OFFSET %s
```

```json
{
  "Plan": {
    "Node Type": "Limit",
    "Parallel Aware": false,
    "Async Capable": false,
    "Startup Cost": 0.29,
    "Total Cost": 11.21,
    "Plan Rows": 25,
    "Plan Width": 585,
    "Actual Startup Time": 0.468,
    "Actual Total Time": 4.22,
    "Actual Rows": 3,
    "Actual Loops": 1,
    "Shared Hit Blocks": 20059,
    "Shared Read Blocks": 0,
    "Shared Dirtied Blocks": 0,
    "Shared Written Blocks": 0,
    "Local Hit Blocks": 0,
    "Local Read Blocks": 0,
    "Local Dirtied Blocks": 0,
    "Local Written Blocks": 0,
    "Temp Read Blocks": 0,
    "Temp Written Blocks": 0,
    "Plans": [
      {
        "Node Type": "Nested Loop",
        "Parent Relationship": "Outer",
        "Parallel Aware": false,
        "Async Capable": false,
        "Join Type": "Left",
        "Startup Cost": 0.29,
        "Total Cost": 2187.24,
        "Plan Rows": 5004,
        "Plan Width": 585,
        "Actual Startup Time": 0.468,
        "Actual Total Time": 4.219,
        "Actual Rows": 3,
        "Actual Loops": 1,
        "Inner Unique": true,
        "Join Filter": "((u.business_id = s.business_id) AND (u.id = s.upload_id))",
        "Rows Removed by Join Filter": 0,
        "Shared Hit Blocks": 20059,
        "Shared Read Blocks": 0,
        "Shared Dirtied Blocks": 0,
        "Shared Written Blocks": 0,
        "Local Hit Blocks": 0,
        "Local Read Blocks": 0,
        "Local Dirtied Blocks": 0,
        "Local Written Blocks": 0,
        "Temp Read Blocks": 0,
        "Temp Written Blocks": 0,
        "Plans": [
          {
            "Node Type": "Index Scan",
            "Parent Relationship": "Outer",
            "Parallel Aware": false,
            "Async Capable": false,
            "Scan Direction": "Forward",
            "Index Name": "sales_line_items_pkey",
            "Relation Name": "sales_line_items",
            "Alias": "s",
            "Startup Cost": 0.29,
            "Total Cost": 2088.42,
            "Plan Rows": 5004,
            "Plan Width": 85,
            "Actual Startup Time": 0.462,
            "Actual Total Time": 4.211,
            "Actual Rows": 3,
            "Actual Loops": 1,
            "Filter": "((business_id = 'a0000000-0000-0000-0000-000000000001'::uuid) AND (business_date = '2026-11-09'::date))",
            "Rows Removed by Filter": 20005,
            "Shared Hit Blocks": 20058,
            "Shared Read Blocks": 0,
            "Shared Dirtied Blocks": 0,
            "Shared Written Blocks": 0,
            "Local Hit Blocks": 0,
            "Local Read Blocks": 0,
            "Local Dirtied Blocks": 0,
            "Local Written Blocks": 0,
            "Temp Read Blocks": 0,
            "Temp Written Blocks": 0
          },
          {
            "Node Type": "Materialize",
            "Parent Relationship": "Inner",
            "Parallel Aware": false,
            "Async Capable": false,
            "Startup Cost": 0.0,
            "Total Cost": 11.26,
            "Plan Rows": 1,
            "Plan Width": 548,
            "Actual Startup Time": 0.001,
            "Actual Total Time": 0.001,
            "Actual Rows": 1,
            "Actual Loops": 3,
            "Shared Hit Blocks": 1,
            "Shared Read Blocks": 0,
            "Shared Dirtied Blocks": 0,
            "Shared Written Blocks": 0,
            "Local Hit Blocks": 0,
            "Local Read Blocks": 0,
            "Local Dirtied Blocks": 0,
            "Local Written Blocks": 0,
            "Temp Read Blocks": 0,
            "Temp Written Blocks": 0,
            "Plans": [
              {
                "Node Type": "Seq Scan",
                "Parent Relationship": "Outer",
                "Parallel Aware": false,
                "Async Capable": false,
                "Relation Name": "raw_csv_uploads",
                "Alias": "u",
                "Startup Cost": 0.0,
                "Total Cost": 11.25,
                "Plan Rows": 1,
                "Plan Width": 548,
                "Actual Startup Time": 0.003,
                "Actual Total Time": 0.003,
                "Actual Rows": 1,
                "Actual Loops": 1,
                "Filter": "(business_id = 'a0000000-0000-0000-0000-000000000001'::uuid)",
                "Rows Removed by Filter": 0,
                "Shared Hit Blocks": 1,
                "Shared Read Blocks": 0,
                "Shared Dirtied Blocks": 0,
                "Shared Written Blocks": 0,
                "Local Hit Blocks": 0,
                "Local Read Blocks": 0,
                "Local Dirtied Blocks": 0,
                "Local Written Blocks": 0,
                "Temp Read Blocks": 0,
                "Temp Written Blocks": 0
              }
            ]
          }
        ]
      }
    ]
  },
  "Planning": {
    "Shared Hit Blocks": 0,
    "Shared Read Blocks": 0,
    "Shared Dirtied Blocks": 0,
    "Shared Written Blocks": 0,
    "Local Hit Blocks": 0,
    "Local Read Blocks": 0,
    "Local Dirtied Blocks": 0,
    "Local Written Blocks": 0,
    "Temp Read Blocks": 0,
    "Temp Written Blocks": 0
  },
  "Planning Time": 0.057,
  "Triggers": [],
  "Execution Time": 4.228
}
```

These measurements describe a local fixture database, not production latency.
