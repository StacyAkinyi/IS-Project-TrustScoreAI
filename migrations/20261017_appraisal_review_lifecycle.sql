-- Run once against the same PostgreSQL database used by the FastAPI backend.
ALTER TABLE supervisor_appraisals
    ADD COLUMN IF NOT EXISTS review_edit_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS satisfied_at TIMESTAMPTZ NULL;
