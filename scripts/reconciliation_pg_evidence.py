"""Reproducible PostgreSQL evidence for daily revenue reconciliation."""

import argparse
import json
import os
from datetime import date
from decimal import Decimal
from pathlib import Path
from statistics import median
from uuid import UUID, uuid5

from psycopg.types.json import Jsonb

from backend.database import get_connection
from backend.data_quality import (
    DAY_TOTAL_SQL,
    DAY_RECORDS_SQL,
    current_owner,
)
from backend.main import app


DB = "omnistat_recon_test"

TENANT = UUID("a0000000-0000-0000-0000-000000000001")
OTHER = UUID("a0000000-0000-0000-0000-000000000002")
OWNER = UUID("c0000000-0000-0000-0000-000000000001")

BATCHES = [
    UUID(f"b0000000-0000-0000-0000-{i:012d}")
    for i in range(1, 6)
]

MATCH = date(2026, 11, 9)
MISMATCH = date(2026, 11, 10)
MISSING = date(2026, 11, 11)
ARCHIVE = date(2026, 9, 15)


def connection():
    """Refuse to connect to anything except the disposable database."""

    if os.environ.get("DATABASE_URL"):
        raise SystemExit("Unset DATABASE_URL before running this tool.")

    if os.environ.get("DB_NAME") != DB:
        raise SystemExit(
            "Set DB_NAME=omnistat_recon_test."
        )

    conn = get_connection()

    with conn.cursor() as cur:
        cur.execute("SELECT current_database()")
        actual = cur.fetchone()[0]

    if actual != DB:
        conn.close()
        raise SystemExit(f"Unsafe database: {actual}")

    return conn


def line(business, batch, day, number,
         product, quantity, revenue):

    record_id = uuid5(
        UUID(int=0),
        f"{batch}-{number}",
    )

    return (
        record_id,
        business,
        batch,
        day,
        product,
        "Fixture",
        quantity,
        Decimal(revenue),
    )


def seed():
    """Create matching, mismatching and missing-summary scenarios."""

    from backend.security import hash_password

    with connection() as conn:
        with conn.cursor() as cur:

            # Delete fixture-owned IDs only, never arbitrary data.
            cur.execute(
                "DELETE FROM users WHERE id=%s",
                (OWNER,),
            )

            cur.execute(
                "DELETE FROM businesses WHERE id IN (%s,%s)",
                (TENANT, OTHER),
            )

            cur.executemany(
                "INSERT INTO businesses(id,name) VALUES(%s,%s)",
                [
                    (TENANT, "Reconciliation fixture"),
                    (OTHER, "Isolation fixture"),
                ],
            )

            cur.execute(
                """
                INSERT INTO users(id,name,email,password_hash)
                VALUES(%s,%s,%s,%s)
                """,
                (
                    OWNER,
                    "Fixture owner",
                    "recon-owner@example.invalid",
                    hash_password("OmniStat-Recon-Test-2026!"),
                ),
            )

            cur.execute(
                """
                INSERT INTO memberships(user_id,business_id,role)
                VALUES(%s,%s,'owner')
                """,
                (OWNER, TENANT),
            )

            configurations = [
                (TENANT, "matching.csv", 3),
                (TENANT, "mismatch.csv", 2),
                (TENANT, "missing.csv", 2),
                (TENANT, "history.csv", 10000),
                (OTHER, "isolation.csv", 10001),
            ]

            for batch, (business, filename, size) in zip(
                BATCHES, configurations
            ):
                cur.execute(
                    """
                    INSERT INTO raw_csv_uploads
                    (
                        id, business_id, original_filename,
                        raw_data, status, row_count, processed_at
                    )
                    VALUES(%s,%s,%s,%s,'processed',%s,NOW())
                    """,
                    (
                        batch,
                        business,
                        filename,
                        Jsonb({"fixture": True}),
                        size,
                    ),
                )

            records = [
                line(TENANT, BATCHES[0], MATCH,
                     1, "Tea", 2, "120.00"),

                line(TENANT, BATCHES[0], MATCH,
                     2, "Tea refund", -1, "-20.00"),

                line(TENANT, BATCHES[0], MATCH,
                     3, "Pastry", 1, "50.00"),

                line(TENANT, BATCHES[1], MISMATCH,
                     1, "Meal", 2, "80.00"),

                line(TENANT, BATCHES[1], MISMATCH,
                     2, "Refund", -1, "-10.00"),

                line(TENANT, BATCHES[2], MISSING,
                     1, "Coffee", 1, "25.00"),

                line(TENANT, BATCHES[2], MISSING,
                     2, "Bakery", 1, "15.00"),

                line(OTHER, BATCHES[4], MATCH,
                     0, "Other business", 1, "999.99"),
            ]

            with cur.copy(
                """
                COPY sales_line_items
                (
                    id, business_id, upload_id, business_date,
                    product_name, category, quantity, revenue
                )
                FROM STDIN
                """
            ) as copy:

                for row in records:
                    copy.write_row(row)

                for n in range(10000):

                    copy.write_row(
                        line(
                            TENANT,
                            BATCHES[3],
                            ARCHIVE,
                            n,
                            "Historical sale",
                            1,
                            "0.01",
                        )
                    )

                    copy.write_row(
                        line(
                            OTHER,
                            BATCHES[4],
                            MATCH,
                            n + 1,
                            "Other tenant sale",
                            1,
                            "0.01",
                        )
                    )

            cur.executemany(
                """
                INSERT INTO daily_sales_aggregates
                (
                    business_id, business_date,
                    total_revenue, items_sold_count
                )
                VALUES(%s,%s,%s,%s)
                """,
                [
                    (TENANT, MATCH, Decimal("150.00"), 2),
                    (TENANT, MISMATCH, Decimal("90.00"), 1),
                    (TENANT, ARCHIVE, Decimal("100.00"), 10000),
                    (OTHER, MATCH, Decimal("1099.99"), 10001),
                ],
            )

            cur.execute("ANALYZE sales_line_items")

            cur.execute(
                "SELECT COUNT(*) FROM sales_line_items"
            )

            total = cur.fetchone()[0]

    assert total == 20008, f"Unexpected row count: {total}"

    print("PASS: Seeded 20,008 sales records")
    print("Matching: $150.00 stored / $150.00 recalculated")
    print("Mismatch: $90.00 stored / $70.00 recalculated")
    print("Missing summary: $40.00 recalculated")
    print("Business isolation: two independent businesses")


def verify():
    """Check real PostgreSQL results through the FastAPI endpoint."""

    from fastapi.testclient import TestClient

    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM sales_line_items"
            )
            assert cur.fetchone()[0] == 20008, (
                "Seed the test database first."
            )

    previous = dict(app.dependency_overrides)

    try:
        app.dependency_overrides[current_owner] = (
            lambda: {"business_id": TENANT}
        )

        with TestClient(app) as client:

            cases = [
                (MATCH, "matching", 150.0, 150.0, 0.0),
                (MISMATCH, "mismatch", 90.0, 70.0, -20.0),
                (MISSING, "missing_summary", None, 40.0, None),
            ]

            for day, status, stored, calculated, difference in cases:

                response = client.get(
                    "/api/business/data-quality/day",
                    params={
                        "day": day.isoformat(),
                        "page_size": 1,
                    },
                )

                assert response.status_code == 200, response.text

                result = response.json()

                assert result["status"] == status
                assert result["stored"]["net_revenue"] == stored
                assert result["recomputed"]["net_revenue"] == calculated
                assert result["difference"]["net_revenue"] == difference

                print(f"PASS: {day} — {status}")

            first = client.get(
                "/api/business/data-quality/day",
                params={
                    "day": MATCH.isoformat(),
                    "page": 1,
                    "page_size": 2,
                },
            ).json()

            second = client.get(
                "/api/business/data-quality/day",
                params={
                    "day": MATCH.isoformat(),
                    "page": 2,
                    "page_size": 2,
                },
            ).json()

            records = first["records"] + second["records"]

            assert len(first["records"]) == 2
            assert len(second["records"]) == 1
            assert first["pagination"]["has_next"]

            assert any(
                row["net_revenue"] == -20.0
                for row in records
            )

            assert all(row["upload_id"] for row in records)

            print("PASS: Pagination, refunds and CSV provenance")

            # A client-supplied business ID cannot override authentication.
            response = client.get(
                "/api/business/data-quality/day",
                params={
                    "day": MATCH.isoformat(),
                    "business_id": str(OTHER),
                },
            )

            assert (
                response.json()["recomputed"]["net_revenue"]
                == 150.0
            )

            app.dependency_overrides[current_owner] = (
                lambda: {"business_id": OTHER}
            )

            response = client.get(
                "/api/business/data-quality/day",
                params={"day": MATCH.isoformat()},
            )

            assert (
                response.json()["recomputed"]["net_revenue"]
                == 1099.99
            )

            print("PASS: PostgreSQL business isolation")

    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


def benchmark():
    """Capture measured execution plans for the same seeded workload."""

    baseline = """
    SELECT COUNT(*),
           COALESCE(SUM(revenue),0),
           COALESCE(SUM(quantity),0)
    FROM sales_line_items
    WHERE business_id=%s
      AND business_date BETWEEN %s AND %s
    """

    workloads = [
        (
            "Existing date-range reconciliation",
            baseline,
            (TENANT, MATCH, MATCH),
        ),
        (
            "New daily reconciliation",
            DAY_TOTAL_SQL,
            (TENANT, MATCH),
        ),
        (
            "Paginated source evidence",
            DAY_RECORDS_SQL,
            (TENANT, MATCH, 25, 0),
        ),
    ]

    with connection() as conn:
        # connection() checks the database name using SELECT.
        # End that transaction before setting benchmark isolation.
        conn.rollback()

        with conn.cursor() as cur:

            cur.execute(
                "SET TRANSACTION ISOLATION LEVEL "
                "REPEATABLE READ READ ONLY"
            )

            cur.execute(
                """
                SELECT COUNT(*), COUNT(DISTINCT business_id)
                FROM sales_line_items
                """
            )

            count, businesses = cur.fetchone()

            assert count == 20008
            assert businesses == 2

            cur.execute(baseline, (TENANT, MATCH, MATCH))
            old_result = cur.fetchone()

            cur.execute(DAY_TOTAL_SQL, (TENANT, MATCH))
            new_result = cur.fetchone()

            assert old_result == new_result

            measurements = []

            for name, sql, arguments in workloads:

                plans = []

                for _ in range(5):
                    cur.execute(
                        "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) "
                        + sql,
                        arguments,
                    )

                    value = cur.fetchone()[0]

                    if isinstance(value, str):
                        value = json.loads(value)

                    plans.append(value[0])

                times = [
                    plan["Execution Time"]
                    for plan in plans
                ]

                measurements.append(
                    (name, sql, times, plans[-1])
                )

    lines = [
        "# Daily Revenue Reconciliation — PostgreSQL Evidence",
        "",
        f"Database: `{DB}`",
        f"Dataset: **{count:,} records** across {businesses} businesses.",
        f"Reporting day: **{MATCH}**",
        "",
        "Both aggregation queries use the same business and date.",
        "The dataset was unchanged between measurements.",
        "Each query was measured five times.",
        "No new index was introduced.",
        "",
    ]

    for name, sql, times, plan in measurements:

        result = median(times)

        print(f"{name}: {result:.4f} ms median")

        lines.extend([
            f"## {name}",
            "",
            f"Median execution time: **{result:.4f} ms**",
            f"Execution times: `{times}`",
            "",
            "```sql",
            sql.strip(),
            "```",
            "",
            "```json",
            json.dumps(plan, indent=2, default=str),
            "```",
            "",
        ])

    lines.append(
        "These measurements describe a local fixture database, "
        "not production latency."
    )

    output = Path(
        "docs/DAILY_RECONCILIATION_PLAN_RESULTS.md"
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n")

    print("PASS: Actual PostgreSQL plans saved to", output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "command",
        choices=("seed", "verify", "benchmark"),
    )

    args = parser.parse_args()

    {
        "seed": seed,
        "verify": verify,
        "benchmark": benchmark,
    }[args.command]()
