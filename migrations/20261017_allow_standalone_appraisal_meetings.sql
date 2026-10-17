-- Allow a supervisor to book a check-in before submitting the semiannual form.
ALTER TABLE appraisal_meetings
    ALTER COLUMN appraisal_id DROP NOT NULL;
