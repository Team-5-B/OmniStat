# OmniStat Sales Intelligence — Test Execution Evidence

- **Execution date:** 2026-11-05 02:44:19 CST
- **Branch:** `siddartha/sales-intelligence`
- **Commit before test execution:** `38ab538`
- **Python:** `3.13.1`
- **Result:** ======================== 50 passed, 1 warning in 5.45s =========================
- **Process exit status:** 0 (0 means all pytest checks passed)

## Test modules executed

- `tests/test_account.py`
- `tests/test_auth.py`
- `tests/test_me.py`
- `tests/test_owner.py`
- `tests/test_sales_intelligence.py`
- `tests/test_siddartha_sprint2.py`
- `tests/test_upload_parser.py`

## Important scope note

The automated tests exercise Python APIs, database query behavior via mocks,
CSV parsing, product mix calculations, refund adjustments, and reporting
logic. They do **not** prove that a live browser uploaded files and updated
PostgreSQL. Those steps must be completed and recorded separately.

## Live integration acceptance checklist (complete after manual testing)

- [ ] Upload a CSV with current-period dates against local PostgreSQL
- [ ] Dashboard net sales and product mix match the uploaded CSV
- [ ] Switch between 7 / 30 / 90 day reporting windows
- [ ] Change trend granularity between daily and monthly
- [ ] Compare category growth and day-of-week averages
- [ ] Confirm account, team and invitation workflows still work
- [ ] Verify a second business cannot access this business's sales
- [ ] Check responsive layout on mobile

## Evidence file

`docs/SALES_INTELLIGENCE_PYTEST_OUTPUT.txt`
