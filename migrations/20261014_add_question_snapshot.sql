-- Preserve the exact reflection questions and telemetry state shown at submission time.
ALTER TABLE unstructured_feedback
    ADD COLUMN IF NOT EXISTS question_snapshot JSONB;
