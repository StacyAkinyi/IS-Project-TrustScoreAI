-- Run once against the same PostgreSQL database used by FastAPI.
ALTER TABLE supervisor_appraisals
    ADD COLUMN IF NOT EXISTS form_number INTEGER NOT NULL DEFAULT 1;

ALTER TABLE supervisor_appraisals
    DROP CONSTRAINT IF EXISTS uq_supervisor_appraisal_employee_period;
ALTER TABLE supervisor_appraisals
    DROP CONSTRAINT IF EXISTS uq_supervisor_appraisal_employee_period_form;
ALTER TABLE supervisor_appraisals
    ADD CONSTRAINT uq_supervisor_appraisal_employee_period_form
    UNIQUE (employee_id, period_code, form_number);

ALTER TABLE supervisor_appraisals
    DROP CONSTRAINT IF EXISTS ck_supervisor_appraisal_form_number;
ALTER TABLE supervisor_appraisals
    ADD CONSTRAINT ck_supervisor_appraisal_form_number
    CHECK (form_number IN (1, 2));
