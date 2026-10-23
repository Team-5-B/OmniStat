# Siddartha — OmniStat Sprint 2 backend contribution

**Source:** *OmniStat Sprint 2 Plan*, tasks **3.2, 3.6, 4.2, 4.5, 4.6, 4.8**, plus the pre-sprint schema warning. These changes were built against the `New 22oct.zip` repository snapshot supplied for this task.

## Quick installation (in the OmniStat repo)

1. **Start on a clean personal feature branch.** Do not commit `.env` or credentials.
2. Extract the provided ZIP **into the repository root** (the folder containing `backend/` and `initialschema.sql`). The ZIP adds new files rather than replacing `backend/main.py`.
3. Run the **idempotent integration script** to register the new router while preserving current auth code:

   ```bash
   python3 scripts/apply_siddartha_sprint2.py
   ```

4. Ensure you are targeting the *lowercase test database* (`omnistat`), **not** the original `OmniStat`. Back up any important data. Then run the **non-destructive migration**:

   ```bash
   psql -d omnistat -v ON_ERROR_STOP=1 -f migrations/003_siddartha_sprint2.sql
   ```

   Do **not** rerun `initialschema.sql` on a database with data. It DROPS and recreates six core tables.

5. In your already-configured Python virtual environment, install requirements (if needed), then test:

   ```bash
   python -m pip install -r requirements.txt
   python -m pytest -v tests/test_siddartha_sprint2.py
   python -m pytest -v
   ```

6. To start the app locally, use your test database and a private JWT secret:

   ```bash
   export DB_NAME=omnistat
   export JWT_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
   python -m uvicorn backend.main:app --reload
   ```

   Open `http://127.0.0.1:8000/docs` to exercise the new routes. Frontend pages are served by the same app at port 8000.

7. Inspect changes and commit **on your feature branch**. Open a PR targeting `integration/team-work`:

   ```bash
   git status --short
   git diff --check
   git add backend/main.py backend/siddartha_sprint2.py initialschema.sql migrations/003_siddartha_sprint2.sql scripts/apply_siddartha_sprint2.py tests/test_siddartha_sprint2.py docs/SIDDARTHA_SPRINT2_README.md
   git commit -m "Implement Siddartha Sprint 2 sales and team APIs"
   git push -u origin HEAD
   ```

## Delivered endpoints and tables

| Task | Implementation | Behavior |
|---|---|---|
| 3.2 | `sales_line_items` + new `raw_csv_uploads` tracking columns | Itemized sales associated with correct upload/business; timestamps, row count, and error message |
| 3.6 | `GET /api/dashboard/summary` | JWT-authenticated 30-day KPIs and daily revenue, including zero-filled dates and an empty-state flag |
| 4.2 | `invites` | Unique invite code, business, creator, employee role, expiration, usage timestamp, and used-by reference |
| 4.5 | `GET /api/business/team`, `PATCH /api/business` | Owner-only team listing and business name updates |
| 4.6 | `POST /api/invites`, `GET /api/invites/{code}` | Owner issues a link; public signup page validates invite details without revealing the invite creator |
| 4.8 | `DELETE /api/business/team/{user_id}` | Owner-only employee membership removal; cannot remove owners, self, or users from another business |
| Pre-sprint | `initialschema.sql` warning | Highlights destructive reset behavior; the new migration is additive instead |

### Authentication and safety

- Protected endpoints validate JWT **and re-check the current business membership in PostgreSQL**. A removed employee's previously issued token no longer grants access to these endpoints.
- All database queries parameterize user values. Business-scoped queries use only the **verified token's business ID**, never a client-supplied business ID.
- New business-management and invite-creation routes require role `owner`; the lookup endpoint is deliberately public because an invited user is not signed in yet.
- Invite codes are 192-bit, URL-safe random secrets; default expiration is **7 days**, provisionally chosen until the team confirms its desired policy.
- The integration script replaces the original unfiltered frontend static mount with a type/path-limited static mount, to avoid leaking `.env`, `.gitignore`, SQL or backend source over HTTP.
- Removing a team member deletes only that business membership, not the user account (which might belong to another business).

### Proposed dashboard JSON contract (coordinate with Nicholas)

```json
{
  "period": "last_30_days",
  "has_data": false,
  "kpis": {
    "total_revenue": 0.0,
    "total_profit": 0.0,
    "items_sold_count": 0
  },
  "revenue_30_days": [
    {"date": "YYYY-MM-DD", "revenue": 0.0}
  ]
}
```

`revenue_30_days` contains **30 dates**, earliest first, through the database server's `CURRENT_DATE`. The list above shows only one representative element. KPI totals are computed from exactly the same 30-day date window. `has_data` is false when no daily aggregate rows exist, even though chart zeros still appear.

**This is a PROPOSED contract.** The sprint plan explicitly says the team still needs to finalize API field names. Nicholas must connect `dashboard.js` against the agreed response shape as task 3.11. The endpoint returns **stored aggregate data**, not invented sample revenue; it will remain empty until the CSV parser / save pipeline populates `daily_sales_aggregates` (Junior/Nicholas tasks 3.3–3.5).

### CSV parser handoff (coordinate with Junior and Nicholas)

`sales_line_items` contains:
`id`, `business_id`, `upload_id`, `business_date`, `product_name`, `category`, `quantity`, `revenue`, `created_at`.

It enforces that `(upload_id, business_id)` matches the original upload's business, preventing a cross-business mismatch. Signed quantities/revenues permit returns and refunds. `raw_csv_uploads` now additionally has `processed_at`, `row_count`, `error_message`, and `updated_at` (plus its existing `status`).

**No CSV parser or upload API is claimed here**; tasks 3.3–3.5 are assigned to Junior and Nicholas. They should agree on this row shape and any extra fields before building their processing logic.

### Invite sign-up handoff (coordinate with Junior)

`GET /api/invites/{code}` returns `{business_name, role, expires_at, valid}` when valid, 404 for unknown codes, and 410 for expired/used codes. `POST /api/invites` returns `code`, `invite_url` (`signup.html?invite=...`), `business_id`, `role`, and `expires_at`. Employee signup/consumption **is not implemented here** because `POST /api/auth/register-invite` is Junior's task 4.7. That endpoint must verify the code and **atomically** mark `invites.used_at` / `used_by` in the same transaction as the new account and membership creation, to prevent double use. It should not accept a `business_id` from an unverified URL query parameter.

### Test coverage and verified scope

The additional file `tests/test_siddartha_sprint2.py` contains **8 mocked-PostgreSQL API tests**, covering:
- 30-day dashboard output, KPIs, and empty state
- missing token, removed membership and business scoping
- owner-only team viewing and business rename
- invite generation, public lookup, expiration and one-time usage state
- employee removal and immediate access revocation
- block public HTTP access to repository secrets and source files

During package preparation, these 8 tests ran successfully using in-memory SQL fakes and temporary import stubs because the packaging environment lacked PostgreSQL and `psycopg`/`bcrypt`. **This is not a full local PostgreSQL acceptance test.** Run the supplied commands in your actual `.venv` to verify against your dependency versions, and verify SQL migration against your separate test database before claiming live end-to-end success. No CSV-to-dashboard, employee signup, or browser integration is claimed complete.
