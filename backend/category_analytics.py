"""Business-scoped category analytics for OmniStat.

Uses the existing sales intelligence calculations so category
dashboards remain consistent with the main dashboard.
"""

from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.database import get_connection
from backend.siddartha_sprint2 import current_member
from backend.sales_intelligence import analyze_sales

router = APIRouter(tags=["Category Analytics"])


def build_category_report(rows, category, days=30, today=None):
    """Calculate category performance from product-level sales."""
    name = category.strip()

    if not name:
        raise ValueError("Category name cannot be empty")

    if days not in (7, 30, 90):
        raise ValueError("Unsupported reporting period")

    today = today or date.today()

    # Calculate business-wide numbers for category comparisons.
    business = analyze_sales(rows, days=days, today=today)

    # Category matching is case-insensitive and ignores extra spaces.
    selected = [
        row for row in rows
        if str(row[2] or "Uncategorized").strip().casefold()
        == name.casefold()
    ]

    category_data = analyze_sales(
        selected,
        days=days,
        today=today,
    )

    # Preserve the category's display name from the actual data.
    display_name = (
        str(selected[0][2]).strip()
        if selected else name
    )

    revenue = Decimal(str(category_data["kpis"]["net_sales"]))

    # Use the same positive-revenue denominator as OmniStat's
    # existing category mix chart. Refund-only categories get 0%.
    positive_total = sum(
        (
            Decimal(str(item["revenue"]))
            for item in business["category_mix"]
            if item["revenue"] > 0
        ),
        Decimal("0"),
    )

    category_share = (
        round(float(revenue * 100 / positive_total), 1)
        if revenue > 0 and positive_total > 0
        else 0.0
    )

    products = category_data["product_performance"]
    top_products = products[:10]
    units = category_data["kpis"]["units_sold"]

    insights = []

    if category_data["has_data"]:
        if top_products and top_products[0]["revenue"] > 0:
            leader = top_products[0]

            insights.append({
                "title": "Top revenue product",
                "detail": (
                    f'{leader["product"]} generated '
                    f'${leader["revenue"]:,.2f} in net sales.'
                ),
            })

        growth = category_data["kpis"]["growth_pct"]

        if growth is not None:
            insights.append({
                "title": "Category revenue trend",
                "detail": (
                    f"Net sales changed {growth:+.1f}% "
                    f"compared with the previous {days} days."
                ),
            })
        else:
            insights.append({
                "title": "Previous period comparison",
                "detail": (
                    "No positive revenue baseline is available "
                    "for the previous period."
                ),
            })

        insights.append({
            "title": "Business revenue contribution",
            "detail": (
                f"{display_name} contributes "
                f"{category_share:.1f}% of positive category revenue."
            ),
        })

        if revenue < 0:
            insights.append({
                "title": "Net refunds",
                "detail": (
                    "This category has negative net sales. "
                    "Review returns and refunds."
                ),
            })

    else:
        insights.append({
            "title": "No current sales",
            "detail": (
                "There are no sales for this category in "
                "the selected reporting period."
            ),
        })

    return {
        "category": display_name,
        "period": category_data["period"],
        "has_data": category_data["has_data"],
        "kpis": {
            **category_data["kpis"],
            "category_share_pct": category_share,
            "revenue_per_net_unit": (
                round(float(revenue / units), 2)
                if units > 0 else None
            ),
        },
        "business_net_sales": business["kpis"]["net_sales"],
        "revenue_trend": category_data["revenue_trend"],
        "monthly_revenue": category_data["monthly_revenue"],
        "weekday_performance": category_data["weekday_performance"],
        "top_products": top_products,
        "product_performance": products,
        "slow_movers": category_data["slow_movers"],
        "insights": insights,
        "notes": {
            "revenue": "Net sales include signed refunds.",
            "units": "Units are net of returns.",
            "category_share": (
                "Share uses positive category net sales, "
                "consistent with the main dashboard."
            ),
            "revenue_per_net_unit": (
                "Net revenue divided by net units; "
                "this is not a menu price or profit margin."
            ),
        },
    }


@router.get("/api/dashboard/category-analytics")
def category_analytics(
    category: str = Query(..., min_length=1, max_length=120),
    days: int = Query(30),
    member: dict = Depends(current_member),
):
    """Return analytics for one category in the logged-in business."""

    if not category.strip():
        raise HTTPException(
            status_code=422,
            detail="Category name cannot be empty",
        )

    if days not in (7, 30, 90):
        raise HTTPException(
            status_code=422,
            detail="Choose 7, 30, or 90 days",
        )

    today = date.today()
    first_day = today - timedelta(days=2 * days - 1)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    business_date,
                    product_name,
                    category,
                    COALESCE(SUM(quantity), 0),
                    COALESCE(SUM(revenue), 0)
                FROM sales_line_items
                WHERE business_id = %s
                  AND business_date BETWEEN %s AND %s
                GROUP BY business_date, product_name, category
                ORDER BY business_date, product_name, category
                """,
                (member["business_id"], first_day, today),
            )

            rows = cur.fetchall()

    return build_category_report(
        rows,
        category=category,
        days=days,
        today=today,
    )
