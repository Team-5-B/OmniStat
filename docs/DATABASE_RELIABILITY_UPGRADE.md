# OmniStat — Database Reliability Upgrade

**Developer:** Siddartha Reddy Pagilla  
**Project:** OmniStat Business Intelligence Platform  
**Branch:** integration/team-work-sprint2  
**Component:** PostgreSQL and FastAPI Backend

## 1. Overview

This upgrade improves the reliability and maintainability
of OmniStat's sales data processing system.

OmniStat accepts Point-of-Sale (POS) CSV uploads,
stores product-level sales records in PostgreSQL,
and calculates business performance metrics.

The new database reliability features help detect
inconsistencies between uploaded sales data and
the daily summaries used by the dashboard.

## 2. Database Performance Indexes

Migration file:

`migrations/004_sales_integrity_indexes.sql`

Three PostgreSQL indexes were added:

1. `idx_uploads_processed_sha256`
   - Supports processed-upload duplicate detection
     using the file's SHA-256 hash.

2. `idx_uploads_processed_data_hash`
   - Supports duplicate detection using normalized
     sales data hashes.

3. `idx_uploads_business_processed_at`
   - Supports recent processed-upload lookups
     for individual businesses.

These indexes use CREATE INDEX IF NOT EXISTS.

The migration does not intentionally delete,
truncate, or update existing sales records.

**Important:** Committing the SQL file does not
execute the migration. It must be reviewed,
backed up, and applied separately to PostgreSQL.

Query performance improvements have not yet
been benchmarked on a live database.

## 3. Sales Data Quality API

Endpoint:

GET /api/business/data-quality?days=30

Supported reporting windows:

- 7 days
- 30 days
- 90 days

The endpoint uses the authenticated owner's
business ID to scope its database queries.

Employees and unauthenticated users are not
permitted to access the report.

### Reported Information

- Total CSV uploads
- Successfully processed uploads
- Pending uploads
- Failed uploads
- Most recent processed upload
- Number of sales line items
- Net units sold
- Net sales revenue
- Number of dates with inconsistent totals
- Details of mismatched dates

### Possible Status Values

`ok`

No inconsistencies were detected within the
selected reporting window.

`needs_review`

At least one date contains a discrepancy
between line-item sales and daily summaries.

## 4. Reconciliation Logic

The API compares two PostgreSQL data sources:

**sales_line_items**
- Original product-level sales records
- Quantities sold
- Net sales revenue
- Business date

**daily_sales_aggregates**
- Aggregated daily revenue
- Aggregated daily units sold
- Business date

Detected issues include:

1. Missing daily summary
2. Summary without line items
3. Revenue or quantity mismatch

The endpoint is read-only.

It does not automatically overwrite,
repair, or delete database records.

## 5. Security

The API uses OmniStat's existing authentication
and owner-only authorization mechanisms.

Business identifiers are obtained from verified
authentication and membership information.

This prevents callers from choosing another
business's data through request parameters.

## 6. Automated Testing

Test files:

- tests/test_integrity_migration.py
- tests/test_data_quality.py

Migration tests verify basic SQL safeguards.

Data-quality tests cover:

- Correct sales totals
- Rejection of unauthorized users
- Detection of incorrect dashboard totals
- Supported reporting periods
- Rejection of invalid reporting periods

The data-quality tests use a mocked database.

They do not modify production data.

## 7. Remaining Verification

Before considering the database upgrade fully
validated, complete these checks:

- Verify the migration against the actual schema.
- Back up the PostgreSQL database.
- Apply the index migration safely.
- Verify the indexes were created.
- Check database query execution plans.
- Test reconciliation against real uploaded CSV data.
- Confirm totals match the Sales Intelligence Dashboard.
- Verify business isolation with multiple real accounts.

Automated tests passing does not replace
real PostgreSQL integration testing.

## 8. Git Development History

This upgrade was developed through separate commits:

1. PostgreSQL CSV upload performance indexes
2. PostgreSQL migration safety tests
3. Sales reconciliation backend implementation
4. FastAPI data-quality route registration
5. Automated data-quality endpoint tests
6. Database reliability documentation

The work builds upon OmniStat's existing Sprint 2
CSV processing, authentication, sales analytics,
and dashboard infrastructure.

## 9. Outcome

OmniStat now includes a backend mechanism for
auditing uploaded sales data against dashboard
aggregates.

The upgrade establishes a foundation for
stronger data integrity monitoring, database
performance tuning, and future automated
business reporting.
