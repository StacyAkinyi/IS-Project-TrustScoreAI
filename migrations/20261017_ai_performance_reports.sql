-- Saved AI-generated period reports. This migration is additive and preserves existing records.
CREATE TABLE IF NOT EXISTS ai_performance_reports (
    report_id SERIAL PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES employees(employee_id),
    generated_by_employee_id INTEGER NOT NULL REFERENCES employees(employee_id),
    period_type VARCHAR(20) NOT NULL CHECK (period_type IN ('quarterly', 'semiannual', 'annual')),
    period_code VARCHAR(12) NOT NULL,
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    telemetry_groups JSONB NOT NULL,
    feedback_dimensions JSONB NOT NULL,
    narrative JSONB NOT NULL,
    data_coverage JSONB NOT NULL,
    report_status VARCHAR(30) NOT NULL DEFAULT 'ai_draft' CHECK (report_status IN ('ai_draft', 'human_reviewed')),
    model_name VARCHAR(100) NOT NULL,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_ai_performance_reports_employee_id ON ai_performance_reports(employee_id);
CREATE INDEX IF NOT EXISTS ix_ai_performance_reports_generated_by_employee_id ON ai_performance_reports(generated_by_employee_id);
CREATE INDEX IF NOT EXISTS ix_ai_performance_reports_period_code ON ai_performance_reports(period_code);
CREATE INDEX IF NOT EXISTS ix_ai_performance_reports_generated_at ON ai_performance_reports(generated_at);
