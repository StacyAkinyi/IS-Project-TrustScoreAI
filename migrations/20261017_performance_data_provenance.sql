-- Run once against the PostgreSQL database used by FastAPI.
ALTER TABLE performance_records
    ADD COLUMN IF NOT EXISTS data_source VARCHAR(30) NOT NULL DEFAULT 'unknown';

ALTER TABLE performance_records
    DROP CONSTRAINT IF EXISTS ck_performance_data_source;
ALTER TABLE performance_records
    ADD CONSTRAINT ck_performance_data_source
    CHECK (data_source IN ('real_anonymized', 'synthetic_demo', 'unknown'));
