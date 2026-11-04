"""Seed synthetic H1 supervisor appraisals for every eligible active employee.

Preview is the default. Add --apply to save forms and automatically classify
answers using the project's multi-label competency and direction models.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import models
from database import SessionLocal
from main import (
    competency_model, competency_thresholds, direction_model,
    _trust_run_model_version,
)
from seed_appraisal_feedback import supervisor_snapshot, validate_question_bank
from trust_score_pipeline import generate_run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=datetime.now(ZoneInfo("Africa/Nairobi")).year)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--apply", action="store_true", help="Save the previewed forms and classification results.")
    args = parser.parse_args()
    if not 2000 <= args.year <= 9998:
        raise SystemExit("Choose a year between 2000 and 9998.")
    validate_question_bank()
    if competency_model is None or direction_model is None:
        raise SystemExit("Install both classifier artifacts before seeding the H1 appraisals.")

    db = SessionLocal()
    try:
        period_code = f"{args.year}-H1"
        existing = {
            employee_id for (employee_id,) in db.query(models.SupervisorAppraisal.employee_id).filter_by(
                period_code=period_code, form_number=1
            ).distinct().all()
        }
        employees = db.query(models.Employee).join(
            models.ImmediateSupervisor,
            models.ImmediateSupervisor.supervisor_id == models.Employee.supervisor_id,
        ).filter(
            models.Employee.user_type == "employee",
            models.Employee.is_active.is_(True),
        ).order_by(models.Employee.employee_id.asc()).all()
        candidates = [employee for employee in employees if employee.employee_id not in existing]
        print(f"Eligible active employees: {len(employees)}")
        print(f"Employees already holding {period_code} Form 1: {len(existing)}")
        print(f"Synthetic supervisor forms planned: {len(candidates)}")
        print("Each form has 16 open-ended answers. Employee follow-ups are not generated or classified.")
        print("This synthetic material is for demonstration and must not be treated as actual employee evidence.")
        if not args.apply:
            print("Preview only. Add --apply to save the forms and classify answers.")
            return
        if not candidates:
            print("No new forms are needed; existing H1 forms will still be classified.")

        created_at = datetime(args.year, 6, 20, 12, 0, tzinfo=ZoneInfo("Africa/Nairobi"))
        for employee in candidates:
            marker = f"synthetic_appraisal_pipeline_{args.year}_employee_{employee.employee_id}_form_1"
            db.add(models.SupervisorAppraisal(
                employee_id=employee.employee_id,
                supervisor_id=employee.supervisor_id,
                period_code=period_code,
                form_number=1,
                answers_snapshot=supervisor_snapshot(employee, 1, args.seed, marker),
                yes_count=0,
                employee_notified_at=created_at,
                created_at=created_at,
            ))
        db.flush()

        model_version = _trust_run_model_version()
        start = datetime(args.year, 1, 1, tzinfo=timezone.utc)
        end = datetime(args.year, 7, 1, tzinfo=timezone.utc)
        classified_employees = 0
        for employee in employees:
            supervisor = db.query(models.ImmediateSupervisor).filter_by(
                supervisor_id=employee.supervisor_id
            ).first()
            if supervisor is None:
                continue
            generate_run(
                db=db,
                employee_id=employee.employee_id,
                generated_by_employee_id=supervisor.emp_id,
                period_type="semiannual",
                period_code=period_code,
                start=start,
                end=end,
                competency_model=competency_model,
                competency_thresholds=competency_thresholds,
                direction_model=direction_model,
                model_version=model_version,
            )
            classified_employees += 1
        db.commit()
        print(f"Saved {len(candidates)} new synthetic H1 forms and classified H1 appraisals for {classified_employees} active employees.")
        print("Trust Scores remain incomplete for any missing KPI groups or competency evidence.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
