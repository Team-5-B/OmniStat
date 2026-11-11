"""Pure CSV parser tests — no database required."""

from fastapi import HTTPException
import pytest

from backend.uploads import parse_sales_csv


def test_omnistat_simple_format():
    fmt, rows = parse_sales_csv(b'date,product,category,quantity,revenue\n2026-11-04,Tea,Drinks,2,9.50\n')
    assert fmt == "omnistat"
    assert len(rows) == 1
    assert rows[0]["quantity"] == 2
    assert str(rows[0]["revenue"]) == "9.50"


def test_square_format_and_refunds():
    csv_data = b'Date,Item,Category,Qty,Net Sales\n11/04/2026,Tea,Drinks,-1,-4.75\n'
    fmt, rows = parse_sales_csv(csv_data)
    assert fmt == "square_item_sales_detail"
    assert rows[0]["quantity"] == -1
    assert rows[0]["revenue"] < 0


@pytest.mark.parametrize("contents", [
    b"date,product,category,quantity,revenue\n2026-11-04,Tea,Drinks,abc,4.50\n",
    b"date,product,category,quantity,revenue\n2026-11-04,Tea,Drinks,1,nan\n",
    b"date,product,category,quantity,revenue\n2026-11-04,Tea,Drinks,1,1.001\n",
    b"date,product,category,quantity,revenue\n2026-99-04,Tea,Drinks,1,4.50\n",
    b"Date,Product\n2026-11-04,Tea\n",
    b"date,product,category,quantity,revenue\n",
    b"date,product,category,quantity,revenue\n2026-11-04,Tea,Drinks,1,4.50,extra\n",
])
def test_invalid_csv_rejected(contents):
    with pytest.raises(HTTPException) as exc:
        parse_sales_csv(contents)
    assert exc.value.status_code == 422


def test_both_example_files(tmp_path):
    from pathlib import Path
    samples = Path(__file__).resolve().parent.parent / 'samples'
    for filename in ('omnistat_parser_minimal_SAMPLE.csv', 'square_item_sales_detail_SAMPLE.csv'):
        fmt, rows = parse_sales_csv((samples / filename).read_bytes())
        assert rows
        assert all(r['product'] and r['date'] for r in rows)
