-- Run once against the same PostgreSQL database used by FastAPI.
-- Link each employee self-questionnaire to the supervisor form it follows.
ALTER TABLE unstructured_feedback
    ADD COLUMN IF NOT EXISTS supervisor_appraisal_id INTEGER
    REFERENCES supervisor_appraisals(appraisal_id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS ix_unstructured_feedback_supervisor_appraisal_id
    ON unstructured_feedback(supervisor_appraisal_id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_unstructured_feedback_appraisal_author
    ON unstructured_feedback(supervisor_appraisal_id, author_employee_id)
    WHERE supervisor_appraisal_id IS NOT NULL AND author_employee_id IS NOT NULL;
