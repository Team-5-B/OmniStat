
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
