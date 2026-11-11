"""Sprint 2 task 3.3-3.5: CSV ingestion for OmniStat.

Supports the agreed simplified OmniStat CSV and the synthetic Square-style
item-sales detail example. Each upload is business-scoped and atomic.
"""

import csv
import hashlib
import io
import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from psycopg.types.json import Jsonb

from backend.database import get_connection
from backend.siddartha_sprint2 import current_owner

router = APIRouter(tags=["Sales CSV upload"])
MAX_CSV_BYTES = 2 * 1024 * 1024
MAX_CSV_ROWS = 10_000
CENTS = Decimal("0.01")


def _csv_error(line: int, message: str) -> HTTPException:
    return HTTPException(status_code=422, detail=f"CSV line {line}: {message}")


def _parse_date(text: str, line: int) -> date:
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            pass
    raise _csv_error(line, "Date must be YYYY-MM-DD or MM/DD/YYYY")


def _parse_quantity(text: str, line: int) -> int:
    try:
        amount = Decimal(text.strip())
        if not amount.is_finite() or amount != amount.to_integral_value():
            raise ValueError
        quantity = int(amount)
        if abs(quantity) > 1_000_000:
            raise ValueError
        return quantity
    except (InvalidOperation, ValueError, OverflowError):
        raise _csv_error(line, "Quantity must be a whole number")


def _parse_money(text: str, line: int) -> Decimal:
    raw = text.strip().replace(",", "").replace("$", "")
    if raw.startswith("(") and raw.endswith(")"):
        raw = "-" + raw[1:-1]
    try:
        amount = Decimal(raw)
        if not amount.is_finite() or amount != amount.quantize(CENTS):
            raise ValueError
        if abs(amount) >= Decimal("10000000000"):
            raise ValueError
        return amount
    except (InvalidOperation, ValueError):
        raise _csv_error(line, "Revenue must be a valid currency amount in cents")


def parse_sales_csv(raw_bytes: bytes) -> tuple[str, list[dict]]:
    """Validate the entire file before any database writes.

    Returns (format_name, normalized_rows), where each normalized row has
    date, product, category, quantity, and revenue.
    """
    if not raw_bytes:
        raise HTTPException(status_code=422, detail="CSV file is empty")
    if len(raw_bytes) > MAX_CSV_BYTES:
        raise HTTPException(status_code=413, detail="CSV file exceeds the 2 MB limit")
    try:
        text = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=422, detail="CSV must be UTF-8 encoded")
    if "\x00" in text:
        raise HTTPException(status_code=422, detail="CSV contains invalid binary data")

    try:
        reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
        if not reader.fieldnames:
            raise HTTPException(status_code=422, detail="CSV header row is missing")
        if len(set(name.strip().casefold() for name in reader.fieldnames)) != len(reader.fieldnames):
            raise HTTPException(status_code=422, detail="CSV has duplicate column names")
        headers = {name.strip().casefold(): name for name in reader.fieldnames}
        simple = {"date", "product", "category", "quantity", "revenue"}
        square = {"date", "item", "category", "qty", "net sales"}
        if simple <= headers.keys():
            format_name = "omnistat"
            mapping = {field: headers[field] for field in simple}
        elif square <= headers.keys():
            format_name = "square_item_sales_detail"
            mapping = {
                "date": headers["date"], "product": headers["item"],
                "category": headers["category"], "quantity": headers["qty"],
                "revenue": headers["net sales"],
            }
        else:
            raise HTTPException(
                status_code=422,
                detail=("Unsupported CSV columns. Use date,product,category,quantity,revenue "
                        "or Square-style Date,Item,Category,Qty,Net Sales."),
            )

        rows = []
        for line_number, row in enumerate(reader, start=2):
            if len(rows) >= MAX_CSV_ROWS:
                raise HTTPException(status_code=413, detail="CSV exceeds 10,000 sales rows")
            if None in row:
                raise _csv_error(line_number, "Too many values in row")
            if not any(str(v or "").strip() for v in row.values()):
                continue
            extracted = {name: (row.get(column) or "").strip() for name, column in mapping.items()}
            product = extracted["product"]
            category = extracted["category"]
            if not product or len(product) > 255:
                raise _csv_error(line_number, "Product is required (max 255 characters)")
            if len(category) > 255:
                raise _csv_error(line_number, "Category must be 255 characters or fewer")
            rows.append({
                "date": _parse_date(extracted["date"], line_number),
                "product": product,
                "category": category or None,
                "quantity": _parse_quantity(extracted["quantity"], line_number),
                "revenue": _parse_money(extracted["revenue"], line_number),
            })
    except csv.Error as error:
        raise HTTPException(status_code=422, detail=f"Malformed CSV: {error}")
    if not rows:
        raise HTTPException(status_code=422, detail="CSV contains no sales rows")
    return format_name, rows


@router.post("/api/uploads", status_code=status.HTTP_201_CREATED)
async def upload_sales_csv(
    file: UploadFile = File(...), owner: dict = Depends(current_owner)
):
    """Upload a validated CSV, save line items, and refresh affected days.

    Owner access only. Transactions keep upload status, line items, and
    dashboard aggregates in sync. Re-uploading identical bytes is rejected.
    """
    filename = (file.filename or "").split("/")[-1].split("\\")[-1]
    if not filename.lower().endswith(".csv") or len(filename) > 255:
        raise HTTPException(status_code=415, detail="Choose a CSV file with a .csv extension")
    try:
        raw_bytes = await file.read(MAX_CSV_BYTES + 1)
    finally:
        await file.close()
    format_name, rows = parse_sales_csv(raw_bytes)
    fingerprint = hashlib.sha256(raw_bytes).hexdigest()
    business_id = owner["business_id"]
    raw_record = {
        "sha256": fingerprint,
        "format": format_name,
        "rows": [
            {"date": r["date"].isoformat(), "product": r["product"],
             "category": r["category"], "quantity": r["quantity"],
             "revenue": str(r["revenue"])}
            for r in rows
        ],
    }

    # Different CSV layouts can contain the exact same sales rows. Prevent
    # importing the same logical data twice (including the two sample files).
    normalized_hash = hashlib.sha256(json.dumps(
        sorted(raw_record["rows"], key=lambda r: json.dumps(r, sort_keys=True)),
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    raw_record["data_hash"] = normalized_hash

    with get_connection() as conn:
        with conn.cursor() as cur:
            # Serialize uploads for one business to prevent two simultaneous
            # requests from double-counting an identical file.
            cur.execute("SELECT id FROM businesses WHERE id = %s FOR UPDATE", (business_id,))
            if cur.fetchone() is None:
                raise HTTPException(status_code=404, detail="Business not found")
            cur.execute(
                """SELECT id FROM raw_csv_uploads
                   WHERE business_id = %s AND status = 'processed'
                     AND (raw_data->>'sha256' = %s OR raw_data->>'data_hash' = %s)
                   LIMIT 1""",
                (business_id, fingerprint, normalized_hash),
            )
            if cur.fetchone() is not None:
                raise HTTPException(status_code=409, detail="These sales records were already uploaded")

            cur.execute(
                """INSERT INTO raw_csv_uploads
                   (business_id, original_filename, raw_data, status, row_count)
                   VALUES (%s, %s, %s, 'pending', %s)
                   RETURNING id""",
                (business_id, filename, Jsonb(raw_record), len(rows)),
            )
            upload_id = cur.fetchone()[0]
            cur.executemany(
                """INSERT INTO sales_line_items
                   (business_id, upload_id, business_date, product_name,
                    category, quantity, revenue)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                [(business_id, upload_id, r["date"], r["product"],
                  r["category"], r["quantity"], r["revenue"]) for r in rows],
            )
            # Recompute totals from all imported line items for each changed
            # date, so several different files on the same day add correctly.
            for sales_day in sorted({r["date"] for r in rows}):
                cur.execute(
                    """INSERT INTO daily_sales_aggregates
                       (business_id, business_date, total_revenue, total_profit, items_sold_count)
                       SELECT %s, %s, COALESCE(SUM(revenue), 0), 0,
                              COALESCE(SUM(quantity), 0)
                       FROM sales_line_items
                       WHERE business_id = %s AND business_date = %s
                       ON CONFLICT (business_id, business_date) DO UPDATE
                       SET total_revenue = EXCLUDED.total_revenue,
                           items_sold_count = EXCLUDED.items_sold_count""",
                    (business_id, sales_day, business_id, sales_day),
                )
            cur.execute(
                """UPDATE raw_csv_uploads
                   SET status = 'processed', processed_at = CURRENT_TIMESTAMP,
                       updated_at = CURRENT_TIMESTAMP
                   WHERE id = %s AND business_id = %s""",
                (upload_id, business_id),
            )
    return {
        "status": "processed", "upload_id": str(upload_id),
        "row_count": len(rows), "format": format_name,
        "days_updated": len({r["date"] for r in rows}),
    }
