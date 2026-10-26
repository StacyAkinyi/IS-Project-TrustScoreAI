-- Preserve the old review records as superseded history, but permit multiple
-- competency labels for one answer and score only the current automatic labels.
BEGIN;

ALTER TABLE feedback_classifications
    ADD COLUMN IF NOT EXISTS is_current BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE feedback_classifications
    DROP CONSTRAINT IF EXISTS uq_feedback_classification_supervisor_item;
ALTER TABLE feedback_classifications
    DROP CONSTRAINT IF EXISTS uq_feedback_classification_employee_item;
ALTER TABLE feedback_classifications
    DROP CONSTRAINT IF EXISTS uq_feedback_classification_supervisor_item_category;
ALTER TABLE feedback_classifications
    DROP CONSTRAINT IF EXISTS uq_feedback_classification_employee_item_category;

ALTER TABLE feedback_classifications
    ADD CONSTRAINT uq_feedback_classification_supervisor_item_category
    UNIQUE (supervisor_appraisal_id, item_key, category);
ALTER TABLE feedback_classifications
    ADD CONSTRAINT uq_feedback_classification_employee_item_category
    UNIQUE (feedback_id, item_key, category);

DO $$
DECLARE constraint_name TEXT;
BEGIN
    FOR constraint_name IN
        SELECT conname
        FROM pg_constraint
        WHERE conrelid = 'feedback_classifications'::regclass
          AND contype = 'c'
          AND pg_get_constraintdef(oid) ILIKE '%review_status%'
    LOOP
        EXECUTE format('ALTER TABLE feedback_classifications DROP CONSTRAINT %I', constraint_name);
    END LOOP;
END $$;

ALTER TABLE feedback_classifications
    ADD CONSTRAINT ck_feedback_classification_review_status
    CHECK (review_status IN ('pending', 'confirmed', 'excluded', 'auto_classified', 'superseded'));

-- Old manually-reviewed records remain available for audit but are not scored.
UPDATE feedback_classifications
SET is_current = FALSE,
    review_status = 'superseded'
WHERE is_current = FALSE;

-- An old run waiting for manual confirmation cannot be treated as a score under
-- the current automatic policy. It can be regenerated from the stored forms.
UPDATE trust_score_runs
SET score_status = 'incomplete', trust_score = NULL
WHERE score_status = 'awaiting_review';

CREATE INDEX IF NOT EXISTS ix_feedback_classifications_is_current
    ON feedback_classifications(is_current);

COMMIT;
