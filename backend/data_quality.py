
"""Owner-only, read-only sales data integrity verification for OmniStat.

Compares uploaded sales_line_items with daily_sales_aggregates
to identify discrepancies in dashboard revenue and unit totals.
"""

from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.database import get_connection
from backend.siddartha_sprint2 import current_owner


router = APIRouter(tags=["Sales Data Integrity"])


def _amount(value):
    """Convert PostgreSQL NUMERIC values into JSON-compatible numbers."""
    return float(value or Decimal("0"))


@router.get("/api/business/data-quality")
def sales_data_quality(
    days: int = Query(
        30,
        description="Audit the past 7, 30, or 90 calendar days",
    ),
    owner: dict = Depends(current_owner),
):
    """Verify sales totals for the authenticated business owner.

    This endpoint is read-only. It does not modify, delete,
    or automatically repair database records.
    """

    if days not in (7, 30, 90):
        raise HTTPException(
            status_code=422,
            detail="Choose 7, 30, or 90 days",
        )

    today = date.today()
    start = today - timedelta(days=days - 1)

    # Taken from verified membership, never from user input.
    business_id = owner["business_id"]

    with get_connection() as connection:
        with connection.cursor() as cursor:

            # 1. Check CSV upload activity.
            cursor.execute(
                """
                SELECT
                    COUNT(*),
                    COUNT(*) FILTER (
                        WHERE status = 'processed'
                    ),
                    COUNT(*) FILTER (
                        WHERE status = 'pending'
                    ),
                    COUNT(*) FILTER (
                        WHERE status = 'failed'
                    ),
                    MAX(processed_at) FILTER (
                        WHERE status = 'processed'
                    )
                FROM raw_csv_uploads
                WHERE business_id = %s
                """,
                (business_id,),
            )

            (
                total_uploads,
                processed,
                pending,
                failed,
                last_processed_at,
            ) = cursor.fetchone()

            # 2. Calculate sales directly from uploaded line items.
            cursor.execute(
                """
                SELECT
                    COUNT(*),
                    COALESCE(SUM(quantity), 0),
                    COALESCE(SUM(revenue), 0)
                FROM sales_line_items
                WHERE business_id = %s
                  AND business_date BETWEEN %s AND %s
                """,
                (business_id, start, today),
            )

            line_count, unit_count, net_sales = cursor.fetchone()

            # 3. Compare sales records against dashboard summaries.
            cursor.execute(
                """
                WITH line_days AS (
                    SELECT
                        business_date,
                        COUNT(*) AS row_count,
                        COALESCE(SUM(quantity), 0) AS units,
                        COALESCE(SUM(revenue), 0) AS net_sales
                    FROM sales_line_items
                    WHERE business_id = %s
                      AND business_date BETWEEN %s AND %s
                    GROUP BY business_date
                ),
                summary_days AS (
                    SELECT
                        business_date,
                        total_revenue,
                        items_sold_count
                    FROM daily_sales_aggregates
                    WHERE business_id = %s
                      AND business_date BETWEEN %s AND %s
                )
                SELECT
                    COALESCE(
                        l.business_date,
                        a.business_date
                    ) AS day,
                    l.row_count,
                    l.units,
                    l.net_sales,
                    a.items_sold_count,
                    a.total_revenue,
                    (l.business_date IS NOT NULL) AS has_line_items,
                    (a.business_date IS NOT NULL) AS has_summary
                FROM line_days AS l
                FULL OUTER JOIN summary_days AS a
                    ON l.business_date = a.business_date
                WHERE l.business_date IS NULL
                   OR a.business_date IS NULL
                   OR l.units IS DISTINCT FROM a.items_sold_count
                   OR l.net_sales IS DISTINCT FROM a.total_revenue
                ORDER BY day
                """,
                (
                    business_id,
                    start,
                    today,
                    business_id,
                    start,
                    today,
                ),
            )

            mismatches = cursor.fetchall()

    # 4. Convert inconsistencies into readable API results.
    issues = []

    for (
        sales_day,
        row_count,
        expected_units,
        expected_revenue,
        summary_units,
        summary_revenue,
        has_lines,
        has_summary,
    ) in mismatches:

        if not has_summary:
            issue = "missing_daily_summary"
        elif not has_lines:
            issue = "summary_without_line_items"
        else:
            issue = "totals_mismatch"

        issues.append(
            {
                "date": sales_day.isoformat(),
                "issue": issue,
                "line_item_count": int(row_count or 0),
                "expected_units": int(expected_units or 0),
                "summary_units": int(summary_units or 0),
                "expected_net_sales": _amount(expected_revenue),
                "summary_net_sales": _amount(summary_revenue),
            }
        )

    # 5. Return the complete business data-quality report.
    return {
        "period": {
            "days": days,
            "start_date": start.isoformat(),
            "end_date": today.isoformat(),
        },
        "business_id": str(business_id),
        "status": "ok" if not issues else "needs_review",
        "uploads": {
            "total": total_uploads,
            "processed": processed,
            "pending": pending,
            "failed": failed,
            "last_processed_at": (
                last_processed_at.isoformat()
                if last_processed_at
                else None
            ),
        },
        "line_items": {
            "count": line_count,
            "net_units": int(unit_count),
            "net_sales": _amount(net_sales),
        },
        "mismatch_days": len(issues),
        "issues": issues,
        "note": (
            "Read-only reconciliation; "
            "no records or dashboard totals were changed."
        ),
    }

# Daily revenue discrepancy drill-down.
# Signed revenue follows the existing CSV ingestion rules.

DAY_SUMMARY_SQL = """
SELECT total_revenue, items_sold_count
FROM daily_sales_aggregates
WHERE business_id = %s AND business_date = %s
"""

DAY_TOTAL_SQL = """
SELECT COUNT(*), COALESCE(SUM(revenue), 0),
       COALESCE(SUM(quantity), 0)
FROM sales_line_items
WHERE business_id = %s AND business_date = %s
"""

DAY_RECORDS_SQL = """
SELECT s.id, s.business_date, s.product_name, s.category,
       s.quantity, s.revenue, s.upload_id,
       u.original_filename
FROM sales_line_items s
LEFT JOIN raw_csv_uploads u
  ON u.id = s.upload_id AND u.business_id = s.business_id
WHERE s.business_id = %s AND s.business_date = %s
ORDER BY s.id
LIMIT %s OFFSET %s
"""


def summarize_daily_difference(summary, totals):
    """Reconcile exact signed Decimal amounts before JSON conversion."""
    count, revenue, units = totals

    count = int(count)
    calculated = Decimal(revenue)
    calculated_units = int(units)

    exists = summary is not None

    stored = Decimal(summary[0]) if exists else None
    stored_units = int(summary[1]) if exists else None

    if not exists:
        if count:
            status = "missing_summary"
            reason = "Sales records exist without a daily summary."
        else:
            status = "no_data"
            reason = "No sales records or daily summary exist."
    elif stored == calculated and stored_units == calculated_units:
        status = "matching"
        reason = "Stored totals agree with the source records."
    elif count == 0:
        status = "mismatch"
        reason = "A daily summary exists without source records."
    elif stored == calculated:
        status = "mismatch"
        reason = "Revenue matches, but net units differ."
    else:
        status = "mismatch"
        reason = (
            "Stored and recomputed totals disagree. "
            "Review the source records to determine why."
        )

    return {
        "status": status,
        "explanation": reason,
        "stored": {
            "net_revenue": _amount(stored) if exists else None,
            "net_units": stored_units,
        },
        "recomputed": {
            "net_revenue": _amount(calculated),
            "net_units": calculated_units,
            "record_count": count,
        },
        "difference": {
            "net_revenue": (
                _amount(calculated - stored) if exists else None
            ),
            "net_units": (
                calculated_units - stored_units if exists else None
            ),
        },
    }


@router.get("/api/business/data-quality/day")
def daily_sales_discrepancy(
    day: date = Query(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    owner: dict = Depends(current_owner),
):
    """Read-only, owner-authorized daily revenue investigation."""

    business_id = owner["business_id"]
    offset = (page - 1) * page_size

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SET TRANSACTION ISOLATION LEVEL "
                "REPEATABLE READ READ ONLY"
            )

            cursor.execute(
                DAY_SUMMARY_SQL, (business_id, day)
            )
            summary = cursor.fetchone()

            cursor.execute(
                DAY_TOTAL_SQL, (business_id, day)
            )
            totals = cursor.fetchone()

            cursor.execute(
                DAY_RECORDS_SQL,
                (business_id, day, page_size, offset),
            )
            rows = cursor.fetchall()

    result = summarize_daily_difference(summary, totals)
    count = result["recomputed"]["record_count"]

    result.update({
        "day": day.isoformat(),
        "records": [
            {
                "id": str(row[0]),
                "business_date": row[1].isoformat(),
                "product": row[2],
                "category": row[3],
                "quantity": int(row[4]),
                "net_revenue": _amount(row[5]),
                "upload_id": str(row[6]) if row[6] else None,
                "upload_filename": row[7],
            }
            for row in rows
        ],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_records": count,
            "total_pages": (count + page_size - 1) // page_size,
            "has_next": offset + len(rows) < count,
            "has_previous": page > 1,
        },
    })

    return result
