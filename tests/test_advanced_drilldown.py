from datetime import date, timedelta
from decimal import Decimal

from backend.advanced_drilldown import build_report


TODAY = date.today()

ROWS = [
    (TODAY, "Thai Tea", "Beverages", 3, Decimal("15")),
    (TODAY, "Coffee", "Beverages", 2, Decimal("10")),
    (TODAY, "Croissant", "Bakery", 1, Decimal("5")),
    (
        TODAY - timedelta(days=7),
        "Thai Tea",
        "Beverages",
        1,
        Decimal("5"),
    ),
]


def test_category_analytics():
    result = build_report(
        ROWS, "Beverages", days=7, today=TODAY
    )

    assert result["kpis"]["net_sales"] == 25
    assert result["kpis"]["category_share_pct"] == 83.3
    assert len(result["product_performance"]) == 2


def test_product_analytics():
    result = build_report(
        ROWS, "Beverages", "Thai Tea", days=7, today=TODAY
    )

    assert result["kpis"]["net_sales"] == 15
    assert result["kpis"]["growth_pct"] == 200
    assert result["kpis"]["category_share_pct"] == 60


def test_empty_product():
    result = build_report(
        ROWS, "Bakery", "Unknown", days=7, today=TODAY
    )

    assert result["kpis"]["net_sales"] == 0
    assert result["has_data"] is False
