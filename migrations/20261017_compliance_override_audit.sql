-- Run once against the PostgreSQL database used by the FastAPI backend.
ALTER TABLE appraisal_reports
    ADD COLUMN IF NOT EXISTS compliance_override_reason TEXT NULL,
    ADD COLUMN IF NOT EXISTS compliance_override_updated_at TIMESTAMPTZ NULL;

CREATE TABLE IF NOT EXISTS compliance_override_audit (
    audit_id SERIAL PRIMARY KEY,
    report_id INTEGER NOT NULL REFERENCES appraisal_reports(report_id),
    executive_id INTEGER NOT NULL REFERENCES executive_managers(executive_id),
    previous_status BOOLEAN NOT NULL,
    new_status BOOLEAN NOT NULL,
    justification TEXT NOT NULL CHECK (length(btrim(justification)) >= 10),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_compliance_override_audit_report_id
    ON compliance_override_audit (report_id);
CREATE INDEX IF NOT EXISTS ix_compliance_override_audit_executive_id
    ON compliance_override_audit (executive_id);
CREATE INDEX IF NOT EXISTS ix_compliance_override_audit_created_at
    ON compliance_override_audit (created_at);
