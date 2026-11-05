"""OmniStat Sales Intelligence: business-scoped product mix and trends.

Designed as an additive Sprint 2 enhancement. Data comes exclusively from
sales_line_items populated by the CSV upload pipeline. No fake revenue, order
count, inventory valuation or profit numbers are generated here.
"""
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Query

from backend.database import get_connection
from backend.siddartha_sprint2 import current_member

router = APIRouter(tags=["Sales Intelligence"])
ZERO = Decimal("0")


def money(value):
    """Convert Decimal to JSON-compatible currency numbers at the API boundary."""
    return round(float(value), 2)


def growth_pct(current, previous):
    """Undefined when the comparison period has no positive baseline."""
    if previous <= ZERO:
        return None
    return round(float((current - previous) * 100 / previous), 1)


def analyze_sales(rows, days=30, today=None, last_upload=None):
    """Pure aggregation for analysis and unit tests.

    Rows contain date, product name, category, signed units and net revenue.
    Signed values honor refunds and returns. The prior window has the same
    number of calendar days as the selected current window.
    """
    if days not in (7, 30, 90):
        raise ValueError("Unsupported reporting window")
    today = today or date.today()
    start = today - timedelta(days=days - 1)
    prior_start = start - timedelta(days=days)
    prior_end = start - timedelta(days=1)

    day_revenue = {start + timedelta(days=i): ZERO for i in range(days)}
    categories = defaultdict(lambda: {"revenue": ZERO, "units": 0})
    products = defaultdict(lambda: {"revenue": ZERO, "units": 0})
    previous_product = defaultdict(lambda: {"revenue": ZERO, "units": 0})
    previous_category = defaultdict(lambda: {"revenue": ZERO, "units": 0})
    total = ZERO
    total_units = 0
    previous_total = ZERO
    current_records = 0
    prior_records = 0

    for sale_day, product, category, units, revenue in rows:
        if hasattr(sale_day, "date"):
            sale_day = sale_day.date()
        amount = Decimal(str(revenue))
        quantity = int(units)
        product = str(product or "Unknown product").strip()
        category = str(category or "Uncategorized").strip() or "Uncategorized"
        key = (product, category)
        if start <= sale_day <= today:
            current_records += 1
            total += amount
            total_units += quantity
            day_revenue[sale_day] += amount
            categories[category]["revenue"] += amount
            categories[category]["units"] += quantity
            products[key]["revenue"] += amount
            products[key]["units"] += quantity
        elif prior_start <= sale_day <= prior_end:
            prior_records += 1
            previous_total += amount
            previous_product[key]["revenue"] += amount
            previous_product[key]["units"] += quantity
            previous_category[category]["revenue"] += amount
            previous_category[category]["units"] += quantity

    positive_category_total = sum(
        (entry["revenue"] for entry in categories.values() if entry["revenue"] > ZERO), ZERO
    )
    category_list = [
        {
            "category": name,
            "revenue": money(v["revenue"]),
            "units_sold": v["units"],
            "previous_revenue": money(previous_category[name]["revenue"]),
            "growth_pct": growth_pct(v["revenue"], previous_category[name]["revenue"]),
            # Negative/refunded categories are shown in the legend but never
            # drawn as negative pie slices.
            "mix_pct": round(float(v["revenue"] * 100 / positive_category_total), 1)
            if v["revenue"] > ZERO and positive_category_total > ZERO else 0.0,
        }
        for name in (categories.keys() | previous_category.keys())
        for v in (categories[name],)
    ]
    category_list.sort(key=lambda x: (-x["revenue"], x["category"].lower()))

    product_list = [
        {
            "product": key[0],
            "category": key[1],
            "units_sold": v["units"],
            "revenue": money(v["revenue"]),
            "revenue_share_pct": round(float(v["revenue"] * 100 / total), 1)
            if total > ZERO else None,
            "growth_pct": growth_pct(v["revenue"], previous_product[key]["revenue"]),
        }
        for key, v in products.items()
    ]
    top_products = sorted(product_list, key=lambda x: (-x["revenue"], -x["units_sold"], x["product"].lower()))
    slow_movers = sorted(
        [p for p in product_list if p["units_sold"] > 0],
        key=lambda x: (x["units_sold"], x["revenue"], x["product"].lower()),
    )[:5]
    best_by_units = sorted(product_list, key=lambda x: (-x["units_sold"], -x["revenue"], x["product"].lower()))
    percentage_growth = growth_pct(total, previous_total)
    months = defaultdict(lambda: ZERO)
    weekdays = [{"weekday": name, "revenue": ZERO, "days": 0} for name in
                ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")]
    for sale_day, day_total in day_revenue.items():
        months[sale_day.strftime("%Y-%m")] += day_total
        group = weekdays[sale_day.weekday()]
        group["revenue"] += day_total
        group["days"] += 1
    monthly_trend = [{"month": name, "revenue": money(value)} for name,value in sorted(months.items())]
    weekday_performance = [
        {"weekday": entry["weekday"], "total_revenue": money(entry["revenue"]),
         "average_daily_revenue": money(entry["revenue"] / entry["days"]) if entry["days"] else 0.0,
         "days_observed": entry["days"]}
        for entry in weekdays
    ]

    insights = []
    positive_categories = [c for c in category_list if c["revenue"] > 0]
    if current_records:
        if positive_categories:
            c = positive_categories[0]
            insights.append({"kind": "category", "title": "Leading category",
                             "detail": f'{c["category"]} contributed {c["mix_pct"]:.1f}% of positive category revenue (${c["revenue"]:,.2f}).'})
        if best_by_units and best_by_units[0]["units_sold"] > 0:
            p = best_by_units[0]
            insights.append({"kind": "product", "title": "Highest unit volume",
                             "detail": f'{p["product"]} sold {p["units_sold"]:,} net units (${p["revenue"]:,.2f} net sales).'})
        if percentage_growth is not None:
            direction = "up" if percentage_growth >= 0 else "down"
            insights.append({"kind": "trend", "title": "Period comparison",
                             "detail": f'Net revenue is {direction} {abs(percentage_growth):.1f}% versus the prior {days} days.'})
        else:
            insights.append({"kind": "trend", "title": "No comparable baseline",
                             "detail": f'The prior {days}-day period has no positive revenue; a growth percentage is not available.'})
        if any(c["revenue"] < 0 for c in category_list):
            insights.append({"kind": "returns", "title": "Refund impact",
                             "detail": "One or more categories have negative net sales; review refunds before interpreting category shares."})
    else:
        insights.append({"kind": "empty", "title": "No sales in this period",
                         "detail": "Upload a POS sales CSV, or choose a longer reporting period."})

    return {
        "period": {"days": days, "start_date": start.isoformat(), "end_date": today.isoformat(),
                   "previous_start_date": prior_start.isoformat(),
                   "previous_end_date": prior_end.isoformat()},
        "has_data": current_records > 0,
        "kpis": {"net_sales": money(total), "units_sold": total_units,
                 "unique_products": sum(1 for p in product_list if p["units_sold"] > 0),
                 "growth_pct": percentage_growth, "previous_net_sales": money(previous_total)},
        "revenue_trend": [
            {"date": d.isoformat(), "revenue": money(day_revenue[d])}
            for d in sorted(day_revenue)
        ],
        "category_mix": category_list,
        "monthly_revenue": monthly_trend,
        "weekday_performance": weekday_performance,
        "product_performance": top_products,
        "slow_movers": slow_movers,
        "insights": insights,
        "last_upload_at": last_upload.isoformat() if last_upload else None,
        "notes": {
            "category_mix": "Shares use positive category net sales; negative categories appear in the table but not the donut.",
            "revenue": "Net sales are sums of signed CSV revenue, including refunds when supplied.",
            "units": "Units sold are net quantities, including returns when supplied.",
            "not_available": "Order count, average order value, profit, margins and inventory alerts require additional source data.",
        },
    }


@router.get("/api/dashboard/analytics")
def dashboard_analytics(
    days: int = Query(30, description="Reporting window: 7, 30, or 90 days"),
    member: dict = Depends(current_member),
):
    if days not in (7, 30, 90):
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="Choose 7, 30, or 90 days")
    today = date.today()
    first_day = today - timedelta(days=2 * days - 1)
    with get_connection() as conn:
        with conn.cursor() as cur:
            # business_id is taken from a verified membership, NEVER the query string.
            # Aggregate in PostgreSQL first so we don't transfer every CSV row.
            cur.execute(
                """SELECT business_date, product_name, category,
                          COALESCE(SUM(quantity), 0), COALESCE(SUM(revenue), 0)
                   FROM sales_line_items
                   WHERE business_id = %s AND business_date BETWEEN %s AND %s
                   GROUP BY business_date, product_name, category
                   ORDER BY business_date, product_name, category""",
                (member["business_id"], first_day, today),
            )
            rows = cur.fetchall()
            cur.execute(
                """SELECT MAX(processed_at) FROM raw_csv_uploads
                   WHERE business_id = %s AND status = 'processed'""",
                (member["business_id"],),
            )
            upload_row = cur.fetchone()
    return analyze_sales(rows, days=days, today=today,
                         last_upload=upload_row[0] if upload_row else None)
