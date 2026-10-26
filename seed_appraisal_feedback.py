"""Add safe synthetic supervisor appraisals and employee follow-ups for pipeline demos.

The script is additive and skips any employee who already has a supervisor form
for the target year. It previews by default; pass --apply to write records.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import inspect

import models
from database import SessionLocal, engine
from main import FOLLOWUP_CATEGORIES, SUPERVISOR_APPRAISAL_QUESTIONS_BY_FORM
from main import _build_supervisor_followup_questions


SEED_MARKER_PREFIX = "synthetic_appraisal_pipeline"
TONES = ("positive", "constructive", "mixed", "neutral")

SUPERVISOR_COMMENTS = {
    "communication": {
        "positive": "The employee shared clear, timely updates and checked that colleagues understood changes. The review record shows reliable handovers and prompt responses during busy work.",
        "constructive": "Some updates about pending work arrived late, leaving colleagues with limited time to adjust. A brief progress note at agreed checkpoints would improve coordination.",
        "mixed": "Routine communication was clear and respectful, but handovers during peak periods sometimes missed the next owner and deadline. A consistent handover checklist would help.",
        "neutral": "The employee provided regular progress updates, answered follow-up questions, and documented the status of assigned work during this review period.",
    },
    "collaboration": {
        "positive": "The employee contributed to shared tasks, listened to colleagues, and supported team members when workloads increased. Peers were kept informed as joint work progressed.",
        "constructive": "The employee completed individual duties, but could involve colleagues earlier when a task affects shared deadlines. More frequent coordination would reduce avoidable rework.",
        "mixed": "The employee supported the team during planned work, while cross-team coordination was less consistent when priorities changed. Agreeing owners at handover would strengthen delivery.",
        "neutral": "The employee participated in team meetings, completed assigned shared tasks, and coordinated with colleagues on routine work during the period.",
    },
    "learning_development": {
        "positive": "The employee applied new learning to daily work, acted on feedback, and shared useful knowledge with colleagues. A measurable next goal can extend this progress.",
        "constructive": "The employee attended learning activities, but evidence of applying the material in daily work was limited. Agreeing a practical task to use the skill would support progress.",
        "mixed": "The employee made progress on role knowledge and responded to some feedback, though development actions were not completed consistently. Breaking the goal into monthly steps may help.",
        "neutral": "The employee completed planned learning activities and discussed development goals with the supervisor. The next review can track how the learning is used in assigned work.",
    },
    "compliance_awareness": {
        "positive": "The employee followed documented procedures, checked records carefully, and escalated potential control concerns through the expected channel. This supported a clear audit trail.",
        "constructive": "A few work records required correction because control steps were not documented consistently. Using the approved checklist and escalating uncertainties earlier would reduce risk.",
        "mixed": "The employee followed routine controls and raised a concern appropriately, but documentation was incomplete on one handover. The next period should focus on consistent evidence capture.",
        "neutral": "The employee completed assigned compliance guidance, used approved procedures for routine tasks, and recorded control checks in the expected work materials.",
    },
}

EMPLOYEE_COMMENTS = {
    "communication": {
        "positive": "I kept colleagues updated on my work and clarified instructions when priorities changed. I will continue using concise handover notes and timely progress updates.",
        "constructive": "I could have shared a few updates earlier, especially when a task was delayed. I plan to raise blockers promptly and confirm who needs each update.",
        "mixed": "I communicated clearly in routine work, but my handovers were less detailed during busy periods. I will use a short checklist to include owners and deadlines.",
        "neutral": "I sent regular progress notes, responded to questions, and documented work status. I will keep these habits and discuss any communication gaps with my supervisor.",
    },
    "collaboration": {
        "positive": "I contributed to shared tasks and supported colleagues when deadlines overlapped. I will keep coordinating early and make sure each person understands the agreed next step.",
        "constructive": "I sometimes focused on my own tasks instead of checking whether the team needed help. I will ask about shared priorities during planning and handovers.",
        "mixed": "I supported colleagues on planned work, though I could have coordinated sooner when priorities shifted. I will clarify ownership before starting shared tasks.",
        "neutral": "I attended team discussions, completed my shared assignments, and coordinated routine handovers. I will continue contributing and raise dependencies earlier.",
    },
    "learning_development": {
        "positive": "I applied new guidance to my daily work and used feedback to improve my process. My next goal is to strengthen this skill through practice and review.",
        "constructive": "I completed learning activities but did not always apply them quickly in my work. I will identify a practical task after each session to reinforce the material.",
        "mixed": "I made progress in some development areas, but I did not complete every planned action. I will set smaller milestones and check progress with my supervisor.",
        "neutral": "I attended the planned learning activities and discussed my development goals. I will record examples of applying new knowledge during the next period.",
    },
    "compliance_awareness": {
        "positive": "I followed the documented steps and asked for clarification when a control requirement was unclear. I will continue keeping complete records and escalating concerns promptly.",
        "constructive": "I could have documented some control checks more consistently. I will use the approved checklist and review records before completing each handover.",
        "mixed": "I followed routine procedures, but some supporting notes were incomplete. I will improve evidence capture and ask for guidance when requirements change.",
        "neutral": "I completed required guidance, followed routine procedures, and recorded checks in the expected materials. I will continue to review updates relevant to my role.",
    },
}


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=datetime.now(ZoneInfo("Africa/Nairobi")).year)
    parser.add_argument("--count", type=int, default=5, help="Maximum number of employees to seed (default: 5).")
    parser.add_argument("--seed", type=int, default=42, help="Repeatable tone selection seed.")
    parser.add_argument("--apply", action="store_true", help="Write the previewed records to PostgreSQL.")
    parser.add_argument("--complete-all", action="store_true", help="Create a follow-up for Form 2 of the first test employee too.")
    return parser.parse_args()


def validate_question_bank():
    for form_number in (1, 2):
        questions = SUPERVISOR_APPRAISAL_QUESTIONS_BY_FORM[form_number]
        counts = Counter(question.get("category") for question in questions)
        expected = {category for category, _ in FOLLOWUP_CATEGORIES}
        if len(questions) != 16 or set(counts) != expected or any(counts[key] != 4 for key in expected):
            raise RuntimeError(f"Form {form_number} must have four questions in each of the four categories.")
        if any(question.get("type") != "open" for question in questions):
            raise RuntimeError(f"Form {form_number} contains a non-open-ended question.")


def answer_tone(employee_id, form_number, question_index, seed):
    return TONES[(employee_id + form_number * 3 + question_index + seed) % len(TONES)]


def supervisor_snapshot(employee, form_number, seed, marker):
    snapshot = []
    for index, question in enumerate(SUPERVISOR_APPRAISAL_QUESTIONS_BY_FORM[form_number]):
        tone = answer_tone(employee.employee_id, form_number, index, seed)
        comment = SUPERVISOR_COMMENTS[question["category"]][tone]
        snapshot.append({**question, "answer": comment, "seed_marker": marker, "synthetic_tone": tone})
    return snapshot


def employee_snapshot(appraisal, employee_id, form_number, seed):
    questions = _build_supervisor_followup_questions(appraisal)
    snapshot = []
    narrative = []
    for index, question in enumerate(questions):
        tone = answer_tone(employee_id, form_number + 2, index, seed)
        answer = EMPLOYEE_COMMENTS[question["category"]][tone]
        snapshot.append({**question, "answer": answer})
        narrative.append(f"{question['category_label']}:\n{answer}")
    return snapshot, "\n\n".join(narrative)


def main():
    args = parse_args()
    if args.year < 2000 or args.year > 9998:
        raise SystemExit("Choose a year between 2000 and 9998.")
    if args.count < 1:
        raise SystemExit("--count must be at least 1.")
    validate_question_bank()

    feedback_columns = {column["name"] for column in inspect(engine).get_columns("unstructured_feedback")}
    if "supervisor_appraisal_id" not in feedback_columns:
        raise SystemExit("Database migration is missing. Run migrations/20261025_appraisal_category_and_followup.sql first.")

    db = SessionLocal()
    try:
        period_codes = {f"{args.year}-H1", f"{args.year}-H2"}
        existing_employee_ids = {
            employee_id for (employee_id,) in db.query(models.SupervisorAppraisal.employee_id).filter(
                models.SupervisorAppraisal.period_code.in_(period_codes)
            ).distinct().all()
        }
        employees = db.query(models.Employee).join(
            models.ImmediateSupervisor,
            models.ImmediateSupervisor.supervisor_id == models.Employee.supervisor_id,
        ).filter(
            models.Employee.user_type == "employee",
            models.Employee.is_active.is_(True),
        ).order_by(models.Employee.employee_id.asc()).all()
        candidates = [employee for employee in employees if employee.employee_id not in existing_employee_ids][:args.count]
        if not candidates:
            print(f"No active assigned employees without {args.year} appraisal forms were found. No data changed.")
            return

        leave_pending_for = None if args.complete_all else candidates[0].employee_id
        print(f"Plan: {len(candidates)} employees; {len(candidates) * 2} supervisor forms; "
              f"{len(candidates) * 2 - (1 if leave_pending_for else 0)} employee follow-ups.")
        print("Synthetic records are marked and existing forms are skipped.")
        print("Employee IDs selected:", ", ".join(str(employee.employee_id) for employee in candidates))
        if leave_pending_for:
            print(f"One follow-up will remain pending for employee #{leave_pending_for} (Form 2) so the questionnaire can be tested.")
        if not args.apply:
            print("Preview only. Re-run with --apply to write these records.")
            return

        tz = ZoneInfo("Africa/Nairobi")
        created_forms = 0
        created_followups = 0
        for employee in candidates:
            for form_number in (1, 2):
                period_code = f"{args.year}-H{form_number}"
                created_at = datetime(args.year, 6 if form_number == 1 else 9, 20, 12, 0, tzinfo=tz)
                marker = f"{SEED_MARKER_PREFIX}_{args.year}_employee_{employee.employee_id}_form_{form_number}"
                appraisal = models.SupervisorAppraisal(
                    employee_id=employee.employee_id,
                    supervisor_id=employee.supervisor_id,
                    period_code=period_code,
                    form_number=form_number,
                    answers_snapshot=supervisor_snapshot(employee, form_number, args.seed, marker),
                    yes_count=0,
                    employee_notified_at=created_at,
                    created_at=created_at,
                )
                db.add(appraisal)
                db.flush()
                created_forms += 1

                if employee.employee_id == leave_pending_for and form_number == 2:
                    continue

                question_snapshot, narrative_text = employee_snapshot(
                    appraisal, employee.employee_id, form_number, args.seed
                )
                db.add(models.UnstructuredFeedback(
                    employee_id=employee.employee_id,
                    supervisor_id=employee.supervisor_id,
                    author_employee_id=employee.employee_id,
                    supervisor_appraisal_id=appraisal.appraisal_id,
                    narrative_text=narrative_text,
                    question_snapshot=question_snapshot,
                    data_source="synthetic_demo",
                    created_at=created_at,
                ))
                created_followups += 1

        db.commit()
        print(f"Saved {created_forms} supervisor forms and {created_followups} linked employee follow-ups.")
        print("Each form has 16 open-ended answers; each follow-up has four category answers.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
