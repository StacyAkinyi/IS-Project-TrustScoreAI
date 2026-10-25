-- Run once in the trust_score_ai_db PostgreSQL database before creating
-- the first admin account. This extends the existing allowed user types.
ALTER TABLE employees
    DROP CONSTRAINT IF EXISTS ck_employees_user_type;

ALTER TABLE employees
    ADD CONSTRAINT ck_employees_user_type
    CHECK (user_type IN ('employee', 'supervisor', 'executive', 'admin'));
