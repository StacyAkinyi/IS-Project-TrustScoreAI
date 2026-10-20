-- Preserve the provenance of feedback used for reporting and demo experiments.
ALTER TABLE unstructured_feedback
    ADD COLUMN IF NOT EXISTS data_source VARCHAR(30) NOT NULL DEFAULT 'unknown';
ALTER TABLE unstructured_feedback
    DROP CONSTRAINT IF EXISTS ck_feedback_data_source;
ALTER TABLE unstructured_feedback
    ADD CONSTRAINT ck_feedback_data_source
    CHECK (data_source IN ('real_anonymized', 'synthetic_demo', 'unknown'));
