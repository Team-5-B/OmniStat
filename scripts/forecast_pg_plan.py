"""Read-only EXPLAIN on the existing tenant-constrained forecast workload.

Usage: DB_NAME=omnistat python -m scripts.forecast_pg_plan --business-id UUID
No index, migration, or any data is modified.
"""
from argparse import ArgumentParser
from datetime import date, timedelta
from json import dumps
from pathlib import Path
from uuid import UUID

from backend.database import get_connection
from backend.demand_forecasting import FORECAST_SOURCE_SQL


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--business-id", type=UUID, required=True)
    parser.add_argument("--output", default="docs/FORECAST_STUDIO_POSTGRES_PLAN.md")
    args = parser.parse_args()
    today = date.today()
    sql = "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + FORECAST_SOURCE_SQL
    # Unlike the public API, this is a local developer profiling tool.
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SELECT COUNT(*) FROM sales_line_items WHERE business_id = %s", (args.business_id,))
            count = cur.fetchone()[0]
            plans=[]
            for _ in range(5):
                cur.execute(sql,(args.business_id,today-timedelta(days=539),today))
                value=cur.fetchone()[0]
                if isinstance(value, str):
                    import json
                    value=json.loads(value)
                plans.append(value[0])
    times=sorted(p["Execution Time"] for p in plans)
    median=times[2]
    output=Path(args.output)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(
        "# ForecastStudio: local PostgreSQL query evidence\n\n"
        f"- Business records scanned (tenant total): {count}\n"
        "- Query: tenant + 540-day business_date window, grouped by date, product, category\n"
        "- Five EXPLAIN ANALYZE executions on the **same unchanged dataset**; no new index added\n"
        f"- Execution times (ms): {times}\n- Median execution (ms): {median}\n"
        "- This is local test evidence, not a before/after performance claim.\n\n"
        "```sql\n" + FORECAST_SOURCE_SQL.strip() + "\n```\n\n"
        "```json\n" + dumps(plans[-1], indent=2, default=str) + "\n```\n"
    )
    print("Tenant rows:", count)
    print("Five execution times (ms):", times)
    print("Median (ms):", median)
    print("Plan saved:", output)


if __name__ == "__main__":
    main()
