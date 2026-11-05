-- Keep employment start date distinct from account creation time.
-- Nullable for existing employees so their real hire dates can be backfilled safely.
ALTER TABLE employees
    ADD COLUMN IF NOT EXISTS start_date DATE;
