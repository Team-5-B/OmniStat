-- OmniStat Sprint 2: Database performance and integrity indexes
-- Developer: Siddartha
-- Prerequisite: Migration 003 already applied
-- Non-destructive: creates indexes only

BEGIN;

-- Speed up duplicate file detection using SHA-256.
CREATE INDEX IF NOT EXISTS idx_uploads_processed_sha256
ON raw_csv_uploads (
    business_id,
    (raw_data->>'sha256')
)
WHERE status = 'processed';

-- Speed up detection of duplicate sales records
-- even when different CSV formats contain the same data.
CREATE INDEX IF NOT EXISTS idx_uploads_processed_data_hash
ON raw_csv_uploads (
    business_id,
    (raw_data->>'data_hash')
)
WHERE status = 'processed';

-- Improve lookup of recently processed CSV uploads.
CREATE INDEX IF NOT EXISTS idx_uploads_business_processed_at
ON raw_csv_uploads (
    business_id,
    processed_at DESC
)
WHERE status = 'processed';

COMMIT;