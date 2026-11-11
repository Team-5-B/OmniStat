"""Secure category and product drill-down analytics."""

from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.database import get_connection
from backend.siddartha_sprint2 import current_member
from backend.sales_intelligence import analyze_sales


category_router = APIRouter(tags=["Advanced Category Analytics"])
product_router = APIRouter(tags=["Advanced Product Analytics"])


def build_report(rows, category, product=None, days=30, today=None):
    if days not in (7, 30, 90):
        raise ValueError("Unsupported reporting period")

    category = category.strip()

    if not category or (product is not None and not product.strip()):
        raise ValueError("Category and product names are required")

    today = today or date.today()

    def matches(actual, expected):
        return (
            str(actual or "Uncategorized").strip().casefold()
            == expected.strip().casefold()
        )

    category_rows = [
        row for row in rows
        if matches(row[2], category)
    ]

    selected_rows = (
        [
            row for row in category_rows
            if matches(row[1], product)
        ]
        if product is not None
        else category_rows
    )

    data = analyze_sales(
        selected_rows,
        days=days,
        today=today,
    )

    category_data = analyze_sales(
        category_rows,
        days=days,
        today=today,
    )

    business_data = analyze_sales(
        rows,
        days=days,
        today=today,
    )

    revenue = Decimal(str(data["kpis"]["net_sales"]))

    category_revenue = Decimal(
        str(category_data["kpis"]["net_sales"])
    )

    positive_business_revenue = sum(
        (
            Decimal(str(item["revenue"]))
            for item in business_data["category_mix"]
            if item["revenue"] > 0
        ),
        Decimal("0"),
    )

    denominator = (
        category_revenue
        if product is not None
        else positive_business_revenue
    )

    share = (
        round(float(revenue * 100 / denominator), 1)
        if revenue > 0 and denominator > 0
        else None
    )

    data["category"] = (
        str(category_rows[0][2]).strip()
        if category_rows
        else category
    )

    if product is not None:
        data["product"] = (
            str(selected_rows[0][1]).strip()
            if selected_rows
            else product.strip()
        )

    data["kpis"]["category_share_pct"] = share

    units = data["kpis"]["units_sold"]

    data["kpis"]["net_revenue_per_unit"] = (
        round(float(revenue / units), 2)
        if units > 0
        else None
    )

    data["notes"]["drilldown"] = (
        "Net sales include refunds. "
        "Profit margins and order counts are not inferred."
    )

    return data


def fetch_business_sales(member, days):
    today = date.today()
    start = today - timedelta(days=days * 2 - 1)

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
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
                GROUP BY
                    business_date,
                    product_name,
                    category
                ORDER BY
                    business_date,
                    product_name,
                    category
                """,
                (member["business_id"], start, today),
            )

            return cursor.fetchall()


@category_router.get("/api/dashboard/category-analytics")
def category_analytics(
    category: str = Query(..., min_length=1, max_length=120),
    days: int = Query(30),
    member: dict = Depends(current_member),
):
    if days not in (7, 30, 90) or not category.strip():
        raise HTTPException(
            status_code=422,
            detail="Choose a category and 7, 30, or 90 days",
        )

    rows = fetch_business_sales(member, days)

    return build_report(
        rows,
        category=category,
        days=days,
    )


@product_router.get("/api/dashboard/product-analytics")
def product_analytics(
    category: str = Query(..., min_length=1, max_length=120),
    product: str = Query(..., min_length=1, max_length=255),
    days: int = Query(30),
    member: dict = Depends(current_member),
):
    if (
        days not in (7, 30, 90)
        or not category.strip()
        or not product.strip()
    ):
        raise HTTPException(
            status_code=422,
            detail="Choose category, product, and reporting period",
        )

    rows = fetch_business_sales(member, days)

    return build_report(
        rows,
        category=category,
        product=product,
        days=days,
    )
