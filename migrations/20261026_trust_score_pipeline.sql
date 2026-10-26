-- Additive storage for model suggestions, human review decisions, and grouped Trust Score runs.
-- Existing appraisal and feedback data is preserved.

BEGIN;

CREATE TABLE IF NOT EXISTS feedback_classifications (
    classification_id SERIAL PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES employees(employee_id),
    source_type VARCHAR(30) NOT NULL
        CHECK (source_type IN ('supervisor_appraisal', 'employee_followup')),
    supervisor_appraisal_id INTEGER REFERENCES supervisor_appraisals(appraisal_id) ON DELETE CASCADE,
    feedback_id INTEGER REFERENCES unstructured_feedback(feedback_id) ON DELETE CASCADE,
    item_key VARCHAR(120) NOT NULL,
    category VARCHAR(40) NOT NULL
        CHECK (category IN ('communication', 'collaboration', 'compliance_awareness', 'learning_development')),
    statement_text TEXT NOT NULL,
    predicted_direction VARCHAR(20) NOT NULL
        CHECK (predicted_direction IN ('negative', 'positive', 'mixed', 'neutral')),
    confidence DOUBLE PRECISION NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    probabilities JSONB NOT NULL,
    review_status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (review_status IN ('pending', 'confirmed', 'excluded')),
    confirmed_direction VARCHAR(20)
        CHECK (confirmed_direction IS NULL OR confirmed_direction IN ('negative', 'positive', 'mixed', 'neutral')),
    reviewed_by_employee_id INTEGER REFERENCES employees(employee_id),
    reviewed_at TIMESTAMPTZ,
    model_version VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_feedback_classification_one_source CHECK (
        (supervisor_appraisal_id IS NOT NULL AND feedback_id IS NULL) OR
        (supervisor_appraisal_id IS NULL AND feedback_id IS NOT NULL)
    ),
    CONSTRAINT uq_feedback_classification_supervisor_item UNIQUE (supervisor_appraisal_id, item_key),
    CONSTRAINT uq_feedback_classification_employee_item UNIQUE (feedback_id, item_key)
);

CREATE INDEX IF NOT EXISTS ix_feedback_classifications_employee_id
    ON feedback_classifications(employee_id);
CREATE INDEX IF NOT EXISTS ix_feedback_classifications_review_status
    ON feedback_classifications(review_status);

CREATE TABLE IF NOT EXISTS trust_score_runs (
    run_id SERIAL PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES employees(employee_id),
    generated_by_employee_id INTEGER NOT NULL REFERENCES employees(employee_id),
    period_type VARCHAR(20) NOT NULL
        CHECK (period_type IN ('quarterly', 'semiannual', 'annual')),
    period_code VARCHAR(12) NOT NULL,
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    kpi_groups JSONB NOT NULL,
    feedback_groups JSONB NOT NULL,
    data_coverage JSONB NOT NULL,
    trust_score DOUBLE PRECISION CHECK (trust_score IS NULL OR trust_score BETWEEN 0 AND 100),
    score_status VARCHAR(20) NOT NULL DEFAULT 'incomplete'
        CHECK (score_status IN ('ready', 'awaiting_review', 'incomplete')),
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_trust_score_run_employee_period UNIQUE (employee_id, period_type, period_code)
);

CREATE INDEX IF NOT EXISTS ix_trust_score_runs_employee_id ON trust_score_runs(employee_id);
CREATE INDEX IF NOT EXISTS ix_trust_score_runs_period_code ON trust_score_runs(period_code);
CREATE INDEX IF NOT EXISTS ix_trust_score_runs_score_status ON trust_score_runs(score_status);
CREATE INDEX IF NOT EXISTS ix_trust_score_runs_generated_at ON trust_score_runs(generated_at);

COMMIT;
