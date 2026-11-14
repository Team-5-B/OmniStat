"""Deterministic forecast demonstration without PostgreSQL or sample claims."""
from datetime import date, timedelta
from decimal import Decimal
from backend.forecast_engine import forecast_rows, reorder_scenario


def main():
    today = date(2026, 11, 12)
    sales = []
    for days_ago in range(400):
        business_day = today - timedelta(days=days_ago)
        tea_units = 18 if business_day.weekday() in (5, 6) else 9
        bread_units = 8 if business_day.weekday() in (5, 6) else 4
        sales.append((business_day, "Thai Tea", "Beverages", tea_units, Decimal(tea_units * 4)))
        sales.append((business_day, "Croissant", "Bakery", bread_units, Decimal(bread_units * 6)))
    sales.append((today, "Thai Tea", "Beverages", -2, Decimal("-8.00")))
    print("SYNTHETIC DEMO ONLY — 400 days, two products, one signed refund")
    for horizon in ("week", "month", "quarter", "year"):
        forecast = forecast_rows(sales, horizon=horizon, today=today)
        print(horizon, forecast["status"], forecast["totals"], "backtest:", forecast["backtest"])
    tea = forecast_rows(sales, days=9, today=today, category="Beverages", product="Thai Tea")
    print("Scenario:", reorder_scenario(tea, on_hand=25, lead_time_days=7, safety_days=2, pack_size=12))


if __name__ == "__main__":
    main()
