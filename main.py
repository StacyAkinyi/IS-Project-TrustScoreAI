from fastapi import FastAPI, Depends, HTTPException, Query, status
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from zoneinfo import ZoneInfo
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from openai import OpenAI, OpenAIError
from typing import List, Optional, Any, Literal
import hashlib
import os
import json
import random
import re
import textwrap
from pathlib import Path
import secrets
import joblib
import numpy as np
from datetime import datetime, timedelta, timezone

import models
from models import Base
import schemas
import auth
from database import engine, get_db
from report_templates import build_local_report
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from trust_score_pipeline import (
    build_feedback_groups,
    build_kpi_groups,
    generate_run as generate_trust_score_run,
    get_period_classifications,
    recalculate_run as recalculate_trust_score_run,
    score_status as calculate_trust_score_status,
    serialize_classification,
    serialize_run,
)

load_dotenv(Path(__file__).resolve().parent / ".env")

security = HTTPBearer()

# ---------------------------------------------------------
# Application & Middleware Setup
# ---------------------------------------------------------
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="TrustScoreAI System API",
    description="Backend gateway routing quantitative KPIs and qualitative text to the ML engine."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", 
        "http://127.0.0.1:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    payload = auth.decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    employee_id = payload.get("employee_id")
    employee = db.query(models.Employee).filter(
        models.Employee.employee_id == employee_id,
        models.Employee.is_active.is_(True),
    ).first()
    if (
        not employee
        or payload.get("token_version") != employee.auth_token_version
    ):
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload


def ensure_employee_access(db: Session, current_user: dict, employee: models.Employee) -> None:
    role = current_user.get("role")
    user_id = current_user.get("user_id")
    if role == "employee" and current_user.get("employee_id") == employee.employee_id:
        return
    if role == "supervisor" and user_id == employee.supervisor_id:
        return
    if role == "executive":
        supervisor = db.query(models.ImmediateSupervisor).filter_by(
            supervisor_id=employee.supervisor_id, executive_id=user_id
        ).first()
        if supervisor:
            return
    raise HTTPException(status_code=403, detail="Access denied")


def ensure_supervisor_access(db: Session, current_user: dict, supervisor_id: int):
    supervisor = db.query(models.ImmediateSupervisor).filter_by(supervisor_id=supervisor_id).first()
    if not supervisor:
        raise HTTPException(status_code=404, detail="Supervisor not found")
    role = current_user.get("role")
    user_id = current_user.get("user_id")
    if (role == "supervisor" and user_id == supervisor_id) or (
        role == "executive" and user_id == supervisor.executive_id
    ):
        return supervisor
    raise HTTPException(status_code=403, detail="Access denied")



def ensure_admin(current_user: dict) -> None:
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Administrator access required")


def admin_employee_payload(db: Session, employee: models.Employee) -> dict:
    supervisor_profile = None
    executive_profile = None
    if employee.user_type == "supervisor":
        supervisor_profile = db.query(models.ImmediateSupervisor).filter_by(emp_id=employee.employee_id).first()
    elif employee.user_type == "executive":
        executive_profile = db.query(models.ExecutiveManager).filter_by(emp_id=employee.employee_id).first()
    elif employee.supervisor_id is not None:
        supervisor_profile = db.query(models.ImmediateSupervisor).filter_by(supervisor_id=employee.supervisor_id).first()
    if supervisor_profile is not None:
        executive_profile = supervisor_profile.executive
    return {
        "employee_id": employee.employee_id,
        "full_name": employee.full_name,
        "email": employee.email,
        "department": employee.department,
        "role": employee.role,
        "user_type": employee.user_type,
        "is_active": employee.is_active,
        "supervisor_id": employee.supervisor_id,
        "supervisor_name": supervisor_profile.full_name if supervisor_profile else None,
        "supervisor_profile_id": supervisor_profile.supervisor_id if employee.user_type == "supervisor" and supervisor_profile else None,
        "executive_id": executive_profile.executive_id if executive_profile else None,
        "executive_name": executive_profile.full_name if executive_profile else None,
        "branch_code": supervisor_profile.branch_code if supervisor_profile else None,
        "oversight_region": executive_profile.oversight_region if executive_profile else None,
        "created_at": employee.created_at,
    }


def active_supervisor_profile(db: Session, supervisor_id: int):
    return db.query(models.ImmediateSupervisor).join(
        models.Employee, models.ImmediateSupervisor.emp_id == models.Employee.employee_id
    ).filter(
        models.ImmediateSupervisor.supervisor_id == supervisor_id,
        models.Employee.is_active.is_(True),
    ).first()


def active_executive_profile(db: Session, executive_id: int):
    return db.query(models.ExecutiveManager).join(
        models.Employee, models.ExecutiveManager.emp_id == models.Employee.employee_id
    ).filter(
        models.ExecutiveManager.executive_id == executive_id,
        models.Employee.is_active.is_(True),
    ).first()


# Trust Scores combine four KPI groups with four automatically classified supervisor-feedback groups.

# Appraisal feedback direction model exported from grouped Colab training.
DIRECTION_MODEL_PATH = Path(__file__).resolve().parent / "trustscore_direction_model.joblib"
DIRECTION_METADATA_PATH = Path(__file__).resolve().parent / "trustscore_direction_model_metadata.json"
COMPETENCY_MODEL_PATH = Path(__file__).resolve().parent / "trustscore_competency_model.joblib"
COMPETENCY_METADATA_PATH = Path(__file__).resolve().parent / "trustscore_competency_model_metadata.json"
direction_model = None
direction_metadata = None
competency_model = None
competency_thresholds = {}
competency_metadata = None
try:
    direction_model = joblib.load(DIRECTION_MODEL_PATH)
    with DIRECTION_METADATA_PATH.open("r", encoding="utf-8") as metadata_file:
        direction_metadata = json.load(metadata_file)
    print("Appraisal direction model loaded.")
except Exception as exc:
    print(f"Appraisal direction model unavailable: {exc}")
try:
    competency_bundle = joblib.load(COMPETENCY_MODEL_PATH)
    competency_model = competency_bundle["model"]
    competency_thresholds = {
        str(key): float(value)
        for key, value in competency_bundle.get("thresholds", {}).items()
    }
    with COMPETENCY_METADATA_PATH.open("r", encoding="utf-8") as metadata_file:
        competency_metadata = json.load(metadata_file)
    print("Multi-label appraisal competency model loaded.")
except FileNotFoundError:
    print("Multi-label competency model missing. Run train_competency_classifier.py with the labeled workbook.")
except Exception as exc:
    print(f"Multi-label competency model unavailable: {exc}")




SUPERVISOR_APPRAISAL_QUESTIONS_BY_FORM = {
    1: [
        {"id": "comm_updates", "category": "communication", "type": "open", "prompt": "Describe an example of how accurately and promptly the employee kept relevant people informed, or what could improve."},
        {"id": "comm_listening", "category": "communication", "type": "open", "prompt": "How did the employee listen, clarify instructions, and communicate respectfully? Give a work example."},
        {"id": "comm_example", "category": "communication", "type": "open", "prompt": "Describe one specific example of the employee communicating clearly or where clearer communication would have helped."},
        {"id": "comm_context", "category": "communication", "type": "open", "prompt": "What communication context or support should be considered for the next review period?"},
        {"id": "collab_shared_work", "category": "collaboration", "type": "open", "prompt": "How did the employee contribute to shared team responsibilities? Include a specific example."},
        {"id": "collab_respect", "category": "collaboration", "type": "open", "prompt": "Describe how the employee considered colleagues' perspectives or handled a disagreement at work."},
        {"id": "collab_example", "category": "collaboration", "type": "open", "prompt": "Give an example of how the employee supported a colleague or helped a shared task succeed."},
        {"id": "collab_growth", "category": "collaboration", "type": "open", "prompt": "What is one practical way the employee could strengthen collaboration or coordination?"},
        {"id": "learning_application", "category": "learning_development", "type": "open", "prompt": "What training, coaching, or new knowledge did the employee apply, and what evidence shows its effect?"},
        {"id": "learning_feedback", "category": "learning_development", "type": "open", "prompt": "How did the employee respond to feedback or agreed development actions? Give an example."},
        {"id": "learning_example", "category": "learning_development", "type": "open", "prompt": "What skill or knowledge did the employee develop, and what work evidence shows its application?"},
        {"id": "learning_goal", "category": "learning_development", "type": "open", "prompt": "What is one measurable learning goal for the next six months, and what support would help?"},
        {"id": "compliance_procedures", "category": "compliance_awareness", "type": "open", "prompt": "Describe how the employee applied policies and control steps required for their role."},
        {"id": "compliance_escalation", "category": "compliance_awareness", "type": "open", "prompt": "How did the employee handle or escalate a potential control, privacy, or compliance concern?"},
        {"id": "compliance_example", "category": "compliance_awareness", "type": "open", "prompt": "Describe a specific example of the employee applying a control or handling a compliance concern appropriately."},
        {"id": "compliance_support", "category": "compliance_awareness", "type": "open", "prompt": "Where would additional guidance or training help the employee apply requirements consistently?"},
    ],
    2: [
        {"id": "comm_priority_updates", "category": "communication", "type": "open", "prompt": "Describe how the employee communicated when priorities changed, including the timeliness and clarity of updates."},
        {"id": "comm_handover", "category": "communication", "type": "open", "prompt": "How reliably did the employee document and hand over important work information? Give an example."},
        {"id": "comm_pressure_example", "category": "communication", "type": "open", "prompt": "Describe an example of the employee communicating effectively during a difficult or time-sensitive situation."},
        {"id": "comm_goal_progress", "category": "communication", "type": "open", "prompt": "What progress did the employee make on communication feedback from the previous review, and what remains to improve?"},
        {"id": "collab_coordination", "category": "collaboration", "type": "open", "prompt": "How did the employee coordinate handovers and shared work across the team? Give a specific example."},
        {"id": "collab_feedback", "category": "collaboration", "type": "open", "prompt": "Describe how the employee considered constructive input or helped resolve a team disagreement."},
        {"id": "collab_outcome", "category": "collaboration", "type": "open", "prompt": "Give an example of the employee contributing to a cross-team outcome or shared deliverable."},
        {"id": "collab_next_step", "category": "collaboration", "type": "open", "prompt": "What collaboration habit should the employee continue or change in the next review period?"},
        {"id": "learning_goal_progress", "category": "learning_development", "type": "open", "prompt": "What progress did the employee make on the learning goal from the previous review? Include evidence."},
        {"id": "learning_transfer", "category": "learning_development", "type": "open", "prompt": "How did the employee use new learning to improve work or solve a role-related problem?"},
        {"id": "learning_progress_example", "category": "learning_development", "type": "open", "prompt": "What evidence shows the employee's learning was applied or shared during this period?"},
        {"id": "learning_barrier", "category": "learning_development", "type": "open", "prompt": "What barrier affected development progress, and what realistic next goal should be agreed?"},
        {"id": "compliance_updates", "category": "compliance_awareness", "type": "open", "prompt": "How did the employee apply policy or control updates to day-to-day work? Provide evidence."},
        {"id": "compliance_training", "category": "compliance_awareness", "type": "open", "prompt": "What required compliance guidance did the employee complete and apply during this period?"},
        {"id": "compliance_risk_example", "category": "compliance_awareness", "type": "open", "prompt": "Describe an example of the employee identifying, preventing, or escalating a compliance risk."},
        {"id": "compliance_next_support", "category": "compliance_awareness", "type": "open", "prompt": "What compliance topic or control needs further coaching or clarification for the next period?"},
    ],
}


def current_review_period():
    today = datetime.now(ZoneInfo("Africa/Nairobi"))
    return f"{today.year}-H{1 if today.month <= 6 else 2}"


QUESTION_METRICS = [
    {"key": "transaction_accuracy", "label": "transaction accuracy", "unit": "%", "max": 100, "direction": "high", "decimals": 1},
    {"key": "workplan_completion", "label": "workplan completion", "unit": "%", "max": 120, "direction": "high", "decimals": 1},
    {"key": "task_deadline_fulfillment_pct", "label": "tasks completed on time", "unit": "%", "max": 100, "direction": "high", "decimals": 1},
    {"key": "complaint_resolution_rate_pct", "label": "complaint resolution", "unit": "%", "max": 100, "direction": "high", "decimals": 1},
    {"key": "customer_satisfaction", "label": "customer satisfaction", "unit": " / 5", "max": 5, "direction": "high", "decimals": 2},
    {"key": "error_frequencies", "label": "processing errors", "unit": "", "max": 10, "direction": "low", "decimals": 0},
    {"key": "loan_processing_turnaround_hours", "label": "loan processing time", "unit": " hours", "max": 168, "direction": "low", "decimals": 1},
    {"key": "non_performing_credit_pct", "label": "non-performing credit", "unit": "%", "max": 18, "direction": "low", "decimals": 1},
    {"key": "cash_reconciliation_errors", "label": "cash reconciliation errors", "unit": "", "max": 1, "direction": "low", "decimals": 0, "zero_tolerance": True},
    {"key": "compliance_incidents", "label": "compliance incidents", "unit": "", "max": 2, "direction": "low", "decimals": 0},
]


def _metric_value(record, metric):
    value = getattr(record, metric["key"], None)
    return float(value) if value is not None else None


def _format_metric_value(value, metric):
    return f"{value:.{metric['decimals']}f}{metric['unit']}"


def _metric_status_for_value(value, metric, observed_values=None):
    if value is None:
        return None
    observations = observed_values if observed_values is not None else [value]
    if metric.get("zero_tolerance") and any(float(item) > 0 for item in observations):
        return "Danger"
    normalized = value / max(float(metric["max"]), 1e-9)
    if metric["direction"] == "high":
        return "Danger" if normalized < 1 / 3 else "Warning" if normalized < 2 / 3 else "Safe"
    return "Safe" if normalized <= 1 / 3 else "Warning" if normalized <= 2 / 3 else "Danger"


def _metric_status(record, metric):
    return _metric_status_for_value(_metric_value(record, metric), metric)


def _aggregate_team_kpis(latest_records, employee_ids):
    """Average each KPI across each employee's latest telemetry row and apply the shared bands."""
    aggregate = []
    for metric in QUESTION_METRICS:
        values = [
            value for employee_id in employee_ids
            if employee_id in latest_records
            for value in [_metric_value(latest_records[employee_id], metric)]
            if value is not None
        ]
        if not values:
            aggregate.append({"key": metric["key"], "label": metric["label"],
                              "unit": metric["unit"], "value": None,
                              "state": "No data", "sample_count": 0})
            continue
        average = sum(values) / len(values)
        state = _metric_status_for_value(average, metric, values)
        aggregate.append({"key": metric["key"], "label": metric["label"],
                          "unit": metric["unit"], "value": average,
                          "state": state, "sample_count": len(values)})
    return aggregate


QUESTION_BANK_PATH = Path(__file__).resolve().parent / "data" / "appraisal_question_bank.json"
with QUESTION_BANK_PATH.open(encoding="utf-8-sig") as question_bank_file:
    APPRAISAL_QUESTION_BANK = json.load(question_bank_file)


def _build_reflection_questions(record):
    def make_question(text, state="no_data", metric=None, value=None):
        return {
            "text": text,
            "state": state,
            "metric_key": metric["key"] if metric else None,
            "metric_label": metric["label"] if metric else None,
            "value": _format_metric_value(value, metric) if metric and value is not None else None,
            "bank_version": 1,
        }

    if record is None:
        return [make_question(text) for text in random.sample(APPRAISAL_QUESTION_BANK["no_data"], k=3)]

    candidates = []
    for metric in QUESTION_METRICS:
        value = _metric_value(record, metric)
        state = _metric_status(record, metric)
        if value is not None and state:
            candidates.append({"metric": metric, "value": value, "state": state.lower()})

    if not candidates:
        return [make_question(text) for text in random.sample(APPRAISAL_QUESTION_BANK["no_data"], k=3)]

    selected = random.sample(candidates, k=min(3, len(candidates)))
    questions = []
    for item in selected:
        state, metric, value = item["state"], item["metric"], item["value"]
        text = random.choice(APPRAISAL_QUESTION_BANK[state]).format(
            metric=metric["label"],
            value=_format_metric_value(value, metric),
        )
        questions.append(make_question(text, state, metric, value))

    while len(questions) < 3:
        questions.append(make_question(random.choice(APPRAISAL_QUESTION_BANK["context"])))
    return questions[:3]
@app.get("/api/v1/employees/{employee_id}", response_model=schemas.EmployeeResponse)
def get_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    employee = db.query(models.Employee).filter_by(employee_id=employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    ensure_employee_access(db, current_user, employee)
    return employee


@app.get("/api/v1/employees/{employee_id}/performance", response_model=List[schemas.PerformanceRecordResponse])
def get_employee_performance(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    employee = db.query(models.Employee).filter_by(employee_id=employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    ensure_employee_access(db, current_user, employee)
    return db.query(models.PerformanceRecord).filter_by(employee_id=employee_id).order_by(
        models.PerformanceRecord.recorded_at.asc()
    ).all()


@app.get("/api/v1/employees/{employee_id}/reports", response_model=List[schemas.AppraisalReportResponse])
def get_employee_reports(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    employee = db.query(models.Employee).filter_by(employee_id=employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    ensure_employee_access(db, current_user, employee)
    return db.query(models.AppraisalReport).filter_by(employee_id=employee_id).order_by(
        models.AppraisalReport.generation_date.asc()
    ).all()


@app.get("/api/v1/employees/{employee_id}/generate-prompt")
def generate_appraisal_prompt(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") != "employee" or current_user.get("employee_id") != employee_id:
        raise HTTPException(status_code=403, detail="Access denied")
    appraisals = db.query(models.SupervisorAppraisal).filter_by(
        employee_id=employee_id
    ).order_by(models.SupervisorAppraisal.created_at.desc()).all()
    if not appraisals:
        return {"employee_id": employee_id, "available": False, "questions": [],
                "message": "A supervisor appraisal must be submitted before the self-questionnaire is available."}

    appraisal_ids = [row.appraisal_id for row in appraisals]
    completed_ids = {
        appraisal_id for (appraisal_id,) in db.query(
            models.UnstructuredFeedback.supervisor_appraisal_id
        ).filter(
            models.UnstructuredFeedback.supervisor_appraisal_id.in_(appraisal_ids),
            models.UnstructuredFeedback.author_employee_id == employee_id,
        ).all()
    }
    appraisal = next((row for row in appraisals if row.appraisal_id not in completed_ids), None)
    if appraisal is None:
        return {"employee_id": employee_id, "available": False, "questions": [],
                "message": "You have completed a self-questionnaire for each submitted supervisor appraisal."}

    question_snapshot = _build_supervisor_followup_questions(appraisal)
    return {
        "employee_id": employee_id,
        "available": True,
        "supervisor_appraisal_id": appraisal.appraisal_id,
        "form_number": appraisal.form_number,
        "period_code": appraisal.period_code,
        "questions": [item["text"] for item in question_snapshot],
        "question_snapshot": question_snapshot,
        "method": "competency follow-up grounded in the employee's submitted supervisor appraisal",
    }


FOLLOWUP_CATEGORIES = [
    ("communication", "Communication"),
    ("collaboration", "Collaboration"),
    ("learning_development", "Learning and development"),
    ("compliance_awareness", "Compliance awareness"),
]


def _build_supervisor_followup_questions(appraisal):
    answers_by_category = {key: [] for key, _ in FOLLOWUP_CATEGORIES}
    for item in appraisal.answers_snapshot or []:
        category = item.get("category")
        answer = item.get("answer")
        if category in answers_by_category and isinstance(answer, str) and answer.strip():
            answers_by_category[category].append(answer.strip())

    questions = []
    for category, title in FOLLOWUP_CATEGORIES:
        supervisor_context = " ".join(answers_by_category[category])
        if len(supervisor_context) > 500:
            supervisor_context = supervisor_context[:497].rsplit(" ", 1)[0] + "..."
        context_line = (
            f"Your supervisor's {title.lower()} section noted: “{supervisor_context}” "
            if supervisor_context else
            f"Your supervisor completed the {title.lower()} section. "
        )
        text = (
            f"{context_line}What context or work evidence would you add, what did you learn "
            "from this review period, and what practical support or next step would help you?"
        )
        questions.append({
            "id": f"self_{category}",
            "category": category,
            "category_label": title,
            "text": text,
            "source_appraisal_id": appraisal.appraisal_id,
        })
    return questions


class SelfAppraisalResponse(BaseModel):
    question_id: str
    category: Literal["communication", "collaboration", "learning_development", "compliance_awareness"]
    answer: str = Field(min_length=10, max_length=3000)


class SelfAppraisalSubmission(BaseModel):
    generated_questions: Optional[List[str]] = None
    question_snapshot: Optional[List[dict]] = None
    supervisor_appraisal_id: Optional[int] = None
    responses: Optional[List[SelfAppraisalResponse]] = None
    feedback_text: Optional[str] = None


@app.post("/evaluate-employee/")
def save_self_appraisal(
    payload: SelfAppraisalSubmission,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") != "employee":
        raise HTTPException(status_code=403, detail="Only employees can submit a self-appraisal")
    employee_id = current_user["employee_id"]
    employee = db.query(models.Employee).filter(
        models.Employee.employee_id == employee_id,
        models.Employee.is_active.is_(True),
    ).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee account not found")

    if payload.supervisor_appraisal_id is not None:
        appraisal = db.query(models.SupervisorAppraisal).filter_by(
            appraisal_id=payload.supervisor_appraisal_id,
            employee_id=employee_id,
        ).first()
        if not appraisal:
            raise HTTPException(status_code=404, detail="The supervisor appraisal was not found for this employee")
        if db.query(models.UnstructuredFeedback.feedback_id).filter_by(
            supervisor_appraisal_id=appraisal.appraisal_id,
            author_employee_id=employee_id,
        ).first():
            raise HTTPException(status_code=409, detail="A self-questionnaire has already been submitted for this appraisal")

        expected_snapshot = _build_supervisor_followup_questions(appraisal)
        expected_questions = [item["text"] for item in expected_snapshot]
        if payload.generated_questions != expected_questions or payload.question_snapshot != expected_snapshot:
            raise HTTPException(status_code=409, detail="The questionnaire changed. Reload it and try again.")
        if payload.responses is None or len(payload.responses) != len(FOLLOWUP_CATEGORIES):
            raise HTTPException(status_code=422, detail="Answer all four category questions before submitting")
        response_by_category = {item.category: item for item in payload.responses}
        if set(response_by_category) != {category for category, _ in FOLLOWUP_CATEGORIES}:
            raise HTTPException(status_code=422, detail="Provide exactly one response for each appraisal category")

        saved_snapshot = []
        narrative_lines = []
        for question in expected_snapshot:
            response = response_by_category[question["category"]]
            if response.question_id != question["id"]:
                raise HTTPException(status_code=422, detail="A response does not match its questionnaire item")
            answer = response.answer.strip()
            if len(answer) < 10:
                raise HTTPException(status_code=422, detail="Each response must contain at least 10 characters")
            saved_snapshot.append({**question, "answer": answer})
            narrative_lines.append(f"{question['category_label']}:\n{answer}")

        feedback = models.UnstructuredFeedback(
            employee_id=employee_id,
            supervisor_id=employee.supervisor_id,
            author_employee_id=employee_id,
            supervisor_appraisal_id=appraisal.appraisal_id,
            narrative_text="\n\n".join(narrative_lines),
            question_snapshot=saved_snapshot,
        )
        try:
            db.add(feedback)
            db.commit()
            db.refresh(feedback)
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=409, detail="A self-questionnaire has already been submitted for this appraisal")
        return {
            "status": "saved",
            "feedback_id": feedback.feedback_id,
            "supervisor_appraisal_id": appraisal.appraisal_id,
            "message": f"Your self-questionnaire for Form {appraisal.form_number} ({appraisal.period_code}) is saved and linked to the supervisor appraisal.",
        }

    if not payload.generated_questions or not payload.question_snapshot or not payload.feedback_text:
        raise HTTPException(status_code=422, detail="The reflection questions and response are required")
    if len(payload.generated_questions) != 3 or len(payload.question_snapshot) != 3:
        raise HTTPException(status_code=422, detail="Exactly three reflection questions are required")
    snapshot_texts = [item.get("text") for item in payload.question_snapshot]
    if snapshot_texts != payload.generated_questions:
        raise HTTPException(status_code=422, detail="The saved questions must match the questions shown")

    response_text = payload.feedback_text.strip()
    if not response_text:
        raise HTTPException(status_code=422, detail="Please enter your reflection before submitting")
    if len(response_text) > 10000:
        raise HTTPException(status_code=422, detail="Your reflection must be 10,000 characters or fewer")

    feedback = models.UnstructuredFeedback(
        employee_id=employee_id,
        supervisor_id=employee.supervisor_id,
        author_employee_id=employee_id,
        narrative_text=response_text,
        question_snapshot=payload.question_snapshot,
    )
    try:
        db.add(feedback)
        db.commit()
        db.refresh(feedback)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="The reflection could not be saved. Please try again")

    return {
        "status": "saved",
        "feedback_id": feedback.feedback_id,
        "message": "Your reflection and the three questions shown are saved together in PostgreSQL.",
    }


class DirectionClassificationRequest(BaseModel):
    employee_id: int = Field(ge=1)
    category: Literal["collaboration", "communication", "compliance_awareness", "learning_development"]
    statement: str = Field(min_length=1, max_length=10000)


@app.post("/api/v1/feedback/classify")
def classify_appraisal_feedback(
    payload: DirectionClassificationRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Return a direction suggestion; never assign a numerical score."""
    if direction_model is None or direction_metadata is None:
        raise HTTPException(status_code=503, detail="The appraisal direction model is not available.")

    employee = db.query(models.Employee).filter_by(employee_id=payload.employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    ensure_employee_access(db, current_user, employee)

    category_text = payload.category.strip().lower().replace("_", " ")
    cleaned_statement = " ".join(payload.statement.strip().lower().split())
    model_input = f"{category_text} [SEP] {cleaned_statement}"
    try:
        classifier = direction_model.named_steps["classifier"]
        labels = [str(label) for label in classifier.classes_]
        probabilities = direction_model.predict_proba([model_input])[0]
        predicted_direction = str(direction_model.predict([model_input])[0])
    except Exception as exc:
        raise HTTPException(status_code=503, detail="The direction model could not classify this statement.") from exc

    confidence_by_direction = {
        label: round(float(probability), 4)
        for label, probability in zip(labels, probabilities)
    }
    if predicted_direction == "negative":
        scoring_action = "supervisor_confirmation_required"
    elif predicted_direction == "positive":
        scoring_action = "human_review_required"
    else:
        scoring_action = "do_not_score"

    return {
        "employee_id": payload.employee_id,
        "category": payload.category,
        "predicted_direction": predicted_direction,
        "confidence": confidence_by_direction.get(predicted_direction, 0.0),
        "probabilities": confidence_by_direction,
        "scoring_action": scoring_action,
        "numerical_score": None,
        "notice": "This is a review suggestion only; it does not change the employee's Trust Score.",
    }

COACHING_TOPICS = {
    "skills": "practical skill development and practice",
    "role": "understanding role expectations and day-to-day responsibilities",
    "career": "career path exploration and continuous development",
    "compliance": "general compliance awareness and ethical decision-making",
    "wellbeing": "work stress, workload, and sustainable wellbeing",
    "prioritization": "time management and task prioritization",
}


class CoachingMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class CoachingChatRequest(BaseModel):
    topic: str
    messages: List[CoachingMessage]


class AIReportGenerateRequest(BaseModel):
    employee_id: int
    period_type: Literal["quarterly", "semiannual", "annual"]
    year: int
    period_number: Optional[int] = None


class TrustScoreRunRequest(BaseModel):
    employee_id: int = Field(ge=1)
    period_type: Literal["quarterly", "semiannual", "annual"]
    year: int = Field(ge=2000, le=9998)
    period_number: Optional[int] = None


class TrustScoreBatchRequest(BaseModel):
    period_type: Literal["quarterly", "semiannual", "annual"]
    year: int = Field(ge=2000, le=9998)
    period_number: Optional[int] = None


class FeedbackClassificationReviewRequest(BaseModel):
    decision: Literal["negative", "positive", "mixed", "neutral", "exclude"]


def _report_period(payload: AIReportGenerateRequest):
    if payload.year < 2000 or payload.year > datetime.now(timezone.utc).year + 1:
        raise HTTPException(status_code=422, detail="Choose a valid report year")
    if payload.period_type == "quarterly":
        if payload.period_number not in (1, 2, 3, 4):
            raise HTTPException(status_code=422, detail="Choose quarter 1, 2, 3, or 4")
        month = (payload.period_number - 1) * 3 + 1
        start = datetime(payload.year, month, 1, tzinfo=timezone.utc)
        end = datetime(payload.year + (month + 2) // 12, (month + 2) % 12 + 1, 1, tzinfo=timezone.utc)
        code = f"{payload.year}-Q{payload.period_number}"
    elif payload.period_type == "semiannual":
        if payload.period_number not in (1, 2):
            raise HTTPException(status_code=422, detail="Choose half 1 or 2")
        month = 1 if payload.period_number == 1 else 7
        start = datetime(payload.year, month, 1, tzinfo=timezone.utc)
        end = datetime(payload.year + (1 if month == 7 else 0), 1 if month == 7 else 7, 1, tzinfo=timezone.utc)
        code = f"{payload.year}-H{payload.period_number}"
    else:
        if payload.period_number is not None:
            raise HTTPException(status_code=422, detail="Annual reports do not use a period number")
        start = datetime(payload.year, 1, 1, tzinfo=timezone.utc)
        end = datetime(payload.year + 1, 1, 1, tzinfo=timezone.utc)
        code = str(payload.year)
    return start, end, code


def _trust_period(payload):
    return _report_period(AIReportGenerateRequest(
        employee_id=getattr(payload, "employee_id", 1),
        period_type=payload.period_type,
        year=payload.year,
        period_number=payload.period_number,
    ))


def _trust_run_model_version():
    category_version = str((competency_metadata or {}).get("model_version", "tfidf-ovr-appraisal-competencies-v1"))
    direction_version = str((direction_metadata or {}).get("model_version", "trustscore_direction_model.joblib"))
    return f"{category_version}+{direction_version}"


def _serialize_trust_run_for_api(db: Session, run: models.TrustScoreRun):
    classifications, appraisals, _ = get_period_classifications(
        db, run.employee_id, run.period_start, run.period_end
    )
    records = db.query(models.PerformanceRecord).filter(
        models.PerformanceRecord.employee_id == run.employee_id,
        models.PerformanceRecord.recorded_at >= run.period_start,
        models.PerformanceRecord.recorded_at < run.period_end,
    ).all()
    kpi_groups, cash_alert = build_kpi_groups(records)
    feedback_groups, _ = build_feedback_groups(classifications)
    trust_score, score_status = calculate_trust_score_status(kpi_groups, feedback_groups)

    supervisor_answer_count = sum(
        1
        for appraisal in appraisals
        for answer in (
            appraisal.answers_snapshot
            if isinstance(appraisal.answers_snapshot, list)
            else []
        )
        if isinstance(answer, dict)
        and isinstance(answer.get("answer"), str)
        and answer["answer"].strip()
    )
    assigned_answer_keys = {
        (row.supervisor_appraisal_id, row.item_key)
        for row in classifications
    }
    coverage = dict(run.data_coverage or {})
    coverage.update({
        "performance_record_count": len(records),
        "supervisor_form_count": len(appraisals),
        "supervisor_answer_count": supervisor_answer_count,
        "unassigned_supervisor_answer_count": max(
            0, supervisor_answer_count - len(assigned_answer_keys)
        ),
        "classified_answer_category_count": len(classifications),
        "employee_followups_scored": False,
        "pending_review_count": 0,
        "scored_group_count": sum(
            item.get("score_0_100") is not None
            for item in [*kpi_groups.values(), *feedback_groups.values()]
        ),
        "cash_reconciliation_zero_tolerance_alert": cash_alert,
    })

    result = serialize_run(run, classifications)
    result.update({
        "kpi_groups": kpi_groups,
        "feedback_groups": feedback_groups,
        "trust_score": trust_score,
        "score_status": score_status,
        "data_coverage": coverage,
    })
    return result


def _check_trust_score_access(db: Session, current_user: dict, employee: models.Employee):
    if current_user.get("role") == "admin":
        ensure_admin(current_user)
        return
    ensure_employee_access(db, current_user, employee)


def _generate_trust_score_for_employee(db: Session, employee_id: int, actor_id: int, payload):
    if competency_model is None:
        raise HTTPException(status_code=503, detail="The multi-label competency model is not installed. Train it with train_competency_classifier.py, then restart the API.")
    if direction_model is None:
        raise HTTPException(status_code=503, detail="The appraisal direction model is unavailable.")
    start, end, period_code = _trust_period(payload)
    try:
        run, _ = generate_trust_score_run(
            db=db,
            employee_id=employee_id,
            generated_by_employee_id=actor_id,
            period_type=payload.period_type,
            period_code=period_code,
            start=start,
            end=end,
            competency_model=competency_model,
            competency_thresholds=competency_thresholds,
            direction_model=direction_model,
            model_version=_trust_run_model_version(),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return run


@app.post("/api/v1/trust-score-runs")
def generate_employee_trust_score_run(
    payload: TrustScoreRunRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    employee = db.query(models.Employee).filter_by(employee_id=payload.employee_id, is_active=True).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    _check_trust_score_access(db, current_user, employee)
    try:
        run = _generate_trust_score_for_employee(db, employee.employee_id, current_user["employee_id"], payload)
        db.commit()
        db.refresh(run)
        return _serialize_trust_run_for_api(db, run)
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="The Trust Score pipeline could not finish. Please retry.") from exc


@app.get("/api/v1/employees/{employee_id}/trust-score-runs")
def list_employee_trust_score_runs(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    employee = db.query(models.Employee).filter_by(employee_id=employee_id, is_active=True).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    _check_trust_score_access(db, current_user, employee)
    rows = db.query(models.TrustScoreRun).filter_by(employee_id=employee_id).order_by(
        models.TrustScoreRun.generated_at.desc()
    ).limit(12).all()
    return [_serialize_trust_run_for_api(db, row) for row in rows]


@app.get("/api/v1/supervisors/{supervisor_id}/trust-score-runs")
def list_supervisor_team_trust_score_runs(
    supervisor_id: int,
    year: int = Query(ge=2000, le=9998),
    period_type: Literal["quarterly", "semiannual", "annual"] = "semiannual",
    period_number: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    ensure_supervisor_access(db, current_user, supervisor_id)
    if current_user.get("role") != "supervisor":
        raise HTTPException(status_code=403, detail="Only the assigned supervisor can view these team runs")
    start, end, period_code = _report_period(AIReportGenerateRequest(
        employee_id=1, period_type=period_type, year=year, period_number=period_number
    ))
    employees = db.query(models.Employee).filter_by(
        supervisor_id=supervisor_id, user_type="employee", is_active=True
    ).all()
    employee_names = {employee.employee_id: employee.full_name for employee in employees}
    if not employee_names:
        return []
    runs = db.query(models.TrustScoreRun).filter(
        models.TrustScoreRun.employee_id.in_(employee_names.keys()),
        models.TrustScoreRun.period_type == period_type,
        models.TrustScoreRun.period_code == period_code,
    ).order_by(models.TrustScoreRun.generated_at.desc()).all()
    return [{
        **_serialize_trust_run_for_api(db, run),
        "employee_name": employee_names.get(run.employee_id),
    } for run in runs]


@app.post("/api/v1/supervisors/{supervisor_id}/trust-score-runs")
def generate_supervisor_team_trust_score_runs(
    supervisor_id: int,
    payload: TrustScoreBatchRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    ensure_supervisor_access(db, current_user, supervisor_id)
    if current_user.get("role") != "supervisor":
        raise HTTPException(status_code=403, detail="Only the immediate supervisor can run team appraisal classification")
    employees = db.query(models.Employee).filter_by(
        supervisor_id=supervisor_id, user_type="employee", is_active=True
    ).order_by(models.Employee.employee_id).all()
    try:
        runs = [
            _generate_trust_score_for_employee(db, employee.employee_id, current_user["employee_id"], payload)
            for employee in employees
        ]
        db.commit()
        employee_names = {
            employee.employee_id: employee.full_name
            for employee in employees
        }
        return {
            "period_type": payload.period_type,
            "period_code": runs[0].period_code if runs else None,
            "employees_processed": len(runs),
            "scores_ready": sum(run.score_status == "ready" for run in runs),
            "incomplete": sum(run.score_status == "incomplete" for run in runs),
            "runs": [{
                **_serialize_trust_run_for_api(db, run),
                "employee_name": employee_names.get(run.employee_id),
            } for run in runs],
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="The team Trust Score pipeline could not finish. Please retry.") from exc


@app.get("/api/v1/supervisors/{supervisor_id}/feedback-classifications/pending")
def list_supervisor_feedback_review_queue(
    supervisor_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    ensure_supervisor_access(db, current_user, supervisor_id)
    if current_user.get("role") != "supervisor":
        raise HTTPException(status_code=403, detail="Only the immediate supervisor can review team feedback classifications")
    rows = db.query(models.FeedbackClassification, models.Employee.full_name).join(
        models.Employee, models.Employee.employee_id == models.FeedbackClassification.employee_id
    ).filter(
        models.Employee.supervisor_id == supervisor_id,
        models.Employee.is_active.is_(True),
        models.FeedbackClassification.review_status == "pending",
    ).order_by(
        models.Employee.full_name,
        models.FeedbackClassification.category,
        models.FeedbackClassification.classification_id,
    ).limit(500).all()
    return [
        {**serialize_classification(row), "employee_name": employee_name}
        for row, employee_name in rows
    ]


@app.patch("/api/v1/feedback-classifications/{classification_id}/review")
def review_feedback_classification(
    classification_id: int,
    payload: FeedbackClassificationReviewRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") not in {"supervisor", "executive", "admin"}:
        raise HTTPException(status_code=403, detail="A supervisor or executive must review this model suggestion")
    row = db.query(models.FeedbackClassification).filter_by(classification_id=classification_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Feedback classification not found")
    employee = db.query(models.Employee).filter_by(employee_id=row.employee_id, is_active=True).first()
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    _check_trust_score_access(db, current_user, employee)
    row.reviewed_by_employee_id = current_user["employee_id"]
    row.reviewed_at = datetime.now(timezone.utc)
    if payload.decision == "exclude":
        row.review_status = "excluded"
        row.confirmed_direction = None
    else:
        row.review_status = "confirmed"
        row.confirmed_direction = payload.decision
    try:
        db.flush()
        runs = db.query(models.TrustScoreRun).filter_by(employee_id=employee.employee_id).all()
        updated = []
        for run in runs:
            source_time = None
            if row.supervisor_appraisal_id is not None:
                source = db.query(models.SupervisorAppraisal).filter_by(
                    appraisal_id=row.supervisor_appraisal_id
                ).first()
                source_time = source.created_at if source else None
            elif row.feedback_id is not None:
                source = db.query(models.UnstructuredFeedback).filter_by(
                    feedback_id=row.feedback_id
                ).first()
                source_time = source.created_at if source else None
            if source_time and run.period_start <= source_time < run.period_end:
                recalculate_trust_score_run(db, run)
                updated.append(run)
        db.commit()
        db.refresh(row)
        return {
            "classification": serialize_classification(row),
            "updated_runs": [{
                "run_id": run.run_id,
                "period_code": run.period_code,
                "trust_score": run.trust_score,
                "score_status": run.score_status,
                "feedback_groups": run.feedback_groups,
            } for run in updated],
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="The review could not be saved. Please retry.") from exc


REPORT_METRICS = {
    "transaction_accuracy": (0, 100, "high", "Transaction accuracy", "%"),
    "error_frequencies": (0, 10, "low", "Processing errors", ""),
    "cash_reconciliation_errors": (0, 1, "low", "Cash reconciliation errors", ""),
    "workplan_completion": (0, 120, "high", "Workplan completion", "%"),
    "task_deadline_fulfillment_pct": (0, 100, "high", "Tasks completed on time", "%"),
    "loan_processing_turnaround_hours": (0, 168, "low", "Loan processing time", " hours"),
    "customer_satisfaction": (1, 5, "high", "Customer satisfaction", " / 5"),
    "complaint_resolution_rate_pct": (0, 100, "high", "Complaint resolution", "%"),
    "non_performing_credit_pct": (0, 18, "low", "Non-performing credit", "%"),
    "compliance_incidents": (0, 2, "low", "Compliance incidents", ""),
}
REPORT_GROUPS = {
    "operational_quality": ["transaction_accuracy", "error_frequencies"],
    "delivery_timeliness": ["workplan_completion", "task_deadline_fulfillment_pct", "loan_processing_turnaround_hours"],
    "customer_outcomes": ["customer_satisfaction", "complaint_resolution_rate_pct"],
    "risk_controls": ["non_performing_credit_pct", "cash_reconciliation_errors", "compliance_incidents"],
}
REPORT_DIMENSIONS = [
    "communication", "collaboration", "compliance_awareness", "learning_development"
]


def _report_state(score):
    if score is None:
        return "No data"
    if score < 100 / 3:
        return "Danger"
    if score < 200 / 3:
        return "Warning"
    return "Safe"


def _build_report_telemetry(records):
    group_outputs, _cash_alert = build_kpi_groups(records)
    units = {
        "transaction_accuracy": "%",
        "error_frequencies": "",
        "cash_reconciliation_errors": "",
        "workplan_completion": "%",
        "task_deadline_fulfillment_pct": "%",
        "loan_processing_turnaround_hours": " hours",
        "customer_satisfaction": " / 5",
        "complaint_resolution_rate_pct": "%",
        "non_performing_credit_pct": "%",
        "compliance_incidents": "",
    }
    for group in group_outputs.values():
        for metric in group["metrics"]:
            metric["unit"] = units.get(metric["key"], "")
            metric["normalized_score"] = metric.get("score_0_100")
            metric["record_count"] = metric.get("sample_count", 0)
    return group_outputs


def _sanitize_feedback_for_report(text, employee_names):
    cleaned = text or ""
    for name in sorted((item for item in employee_names if item), key=len, reverse=True):
        cleaned = re.sub(re.escape(name), "[PERSON]", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", "[EMAIL]", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"(?<!\w)(?:\+?\d[\d .()/-]{7,}\d)(?!\w)", "[PHONE_OR_ID]", cleaned)
    cleaned = re.sub(r"\b(?:account|acct|customer|client|loan)\s*(?:no\.?|number|id|#)?\s*[:#-]?\s*[A-Z0-9-]{5,}\b", "[REDACTED_REFERENCE]", cleaned, flags=re.IGNORECASE)
    return cleaned[:1200]


@app.get("/api/v1/reporting/employees")
def get_reportable_employees(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    role = current_user.get("role")
    if role == "employee":
        rows = db.query(models.Employee).filter_by(employee_id=current_user["employee_id"], is_active=True).all()
    elif role == "supervisor":
        rows = db.query(models.Employee).filter_by(supervisor_id=current_user["user_id"], user_type="employee", is_active=True).order_by(models.Employee.full_name).all()
    elif role == "executive":
        rows = db.query(models.Employee).join(
            models.ImmediateSupervisor, models.Employee.supervisor_id == models.ImmediateSupervisor.supervisor_id
        ).filter(models.ImmediateSupervisor.executive_id == current_user["user_id"],
                 models.Employee.user_type == "employee", models.Employee.is_active.is_(True)).order_by(models.Employee.full_name).all()
    else:
        raise HTTPException(status_code=403, detail="This account cannot generate performance reports")
    return [{"employee_id": row.employee_id, "full_name": row.full_name, "role": row.role} for row in rows]


@app.get("/api/v1/ai-reports/{employee_id}")
def list_ai_reports(employee_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    employee = db.query(models.Employee).filter_by(employee_id=employee_id, is_active=True).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    ensure_employee_access(db, current_user, employee)
    rows = db.query(models.AIPerformanceReport).filter_by(employee_id=employee_id).order_by(
        models.AIPerformanceReport.generated_at.desc()
    ).limit(30).all()
    return [_serialize_ai_report(row) for row in rows]


def _serialize_ai_report(row):
    return {"report_id": row.report_id, "employee_id": row.employee_id,
            "period_type": row.period_type, "period_code": row.period_code,
            "period_start": row.period_start, "period_end": row.period_end,
            "telemetry_groups": row.telemetry_groups, "feedback_dimensions": row.feedback_dimensions,
            "narrative": row.narrative, "data_coverage": row.data_coverage,
            "report_status": row.report_status, "model_name": row.model_name,
            "generated_at": row.generated_at}


@app.post("/api/v1/ai-reports/generate")
def generate_ai_performance_report(payload: AIReportGenerateRequest, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    employee = db.query(models.Employee).filter_by(employee_id=payload.employee_id, is_active=True).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    ensure_employee_access(db, current_user, employee)
    start, end, period_code = _report_period(payload)
    records = db.query(models.PerformanceRecord).filter(
        models.PerformanceRecord.employee_id == employee.employee_id,
        models.PerformanceRecord.recorded_at >= start,
        models.PerformanceRecord.recorded_at < end,
    ).order_by(models.PerformanceRecord.recorded_at.asc()).all()

    classifications, appraisals, _ = get_period_classifications(
        db, employee.employee_id, start, end
    )
    classifier_rows = [
        row for row in classifications
        if row.review_status == "auto_classified"
    ]

    # Do not generate a report from stale or missing classifications. Each
    # supervisor form in the selected period must be covered by a current run.
    overlapping_runs = db.query(models.TrustScoreRun).filter(
        models.TrustScoreRun.employee_id == employee.employee_id,
        models.TrustScoreRun.period_start < end,
        models.TrustScoreRun.period_end > start,
    ).all()
    current_run_ids = set()
    for trust_run in overlapping_runs:
        actual_form_count = db.query(func.count(models.SupervisorAppraisal.appraisal_id)).filter(
            models.SupervisorAppraisal.employee_id == employee.employee_id,
            models.SupervisorAppraisal.created_at >= trust_run.period_start,
            models.SupervisorAppraisal.created_at < trust_run.period_end,
        ).scalar() or 0
        saved_form_count = int((trust_run.data_coverage or {}).get("supervisor_form_count") or 0)
        if saved_form_count == actual_form_count:
            current_run_ids.add(trust_run.run_id)

    unprocessed_appraisals = [
        appraisal for appraisal in appraisals
        if not any(
            trust_run.run_id in current_run_ids
            and trust_run.period_start <= appraisal.created_at < trust_run.period_end
            for trust_run in overlapping_runs
        )
    ]
    if unprocessed_appraisals:
        raise HTTPException(
            status_code=422,
            detail="Run automatic classification for every supervisor appraisal in this period before generating the report.",
        )
    if not records and not classifier_rows:
        raise HTTPException(
            status_code=422,
            detail="No telemetry or supervisor-classified evidence exists for that report period.",
        )

    telemetry_groups = _build_report_telemetry(records)
    feedback_groups, _ = build_feedback_groups(classifier_rows)
    all_names = [
        row[0] for row in db.query(models.Employee.full_name).all()
    ]

    # Include only supervisor answers already assigned by the competency model.
    # Employee self-follow-ups are deliberately excluded from reports and scores.
    supervisor_evidence = {}
    for dimension in REPORT_DIMENSIONS:
        group_rows = [row for row in classifier_rows if row.category == dimension]
        supervisor_evidence[dimension] = {
            "score_0_100": feedback_groups[dimension]["score_0_100"],
            "positive_count": feedback_groups[dimension]["positive_count"],
            "negative_count": feedback_groups[dimension]["negative_count"],
            "mixed_or_neutral_count": feedback_groups[dimension]["mixed_or_neutral_count"],
            "classification_count": feedback_groups[dimension]["classification_count"],
            "evidence": [
                {
                    "direction": row.predicted_direction,
                    "statement": _sanitize_feedback_for_report(row.statement_text, all_names)[:500],
                }
                for row in group_rows[:25]
            ],
            "evidence_truncated": max(0, len(group_rows) - 25),
        }

    feedback_answer_keys = {
        (row.supervisor_appraisal_id, row.item_key)
        for row in classifier_rows
    }
    supervisor_answer_count = sum(
        1
        for appraisal in appraisals
        for answer in (
            appraisal.answers_snapshot
            if isinstance(appraisal.answers_snapshot, list)
            else []
        )
        if isinstance(answer, dict)
        and isinstance(answer.get("answer"), str)
        and answer["answer"].strip()
    )
    narrative, normalized_dimensions = build_local_report(
        period_type=payload.period_type,
        period_code=period_code,
        telemetry_groups=telemetry_groups,
        feedback_groups=feedback_groups,
        supervisor_evidence=supervisor_evidence,
        coverage={
            "telemetry_records": len(records),
            "telemetry_months": len({record.recorded_at.strftime("%Y-%m") for record in records}),
            "supervisor_forms": len(appraisals),
            "supervisor_answers": supervisor_answer_count,
            "classified_answer_category_assignments": len(classifier_rows),
            "distinct_classified_answers": len(feedback_answer_keys),
        },
    )

    sources = sorted({record.data_source or "unknown" for record in records})
    data_coverage = {
        "telemetry_record_count": len(records),
        "telemetry_months_covered": len({record.recorded_at.strftime("%Y-%m") for record in records}),
        "data_sources": sources,
        "supervisor_form_count": len(appraisals),
        "supervisor_answer_count": supervisor_answer_count,
        "classified_answer_count": len(feedback_answer_keys),
        "classified_answer_category_count": len(classifier_rows),
        "feedback_item_count": len(classifier_rows),
        "feedback_data_sources": ["supervisor_appraisal_classifier"] if classifier_rows else [],
        "feedback_score_source": "supervisor_appraisal_classifier",
        "employee_followups_included": False,
        "feedback_ratings_are_human_reviewed": False,
        "report_generation_method": "local_templates_v1",
    }
    report = models.AIPerformanceReport(
        employee_id=employee.employee_id,
        generated_by_employee_id=current_user["employee_id"],
        period_type=payload.period_type,
        period_code=period_code,
        period_start=start,
        period_end=end,
        telemetry_groups=telemetry_groups,
        feedback_dimensions=normalized_dimensions,
        narrative=narrative,
        data_coverage=data_coverage,
        report_status="ai_draft",
        model_name="local_templates_v1",
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return _serialize_ai_report(report)

@app.post("/api/v1/coaching/chat")
def coaching_chat(
    payload: CoachingChatRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") != "employee":
        raise HTTPException(status_code=403, detail="Only employees can use the coaching chat")
    if payload.topic not in COACHING_TOPICS:
        raise HTTPException(status_code=422, detail="Choose one of the available coaching topics")
    if not payload.messages or len(payload.messages) > 12:
        raise HTTPException(status_code=422, detail="Send between one and twelve recent chat messages")
    if payload.messages[-1].role != "user":
        raise HTTPException(status_code=422, detail="The latest chat message must be from you")
    if any(not message.content.strip() or len(message.content) > 2000 for message in payload.messages):
        raise HTTPException(status_code=422, detail="Each message must contain 1 to 2,000 characters")

    employee = db.query(models.Employee).filter(
        models.Employee.employee_id == current_user["employee_id"],
        models.Employee.is_active.is_(True),
    ).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee account not found")

    latest_message = payload.messages[-1].content.lower()
    urgent_phrases = ("suicid", "kill myself", "end my life", "hurt myself", "self-harm", "self harm")
    if any(phrase in latest_message for phrase in urgent_phrases):
        return {
            "reply": (
                "I’m sorry you’re facing this. I’m a work-coaching tool, not emergency or clinical support. "
                "If you may be in immediate danger, contact local emergency services now and reach out to "
                "someone you trust who can stay with you. You can also contact a qualified health professional "
                "or your organization’s wellbeing support."
            ),
            "topic": payload.topic,
        }

    if payload.topic == "compliance":
        return {
            "reply": (
                "I can help you think through a compliance concern in general terms, but your organization’s "
                "approved policies and procedures are not connected to this coach yet. Please check the current "
                "policy or contact your Compliance team before acting. Avoid sharing customer, account, or other "
                "confidential details here. If you describe the situation without identifying details, I can help "
                "you prepare questions to ask."
            ),
            "topic": payload.topic,
        }

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="The coaching service is not configured yet. Add OPENAI_API_KEY to the backend .env file.",
        )

    latest_record = db.query(models.PerformanceRecord).filter_by(
        employee_id=employee.employee_id
    ).order_by(models.PerformanceRecord.recorded_at.desc()).first()
    latest_report = db.query(models.AppraisalReport).filter_by(
        employee_id=employee.employee_id
    ).order_by(models.AppraisalReport.generation_date.desc()).first()
    supervisor_profile = db.query(models.ImmediateSupervisor).filter_by(
        supervisor_id=employee.supervisor_id
    ).first() if employee.supervisor_id is not None else None
    employee_context = {
        "employee": employee.full_name,
        "role": employee.role,
        "department": employee.department,
        "supervisor": supervisor_profile.full_name if supervisor_profile else None,
        "branch": employee.branch_location,
        "latest_trust_score": latest_report.unified_trust_score if latest_report else None,
        "latest_score_date": latest_report.generation_date.isoformat() if latest_report else None,
        "latest_telemetry": [
            {"metric": metric["label"], "value": _metric_value(latest_record, metric),
             "unit": metric["unit"], "state": _metric_status(latest_record, metric)}
            for metric in QUESTION_METRICS
        ] if latest_record else [],
        "schedule_data_available": False,
    }

    instructions = (
        "You are a supportive workplace learning coach for a bank employee. "
        f"The employee chose this topic: {COACHING_TOPICS[payload.topic]}. "
        f"Their stated role is {employee.role!r} in the {employee.department!r} department. "
        f"Verified profile, latest score, and telemetry context: {json.dumps(employee_context, ensure_ascii=False)}. "
        "Give practical, respectful coaching that helps the employee build skills and make their own decisions. "
        "Use plain language, suggest a small number of concrete next steps, and ask at most one useful follow-up question. "
        "Do not estimate, predict, or try to improve an employee score; do not make hiring, promotion, discipline, or other employment decisions. "
        "If asked about a schedule, say no schedule data is currently connected. Do not invent a score, supervisor, telemetry value, or schedule. "
        "Treat KPI colors as demonstration bands and scores as historical information, not employment decisions or predictions. "
        "Do not infer burnout, mental health, character, or causes from metrics. "
        "Do not claim knowledge of the bank's internal policy. For specific policy or legal questions, direct the employee to approved policy material or Compliance. "
        "For stress or burnout, be empathetic, do not diagnose or replace professional care, and suggest appropriate human support when needed. "
        "Do not request or repeat customer identifiers, account details, passwords, or other confidential information."
    )
    client = OpenAI(api_key=api_key)
    try:
        response = client.responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-6-luna"),
            instructions=instructions,
            input=[
                {"role": message.role, "content": message.content.strip()}
                for message in payload.messages[-12:]
            ],
            max_output_tokens=500,
            store=False,
        )
    except OpenAIError:
        raise HTTPException(status_code=502, detail="The coaching service could not answer right now. Please try again shortly")

    reply = response.output_text.strip()
    if not reply:
        raise HTTPException(status_code=502, detail="The coaching service returned an empty response")
    return {"reply": reply, "topic": payload.topic}

@app.get("/api/v1/supervisors/{supervisor_id}/appraisal-template")
def get_supervisor_appraisal_template(
    supervisor_id: int,
    employee_id: Optional[int] = None,
    form_number: Optional[int] = None,
    appraisal_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    ensure_supervisor_access(db, current_user, supervisor_id)
    if current_user.get("role") != "supervisor":
        raise HTTPException(status_code=403, detail="Only the assigned supervisor can issue this appraisal")
    calendar_period = current_review_period()
    if employee_id is None:
        # Reopening a submitted appraisal for its one-time revision.
        if appraisal_id is not None:
            record = db.query(models.SupervisorAppraisal).filter_by(
                appraisal_id=appraisal_id, supervisor_id=supervisor_id
            ).first()
            if not record:
                raise HTTPException(status_code=404, detail="Supervisor appraisal not found")
            stored_questions = [
                {key: value for key, value in item.items() if key != "answer"}
                for item in (record.answers_snapshot or [])
            ]
            if any(item.get("type") == "yes_no" for item in stored_questions):
                # Existing legacy forms remain viewable, while their one-time
                # revision uses the current open-ended form for that half-year.
                stored_questions = SUPERVISOR_APPRAISAL_QUESTIONS_BY_FORM[record.form_number]
            if stored_questions:
                return {"period_code": record.period_code, "form_number": record.form_number,
                        "complete": False, "questions": stored_questions}
        revision_form = form_number or 1
        questions = SUPERVISOR_APPRAISAL_QUESTIONS_BY_FORM.get(revision_form)
        if questions is None:
            raise HTTPException(status_code=422, detail="Form number must be 1 or 2")
        return {"period_code": calendar_period, "form_number": revision_form,
                "complete": False, "questions": questions}

    employee = db.query(models.Employee).filter_by(
        employee_id=employee_id, supervisor_id=supervisor_id
    ).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee is not assigned to this supervisor")

    if calendar_period.endswith("-H1"):
        form_period = calendar_period
        active_form_number = 1
        overdue_first_form = False
    else:
        first_half_period = f"{calendar_period[:4]}-H1"
        first_form = db.query(models.SupervisorAppraisal).filter_by(
            employee_id=employee_id, supervisor_id=supervisor_id,
            period_code=first_half_period, form_number=1,
        ).first()
        if first_form:
            form_period = calendar_period
            active_form_number = 2
            overdue_first_form = False
        else:
            # Permit a late first-half entry, then the second-half form can follow.
            form_period = first_half_period
            active_form_number = 1
            overdue_first_form = True

    questions = SUPERVISOR_APPRAISAL_QUESTIONS_BY_FORM[active_form_number]
    existing = db.query(models.SupervisorAppraisal).filter_by(
        employee_id=employee_id, supervisor_id=supervisor_id,
        period_code=form_period, form_number=active_form_number,
    ).first()
    if existing:
        return {"period_code": form_period, "form_number": active_form_number,
                "complete": True, "questions": []}
    return {"period_code": form_period, "form_number": active_form_number,
            "complete": False, "overdue_first_form": overdue_first_form,
            "message": ("Complete the first-half Form 1 to unlock Form 2."
                        if overdue_first_form else None),
            "questions": questions}


@app.post("/api/v1/supervisors/{supervisor_id}/appraisals")
def submit_supervisor_appraisal(
    supervisor_id: int,
    payload: schemas.SupervisorAppraisalSubmission,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    ensure_supervisor_access(db, current_user, supervisor_id)
    if current_user.get("role") != "supervisor":
        raise HTTPException(status_code=403, detail="Only the assigned supervisor can submit this appraisal")
    employee = db.query(models.Employee).filter_by(
        employee_id=payload.employee_id, supervisor_id=supervisor_id
    ).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee is not assigned to this supervisor")
    calendar_period = current_review_period()
    if calendar_period.endswith("-H1"):
        period_code = calendar_period
        active_form_number = 1
    else:
        first_half_period = f"{calendar_period[:4]}-H1"
        first_form = db.query(models.SupervisorAppraisal).filter_by(
            employee_id=employee.employee_id, supervisor_id=supervisor_id,
            period_code=first_half_period, form_number=1,
        ).first()
        if first_form:
            period_code = calendar_period
            active_form_number = 2
        else:
            period_code = first_half_period
            active_form_number = 1

    form_number = payload.form_number
    if form_number != active_form_number:
        raise HTTPException(status_code=409, detail=(
            f"Form {form_number} is not active for this employee right now. "
            f"Complete Form {active_form_number} for {period_code} first. "
            "Form 2 is only available from July onward."
        ))
    questions = SUPERVISOR_APPRAISAL_QUESTIONS_BY_FORM[form_number]
    if db.query(models.SupervisorAppraisal).filter_by(
        employee_id=employee.employee_id, supervisor_id=supervisor_id,
        period_code=period_code, form_number=form_number,
    ).first():
        raise HTTPException(status_code=409, detail=f"Form {form_number} is already submitted for this employee in this review period")
    if len(payload.answers) != len(questions):
        raise HTTPException(status_code=422, detail=f"The semiannual form requires exactly {len(questions)} answers")
    answers_by_id = {answer.get("question_id"): answer.get("answer") for answer in payload.answers}
    expected_ids = {question["id"] for question in questions}
    if set(answers_by_id) != expected_ids:
        raise HTTPException(status_code=422, detail="The form answers do not match the current appraisal questions")
    snapshot = []
    yes_count = 0
    for question in questions:
        answer = answers_by_id[question["id"]]
        if not isinstance(answer, str) or len(answer.strip()) < 10 or len(answer) > 3000:
            raise HTTPException(status_code=422, detail="Each open response must contain 10 to 3,000 characters")
        answer = answer.strip()
        snapshot.append({**question, "answer": answer})
    record = models.SupervisorAppraisal(
        employee_id=employee.employee_id,
        supervisor_id=supervisor_id,
        period_code=period_code,
        form_number=form_number,
        answers_snapshot=snapshot,
        yes_count=yes_count,
    )
    try:
        db.add(record)
        db.commit()
        db.refresh(record)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Form {form_number} is already submitted for this employee in this half-year period")
    return {"appraisal_id": record.appraisal_id, "employee_id": record.employee_id,
            "period_code": record.period_code, "form_number": record.form_number,
            "yes_count": record.yes_count,
            "employee_notified_at": record.employee_notified_at,
            "message": (("Form 1 is saved for the first half. Form 2 is now available for the second half."
                         if calendar_period.endswith("-H2") else
                         "Form 1 is saved. Form 2 becomes available on July 1.")
                        if form_number == 1 else
                        "Form 2 is saved and available in the employee dashboard.")}


def _meeting_summary(db: Session, appraisal_id: int):
    meeting = db.query(models.AppraisalMeeting).filter_by(appraisal_id=appraisal_id).first()
    if not meeting:
        return None
    return {
        "meeting_id": meeting.meeting_id,
        "scheduled_at": meeting.scheduled_at,
        "status": meeting.status,
        "confirmed_at": meeting.confirmed_at,
    }


def _enforce_supervisor_meeting_spacing(db: Session, supervisor_id: int, scheduled_at: datetime) -> None:
    # Lock the supervisor row so simultaneous booking requests for this supervisor
    # cannot both pass the spacing check before either one commits.
    supervisor = db.query(models.ImmediateSupervisor).filter_by(
        supervisor_id=supervisor_id
    ).with_for_update().first()
    if not supervisor:
        raise HTTPException(status_code=404, detail="Supervisor not found")

    minimum_gap = timedelta(minutes=30)
    conflict = db.query(models.AppraisalMeeting).filter(
        models.AppraisalMeeting.supervisor_id == supervisor_id,
        models.AppraisalMeeting.scheduled_at > scheduled_at - minimum_gap,
        models.AppraisalMeeting.scheduled_at < scheduled_at + minimum_gap,
    ).first()
    if conflict:
        raise HTTPException(
            status_code=409,
            detail="This supervisor already has a meeting within 30 minutes of that time. Choose a slot at least 30 minutes before or after it.",
        )


def _pdf_literal(value: str) -> bytes:
    safe = str(value).encode("cp1252", errors="replace").decode("cp1252")
    safe = "".join(char if char >= " " else " " for char in safe)
    return safe.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)").encode("cp1252")


def _simple_text_pdf(lines):
    page_lines = [lines[index:index + 48] for index in range(0, len(lines), 48)] or [[]]
    objects = [None, b"<< /Type /Catalog /Pages 2 0 R >>", None,
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"]
    page_refs = []
    page_data = []
    for page_index, content_lines in enumerate(page_lines):
        page_obj_id = 4 + page_index * 2
        content_obj_id = page_obj_id + 1
        page_refs.append(f"{page_obj_id} 0 R".encode("ascii"))
        stream = bytearray(b"BT\n/F1 10 Tf\n14 TL\n52 748 Td\n")
        for line in content_lines:
            stream.extend(b"(")
            stream.extend(_pdf_literal(line))
            stream.extend(b") Tj\nT*\n")
        stream.extend(b"ET")
        page_data.append((page_obj_id, content_obj_id, bytes(stream)))
    objects[2] = b"<< /Type /Pages /Kids [" + b" ".join(page_refs) + b"] /Count " + str(len(page_lines)).encode("ascii") + b" >>"
    for page_obj_id, content_obj_id, stream in page_data:
        objects.extend([None] * max(0, content_obj_id + 1 - len(objects)))
        objects[page_obj_id] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_obj_id} 0 R >>"
        ).encode("ascii")
        objects[content_obj_id] = (
            b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream"
        )
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for object_id in range(1, len(objects)):
        offsets.append(len(pdf))
        pdf.extend(f"{object_id} 0 obj\n".encode("ascii"))
        pdf.extend(objects[object_id])
        pdf.extend(b"\nendobj\n")
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects)}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(f"trailer\n<< /Size {len(objects)} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF".encode("ascii"))
    return bytes(pdf)


@app.get("/api/v1/supervisors/{supervisor_id}/appraisals")
def get_supervisor_appraisals(
    supervisor_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    ensure_supervisor_access(db, current_user, supervisor_id)
    rows = db.query(models.SupervisorAppraisal, models.Employee.full_name).join(
        models.Employee, models.Employee.employee_id == models.SupervisorAppraisal.employee_id
    ).filter(models.SupervisorAppraisal.supervisor_id == supervisor_id).order_by(
        models.SupervisorAppraisal.created_at.desc()
    ).all()
    appraisal_ids = [row.appraisal_id for row, _ in rows]
    followups_by_appraisal = {}
    if appraisal_ids:
        followups = db.query(models.UnstructuredFeedback).filter(
            models.UnstructuredFeedback.supervisor_appraisal_id.in_(appraisal_ids),
            models.UnstructuredFeedback.author_employee_id == models.UnstructuredFeedback.employee_id,
        ).order_by(models.UnstructuredFeedback.created_at.desc()).all()
        for feedback in followups:
            followups_by_appraisal.setdefault(feedback.supervisor_appraisal_id, feedback)
    return [{"appraisal_id": row.appraisal_id, "employee_id": row.employee_id,
             "employee_name": full_name, "period_code": row.period_code, "form_number": row.form_number,
              "answers": row.answers_snapshot, "yes_count": row.yes_count,
              "question_count": len(row.answers_snapshot or []),
             "employee_followup": ({
                 "feedback_id": followups_by_appraisal[row.appraisal_id].feedback_id,
                 "submitted_at": followups_by_appraisal[row.appraisal_id].created_at,
                 "answers": followups_by_appraisal[row.appraisal_id].question_snapshot,
             } if row.appraisal_id in followups_by_appraisal else None),
             "review_request_text": row.review_request_text,
             "review_requested_at": row.review_requested_at,
             "review_edit_count": row.review_edit_count,
             "satisfied_at": row.satisfied_at,
             "status": "satisfied" if row.satisfied_at else ("review_requested" if row.review_requested_at and row.review_edit_count == 0 else ("reviewed" if row.review_edit_count else "awaiting_employee")),
             "meeting": _meeting_summary(db, row.appraisal_id),
             "created_at": row.created_at} for row, full_name in rows]


@app.post("/api/v1/supervisors/{supervisor_id}/appraisals/{appraisal_id}/meetings")
def schedule_appraisal_meeting(
    supervisor_id: int,
    appraisal_id: int,
    payload: schemas.ScheduleAppraisalMeeting,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    ensure_supervisor_access(db, current_user, supervisor_id)
    if current_user.get("role") != "supervisor":
        raise HTTPException(status_code=403, detail="Only the assigned supervisor can schedule this meeting")
    appraisal = db.query(models.SupervisorAppraisal).filter_by(
        appraisal_id=appraisal_id, supervisor_id=supervisor_id
    ).first()
    if not appraisal:
        raise HTTPException(status_code=404, detail="Supervisor appraisal not found")
    if appraisal.satisfied_at:
        raise HTTPException(status_code=409, detail="This appraisal is closed")
    if db.query(models.AppraisalMeeting).filter_by(appraisal_id=appraisal_id).first():
        raise HTTPException(status_code=409, detail="A meeting is already booked for this appraisal")
    scheduled_at = payload.scheduled_at
    if scheduled_at.tzinfo is None:
        scheduled_at = scheduled_at.replace(tzinfo=ZoneInfo("Africa/Nairobi"))
    if scheduled_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=422, detail="Choose a future meeting date and time")
    _enforce_supervisor_meeting_spacing(db, supervisor_id, scheduled_at)
    meeting = models.AppraisalMeeting(
        appraisal_id=appraisal.appraisal_id,
        employee_id=appraisal.employee_id,
        supervisor_id=supervisor_id,
        scheduled_at=scheduled_at,
    )
    db.add(meeting)
    try:
        db.commit()
        db.refresh(meeting)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A meeting is already booked for this appraisal")
    return {"meeting_id": meeting.meeting_id, "status": meeting.status,
            "scheduled_at": meeting.scheduled_at,
            "message": "Meeting booked and shown in the employee appraisal section for confirmation."}


@app.post("/api/v1/supervisors/{supervisor_id}/employees/{employee_id}/meetings")
def schedule_employee_meeting(
    supervisor_id: int,
    employee_id: int,
    payload: schemas.ScheduleAppraisalMeeting,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    ensure_supervisor_access(db, current_user, supervisor_id)
    if current_user.get("role") != "supervisor":
        raise HTTPException(status_code=403, detail="Only the assigned supervisor can schedule this meeting")
    employee = db.query(models.Employee).filter_by(
        employee_id=employee_id, supervisor_id=supervisor_id
    ).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee is not assigned to this supervisor")
    scheduled_at = payload.scheduled_at
    if scheduled_at.tzinfo is None:
        scheduled_at = scheduled_at.replace(tzinfo=ZoneInfo("Africa/Nairobi"))
    if scheduled_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=422, detail="Choose a future meeting date and time")
    _enforce_supervisor_meeting_spacing(db, supervisor_id, scheduled_at)
    meeting = models.AppraisalMeeting(
        appraisal_id=None,
        employee_id=employee_id,
        supervisor_id=supervisor_id,
        scheduled_at=scheduled_at,
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    return {"meeting_id": meeting.meeting_id, "status": meeting.status,
            "scheduled_at": meeting.scheduled_at,
            "message": "Meeting booked and shown in the employee’s appraisal section for confirmation."}


@app.post("/api/v1/employees/{employee_id}/appraisal-meetings/{meeting_id}/confirm")
def confirm_appraisal_meeting(
    employee_id: int,
    meeting_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") != "employee" or current_user.get("employee_id") != employee_id:
        raise HTTPException(status_code=403, detail="Only the employee booked for this meeting can confirm it")
    meeting = db.query(models.AppraisalMeeting).filter_by(
        meeting_id=meeting_id, employee_id=employee_id
    ).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting booking not found")
    if meeting.status != "confirmed":
        meeting.status = "confirmed"
        meeting.confirmed_at = datetime.now(timezone.utc)
        db.commit()
    return {"status": meeting.status, "message": "Meeting confirmed. Your supervisor can see your confirmation in their meetings list."}


@app.get("/api/v1/supervisors/{supervisor_id}/meetings")
def get_supervisor_appraisal_meetings(
    supervisor_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    ensure_supervisor_access(db, current_user, supervisor_id)
    rows = db.query(models.AppraisalMeeting, models.Employee.full_name,
                    models.SupervisorAppraisal.period_code).join(
        models.Employee, models.Employee.employee_id == models.AppraisalMeeting.employee_id
    ).outerjoin(
        models.SupervisorAppraisal, models.SupervisorAppraisal.appraisal_id == models.AppraisalMeeting.appraisal_id
    ).filter(models.AppraisalMeeting.supervisor_id == supervisor_id).order_by(
        models.AppraisalMeeting.scheduled_at.asc()
    ).all()
    return [{"meeting_id": meeting.meeting_id, "appraisal_id": meeting.appraisal_id,
             "employee_id": meeting.employee_id, "employee_name": employee_name,
             "period_code": period_code,
             "meeting_type": "appraisal" if meeting.appraisal_id else "check_in",
             "scheduled_at": meeting.scheduled_at,
             "status": meeting.status, "confirmed_at": meeting.confirmed_at}
            for meeting, employee_name, period_code in rows]


@app.get("/api/v1/employees/{employee_id}/appraisal-meetings")
def get_employee_appraisal_meetings(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") != "employee" or current_user.get("employee_id") != employee_id:
        raise HTTPException(status_code=403, detail="Access denied")
    rows = db.query(models.AppraisalMeeting, models.SupervisorAppraisal.period_code).outerjoin(
        models.SupervisorAppraisal,
        models.SupervisorAppraisal.appraisal_id == models.AppraisalMeeting.appraisal_id,
    ).filter(models.AppraisalMeeting.employee_id == employee_id).order_by(
        models.AppraisalMeeting.scheduled_at.asc()
    ).all()
    return [{"meeting_id": meeting.meeting_id, "appraisal_id": meeting.appraisal_id,
             "employee_id": meeting.employee_id, "supervisor_id": meeting.supervisor_id,
             "period_code": period_code, "meeting_type": "appraisal" if meeting.appraisal_id else "check_in",
             "scheduled_at": meeting.scheduled_at, "status": meeting.status,
             "confirmed_at": meeting.confirmed_at}
            for meeting, period_code in rows]


@app.get("/api/v1/executives/{executive_id}/supervisors/{supervisor_id}/appraisals")
def get_executive_supervisor_appraisals(
    executive_id: int,
    supervisor_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") != "executive" or current_user.get("user_id") != executive_id:
        raise HTTPException(status_code=403, detail="Access denied")
    supervisor = db.query(models.ImmediateSupervisor).filter_by(
        supervisor_id=supervisor_id, executive_id=executive_id
    ).first()
    if not supervisor:
        raise HTTPException(status_code=404, detail="Supervisor not found in this executive's region")
    rows = db.query(models.SupervisorAppraisal, models.Employee.full_name).join(
        models.Employee, models.Employee.employee_id == models.SupervisorAppraisal.employee_id
    ).filter(models.SupervisorAppraisal.supervisor_id == supervisor_id).order_by(
        models.SupervisorAppraisal.created_at.desc()
    ).all()
    return [{"appraisal_id": row.appraisal_id, "employee_id": row.employee_id,
             "employee_name": employee_name, "period_code": row.period_code, "form_number": row.form_number,
              "answers": row.answers_snapshot, "yes_count": row.yes_count,
              "question_count": len(row.answers_snapshot or []),
             "review_request_text": row.review_request_text,
             "review_requested_at": row.review_requested_at,
             "review_edit_count": row.review_edit_count,
             "satisfied_at": row.satisfied_at,
             "meeting": _meeting_summary(db, row.appraisal_id),
             "created_at": row.created_at}
            for row, employee_name in rows]


@app.get("/api/v1/supervisor-appraisals/{appraisal_id}/download")
def download_supervisor_appraisal(
    appraisal_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    record = db.query(models.SupervisorAppraisal).filter_by(appraisal_id=appraisal_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Supervisor appraisal not found")
    role = current_user.get("role")
    employee = db.query(models.Employee).filter_by(employee_id=record.employee_id).first()
    allowed = role == "employee" and current_user.get("employee_id") == record.employee_id
    if role == "supervisor":
        allowed = current_user.get("user_id") == record.supervisor_id
    elif role == "executive":
        allowed = db.query(models.ImmediateSupervisor).filter_by(
            supervisor_id=record.supervisor_id,
            executive_id=current_user.get("user_id"),
        ).first() is not None
    if not allowed:
        raise HTTPException(status_code=403, detail="You do not have access to this appraisal")
    supervisor = db.query(models.ImmediateSupervisor).filter_by(
        supervisor_id=record.supervisor_id
    ).first()
    supervisor_employee = db.query(models.Employee).filter_by(
        employee_id=supervisor.emp_id
    ).first() if supervisor else None
    lines = [
        "TrustScoreAI - Semiannual Supervisor Appraisal",
        "",
        f"Employee: {employee.full_name if employee else 'Unknown'} (ID {record.employee_id})",
        f"Supervisor: {supervisor_employee.full_name if supervisor_employee else 'Unknown'} (ID {record.supervisor_id})",
        f"Review period: {record.period_code}",
        f"Form: {record.form_number} of 2",
        f"Submitted: {record.created_at.strftime('%Y-%m-%d %H:%M UTC') if record.created_at else 'Unknown'}",
        f"Questions answered: {len(record.answers_snapshot or [])}",
        f"Employee status: {'Satisfied and closed' if record.satisfied_at else 'Review requested' if record.review_requested_at and record.review_edit_count == 0 else 'Revised once' if record.review_edit_count else 'Awaiting employee response'}",
        "",
        "APPRAISAL QUESTIONS AND ANSWERS",
        "",
    ]
    previous_category = None
    for index, answer in enumerate(record.answers_snapshot or [], start=1):
        category = answer.get("category") or "General"
        if category != previous_category:
            lines.extend(["", category.replace("_", " ").title(), ""])
            previous_category = category
        response_value = str(answer.get("answer", ""))
        lines.extend(textwrap.wrap(f"{index}. {answer.get('prompt', '')}", width=92) or [f"{index}."])
        lines.extend(textwrap.wrap("Answer: " + response_value, width=92))
        lines.append("")
    if record.review_request_text:
        lines.extend(["EMPLOYEE REVIEW REQUEST", ""])
        lines.extend(textwrap.wrap(record.review_request_text, width=92))
        lines.append("")
    meeting = db.query(models.AppraisalMeeting).filter_by(appraisal_id=appraisal_id).first()
    if meeting:
        lines.extend(["MEETING", f"Scheduled: {meeting.scheduled_at.isoformat()}",
                      f"Employee confirmation: {meeting.status}"])
    pdf = _simple_text_pdf(lines)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="supervisor-appraisal-{appraisal_id}.pdf"'},
    )


@app.get("/api/v1/employees/{employee_id}/supervisor-appraisals")
def get_employee_supervisor_appraisals(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") != "employee" or current_user.get("employee_id") != employee_id:
        raise HTTPException(status_code=403, detail="Only the matching base employee account can access these appraisals")
    rows = db.query(models.SupervisorAppraisal).filter_by(employee_id=employee_id).order_by(
        models.SupervisorAppraisal.created_at.desc()
    ).all()
    feedback_rows = db.query(models.UnstructuredFeedback.supervisor_appraisal_id,
                              models.UnstructuredFeedback.feedback_id,
                              models.UnstructuredFeedback.created_at).filter(
        models.UnstructuredFeedback.supervisor_appraisal_id.in_([row.appraisal_id for row in rows]),
        models.UnstructuredFeedback.author_employee_id == employee_id,
    ).all() if rows else []
    feedback_by_appraisal = {appraisal_id: (feedback_id, created_at)
                             for appraisal_id, feedback_id, created_at in feedback_rows}
    return [{"appraisal_id": row.appraisal_id, "period_code": row.period_code,
             "form_number": row.form_number, "answers": row.answers_snapshot, "yes_count": row.yes_count,
             "question_count": len(row.answers_snapshot or []),
             "self_questionnaire_submitted": row.appraisal_id in feedback_by_appraisal,
             "self_questionnaire_feedback_id": feedback_by_appraisal.get(row.appraisal_id, (None, None))[0],
             "self_questionnaire_submitted_at": feedback_by_appraisal.get(row.appraisal_id, (None, None))[1],
             "employee_notified_at": row.employee_notified_at,
             "review_request_text": row.review_request_text,
             "review_requested_at": row.review_requested_at,
             "review_edit_count": row.review_edit_count,
             "satisfied_at": row.satisfied_at,
             "status": "satisfied" if row.satisfied_at else ("review_requested" if row.review_requested_at and row.review_edit_count == 0 else ("reviewed" if row.review_edit_count else "awaiting_employee")),
             "meeting": _meeting_summary(db, row.appraisal_id),
             "created_at": row.created_at} for row in rows]


@app.post("/api/v1/employees/{employee_id}/supervisor-appraisals/{appraisal_id}/review-request")
def request_appraisal_clarification(
    employee_id: int,
    appraisal_id: int,
    payload: schemas.ReviewClarificationRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") != "employee" or current_user.get("employee_id") != employee_id:
        raise HTTPException(status_code=403, detail="Only the matching base employee account can access these appraisals")
    message = payload.message.strip()
    if len(message) < 10 or len(message) > 2000:
        raise HTTPException(status_code=422, detail="Please enter 10 to 2,000 characters describing what needs clarification")
    record = db.query(models.SupervisorAppraisal).filter_by(
        appraisal_id=appraisal_id, employee_id=employee_id
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="Supervisor appraisal not found")
    if record.satisfied_at:
        raise HTTPException(status_code=409, detail="This appraisal is closed because you marked it satisfied")
    if record.review_requested_at or record.review_edit_count >= 1:
        raise HTTPException(status_code=409, detail="This appraisal has already used its one review opportunity")
    record.review_request_text = message
    record.review_requested_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "review_requested", "message": "Your one-time review request is now visible to your supervisor."}


@app.post("/api/v1/employees/{employee_id}/supervisor-appraisals/{appraisal_id}/satisfied")
def mark_supervisor_appraisal_satisfied(
    employee_id: int,
    appraisal_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") != "employee" or current_user.get("employee_id") != employee_id:
        raise HTTPException(status_code=403, detail="Only the matching base employee account can access these appraisals")
    record = db.query(models.SupervisorAppraisal).filter_by(appraisal_id=appraisal_id, employee_id=employee_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Supervisor appraisal not found")
    if record.review_requested_at and record.review_edit_count == 0:
        raise HTTPException(status_code=409, detail="Your review request is still awaiting a supervisor response")
    if not record.satisfied_at:
        record.satisfied_at = datetime.now(timezone.utc)
        db.commit()
    return {"status": "satisfied", "message": "Appraisal marked satisfied and closed. It can no longer be changed."}


@app.put("/api/v1/supervisors/{supervisor_id}/appraisals/{appraisal_id}")
def revise_supervisor_appraisal(
    supervisor_id: int,
    appraisal_id: int,
    payload: schemas.SupervisorAppraisalSubmission,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    ensure_supervisor_access(db, current_user, supervisor_id)
    if current_user.get("role") != "supervisor":
        raise HTTPException(status_code=403, detail="Only the assigned supervisor can revise this appraisal")
    record = db.query(models.SupervisorAppraisal).filter_by(appraisal_id=appraisal_id, supervisor_id=supervisor_id).with_for_update().first()
    if not record or record.employee_id != payload.employee_id:
        raise HTTPException(status_code=404, detail="Supervisor appraisal not found")
    if record.satisfied_at:
        raise HTTPException(status_code=409, detail="This appraisal is closed because the employee marked it satisfied")
    if not record.review_requested_at or record.review_edit_count >= 1:
        raise HTTPException(status_code=409, detail="A pending one-time employee review request is required")
    answers_by_id = {answer.get("question_id"): answer.get("answer") for answer in payload.answers}
    revision_questions = [
        {key: value for key, value in item.items() if key != "answer"}
        for item in (record.answers_snapshot or [])
    ] or SUPERVISOR_APPRAISAL_QUESTIONS_BY_FORM[record.form_number]
    if any(item.get("type") == "yes_no" for item in revision_questions):
        revision_questions = SUPERVISOR_APPRAISAL_QUESTIONS_BY_FORM[record.form_number]
    if len(payload.answers) != len(revision_questions):
        raise HTTPException(status_code=422, detail=f"The appraisal revision requires exactly {len(revision_questions)} answers")
    if set(answers_by_id) != {question["id"] for question in revision_questions}:
        raise HTTPException(status_code=422, detail="The form answers do not match the current appraisal questions")
    snapshot = []
    yes_count = 0
    for question in revision_questions:
        answer = answers_by_id[question["id"]]
        if not isinstance(answer, str) or len(answer.strip()) < 10 or len(answer) > 3000:
            raise HTTPException(status_code=422, detail="Each open response must contain 10 to 3,000 characters")
        answer = answer.strip()
        snapshot.append({**question, "answer": answer})
    record.answers_snapshot = snapshot
    record.yes_count = yes_count
    record.review_edit_count = 1
    db.commit()
    return {"status": "reviewed", "form_number": record.form_number, "message": f"Form {record.form_number} was revised once and returned to the employee."}


@app.get("/api/v1/supervisors/{supervisor_id}/team-overview")
def get_supervisor_team_overview(
    supervisor_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    ensure_supervisor_access(db, current_user, supervisor_id)
    employees = db.query(models.Employee).filter_by(supervisor_id=supervisor_id).order_by(
        models.Employee.full_name.asc()
    ).all()
    employee_ids = [employee.employee_id for employee in employees]
    latest_records = {}
    if employee_ids:
        records = db.query(models.PerformanceRecord).filter(
            models.PerformanceRecord.employee_id.in_(employee_ids)
        ).order_by(models.PerformanceRecord.recorded_at.desc()).all()
        for record in records:
            latest_records.setdefault(record.employee_id, record)
    latest_trust_runs = {}
    if employee_ids:
        runs = db.query(models.TrustScoreRun).filter(
            models.TrustScoreRun.employee_id.in_(employee_ids)
        ).order_by(models.TrustScoreRun.generated_at.desc()).all()
        for run in runs:
            latest_trust_runs.setdefault(run.employee_id, run)
    overview = []
    for employee in employees:
        record = latest_records.get(employee.employee_id)
        metrics = []
        if record:
            for metric in QUESTION_METRICS:
                value = _metric_value(record, metric)
                if value is not None:
                    metrics.append({"key": metric["key"], "label": metric["label"],
                                    "value": value, "unit": metric["unit"],
                                    "state": _metric_status(record, metric)})
        trust_run = latest_trust_runs.get(employee.employee_id)
        overview.append({"employee_id": employee.employee_id, "full_name": employee.full_name,
                         "role": employee.role, "recorded_at": record.recorded_at if record else None,
                         "trust_score": trust_run.trust_score if trust_run else None,
                         "trust_score_status": trust_run.score_status if trust_run else "not_generated",
                         "trust_score_period": trust_run.period_code if trust_run else None,
                         "trust_score_generated_at": trust_run.generated_at if trust_run else None,
                         "pending_feedback_review_count": (trust_run.data_coverage or {}).get("pending_review_count", 0) if trust_run else 0,
                         "metrics": metrics})
    aggregate = _aggregate_team_kpis(latest_records, employee_ids)
    return {"period_code": current_review_period(), "employees": overview, "aggregate": aggregate}


class SupervisorCoachingChatRequest(BaseModel):
    messages: List[CoachingMessage]


@app.post("/api/v1/supervisors/{supervisor_id}/coaching/chat")
def supervisor_coaching_chat(
    supervisor_id: int,
    payload: SupervisorCoachingChatRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    ensure_supervisor_access(db, current_user, supervisor_id)
    if current_user.get("role") != "supervisor":
        raise HTTPException(status_code=403, detail="Only a supervisor can use this coaching chat")
    if not payload.messages or len(payload.messages) > 12 or payload.messages[-1].role != "user":
        raise HTTPException(status_code=422, detail="Send up to twelve messages, ending with your question")
    if any(not item.content.strip() or len(item.content) > 2000 for item in payload.messages):
        raise HTTPException(status_code=422, detail="Each chat message must contain 1 to 2,000 characters")
    team = db.query(models.Employee).filter_by(supervisor_id=supervisor_id).all()
    ids = [employee.employee_id for employee in team]
    latest = {}
    if ids:
        for record in db.query(models.PerformanceRecord).filter(
            models.PerformanceRecord.employee_id.in_(ids)
        ).order_by(models.PerformanceRecord.recorded_at.desc()).all():
            latest.setdefault(record.employee_id, record)
    context = []
    for employee in team:
        record = latest.get(employee.employee_id)
        metrics = []
        if record:
            for metric in QUESTION_METRICS:
                value = _metric_value(record, metric)
                if value is not None:
                    metrics.append(f"{metric['label']}: {value:g}{metric['unit']} ({_metric_status(record, metric)})")
        context.append({"employee": employee.full_name, "employee_id": employee.employee_id,
                        "role": employee.role, "latest_telemetry": metrics or ["No telemetry available"]})
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=503, detail="The coaching service is not configured. Add OPENAI_API_KEY to the backend .env file.")
    prompt = (
        "You are a practical, fair coaching assistant for an immediate supervisor. Use only the supplied direct-report data. "
        "When asked about an employee, cite the specific telemetry and its safe/warning/danger state, note missing data, and offer supportive next steps. "
        "Do not infer burnout, mental health, character, intent, or causes from metrics. Encourage a private, respectful conversation to understand context. "
        "Do not make promotion, discipline, termination, or other employment decisions. Do not compare employees as people. "
        "Treat KPI bands as demonstration thresholds rather than bank policy. Protect employee privacy and do not request customer or account data. "
        f"This supervisor's team-only context is: {json.dumps(context, ensure_ascii=False)}"
    )
    try:
        response = OpenAI(api_key=os.getenv("OPENAI_API_KEY")).responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-6-luna"),
            instructions=prompt,
            input=[{"role": item.role, "content": item.content.strip()} for item in payload.messages[-12:]],
            max_output_tokens=500,
            store=False,
        )
    except OpenAIError:
        raise HTTPException(status_code=502, detail="The supervisor coach could not answer right now. Please try again shortly")
    reply = response.output_text.strip()
    if not reply:
        raise HTTPException(status_code=502, detail="The supervisor coach returned an empty response")
    return {"reply": reply}


@app.post("/api/v1/executives/{executive_id}/coaching/chat")
def executive_coaching_chat(
    executive_id: int,
    payload: SupervisorCoachingChatRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") != "executive" or current_user.get("user_id") != executive_id:
        raise HTTPException(status_code=403, detail="Access denied")
    if not payload.messages or len(payload.messages) > 12 or payload.messages[-1].role != "user":
        raise HTTPException(status_code=422, detail="Send up to twelve messages, ending with your question")
    if any(not item.content.strip() or len(item.content) > 2000 for item in payload.messages):
        raise HTTPException(status_code=422, detail="Each chat message must contain 1 to 2,000 characters")
    supervisors = db.query(models.ImmediateSupervisor).filter_by(executive_id=executive_id).all()
    supervisor_ids = [item.supervisor_id for item in supervisors]
    employees = db.query(models.Employee).filter(
        models.Employee.supervisor_id.in_(supervisor_ids)
    ).all() if supervisor_ids else []
    employee_ids = [employee.employee_id for employee in employees]
    latest = {}
    if employee_ids:
        for record in db.query(models.PerformanceRecord).filter(
            models.PerformanceRecord.employee_id.in_(employee_ids)
        ).order_by(models.PerformanceRecord.recorded_at.desc()).all():
            latest.setdefault(record.employee_id, record)
    context = []
    for employee in employees:
        record = latest.get(employee.employee_id)
        metrics = []
        if record:
            for metric in QUESTION_METRICS:
                value = _metric_value(record, metric)
                if value is not None:
                    metrics.append(f"{metric['label']}: {value:g}{metric['unit']} ({_metric_status(record, metric)})")
        context.append({"employee": employee.full_name, "employee_id": employee.employee_id,
                        "role": employee.role, "supervisor_id": employee.supervisor_id,
                        "latest_telemetry": metrics or ["No telemetry available"]})
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=503, detail="The coaching service is not configured. Add OPENAI_API_KEY to the backend .env file.")
    instructions = (
        "You are a fair decision-support coach for a bank executive. Use only the supplied region's direct-report data. "
        "Summarize team-level patterns and, when asked by name, cite latest telemetry and safe/warning/danger state. "
        "Do not infer personal traits, burnout, mental health, intent, or causes from metrics; ask leaders to speak respectfully with staff. "
        "Do not make employment decisions or compare employees as people. KPI colors are demonstration thresholds, not bank policy. "
        "Do not request customer identifiers or confidential account details. "
        f"Region-scoped employee context: {json.dumps(context, ensure_ascii=False)}"
    )
    try:
        response = OpenAI(api_key=os.getenv("OPENAI_API_KEY")).responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-6-luna"), instructions=instructions,
            input=[{"role": item.role, "content": item.content.strip()} for item in payload.messages[-12:]],
            max_output_tokens=500, store=False,
        )
    except OpenAIError:
        raise HTTPException(status_code=502, detail="The executive coach could not answer right now. Please try again shortly")
    reply = response.output_text.strip()
    if not reply:
        raise HTTPException(status_code=502, detail="The executive coach returned an empty response")
    return {"reply": reply}


# ---------------------------------------------------------
# 5. Supervisor Dashboard Endpoints# ---------------------------------------------------------
# 5. Supervisor Dashboard Endpoints
# ---------------------------------------------------------
@app.get("/api/v1/supervisors/{supervisor_id}", response_model=schemas.SupervisorResponse)
def get_supervisor(
    supervisor_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    return ensure_supervisor_access(db, current_user, supervisor_id)

@app.get("/api/v1/supervisors/{supervisor_id}/employees", response_model=List[schemas.EmployeeResponse])
def get_supervisor_employees(
    supervisor_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    ensure_supervisor_access(db, current_user, supervisor_id)
    return db.query(models.Employee).filter(
        models.Employee.supervisor_id == supervisor_id
    ).all()

@app.get("/api/v1/supervisors/{supervisor_id}/team", response_model=List[schemas.EmployeeResponse])
def get_supervisor_team(
    supervisor_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    ensure_supervisor_access(db, current_user, supervisor_id)
    return db.query(models.Employee).filter_by(supervisor_id=supervisor_id).all()


@app.get("/api/v1/supervisors/{supervisor_id}/team-reports", response_model=List[schemas.AppraisalReportResponse])
def get_supervisor_team_reports(
    supervisor_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    ensure_supervisor_access(db, current_user, supervisor_id)
    return db.query(models.AppraisalReport).join(
        models.Employee, models.AppraisalReport.employee_id == models.Employee.employee_id
    ).filter(
        models.Employee.supervisor_id == supervisor_id
    ).all()

# ---------------------------------------------------------
# 6. Executive Dashboard & Overrides Endpoints
# ---------------------------------------------------------
@app.get("/api/v1/executives/{executive_id}", response_model=schemas.ExecutiveResponse)
def get_executive(
    executive_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] != "executive" or current_user.get("user_id") != executive_id:
        raise HTTPException(status_code=403, detail="Access denied")

    executive = db.query(models.ExecutiveManager).filter(
        models.ExecutiveManager.executive_id == executive_id
    ).first()
    if not executive:
        raise HTTPException(status_code=404, detail="Executive not found")
    return executive

@app.get("/api/v1/executives/{executive_id}/reports", response_model=List[schemas.AppraisalReportResponse])
def get_executive_reports(
    executive_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] != "executive" or current_user.get("user_id") != executive_id:
        raise HTTPException(status_code=403, detail="Access denied")

    reports = db.query(models.AppraisalReport).join(
        models.Employee, models.AppraisalReport.employee_id == models.Employee.employee_id
    ).join(
        models.ImmediateSupervisor, models.Employee.supervisor_id == models.ImmediateSupervisor.supervisor_id
    ).filter(
        models.ImmediateSupervisor.executive_id == executive_id
    ).order_by(models.AppraisalReport.generation_date.desc()).all()
    report_ids = [report.report_id for report in reports]
    audit_rows = db.query(models.ComplianceOverrideAudit).filter(
        models.ComplianceOverrideAudit.report_id.in_(report_ids)
    ).order_by(models.ComplianceOverrideAudit.created_at.desc()).all() if report_ids else []
    audits_by_report = {}
    for event in audit_rows:
        audits_by_report.setdefault(event.report_id, []).append({
            "audit_id": event.audit_id,
            "executive_id": event.executive_id,
            "previous_status": event.previous_status,
            "new_status": event.new_status,
            "justification": event.justification,
            "created_at": event.created_at,
        })
    return [{
        "report_id": report.report_id,
        "employee_id": report.employee_id,
        "unified_trust_score": report.unified_trust_score,
        "report_status": report.report_status,
        "compliance_override_status": report.compliance_override_status,
        "overriding_executive_id": report.overriding_executive_id,
        "compliance_override_reason": report.compliance_override_reason,
        "compliance_override_updated_at": report.compliance_override_updated_at,
        "override_audit": audits_by_report.get(report.report_id, []),
        "generation_date": report.generation_date,
    } for report in reports]

@app.get("/api/v1/executives/{executive_id}/supervisors", response_model=List[schemas.SupervisorResponse])
def get_executive_supervisors(
    executive_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if current_user["role"] != "executive" or current_user.get("user_id") != executive_id:
        raise HTTPException(status_code=403, detail="Access denied")
    supervisors = db.query(models.ImmediateSupervisor).filter_by(
        executive_id=executive_id
    ).order_by(models.ImmediateSupervisor.supervisor_id.asc()).all()
    supervisor_ids = [supervisor.supervisor_id for supervisor in supervisors]
    employees_by_supervisor = {supervisor_id: [] for supervisor_id in supervisor_ids}
    supervisor_appraisal_counts = {supervisor_id: 0 for supervisor_id in supervisor_ids}
    latest_records = {}
    if supervisor_ids:
        appraisal_supervisor_ids = db.query(
            models.SupervisorAppraisal.supervisor_id
        ).filter(models.SupervisorAppraisal.supervisor_id.in_(supervisor_ids)).all()
        for (appraisal_supervisor_id,) in appraisal_supervisor_ids:
            supervisor_appraisal_counts[appraisal_supervisor_id] = supervisor_appraisal_counts.get(appraisal_supervisor_id, 0) + 1
        employees = db.query(
            models.Employee.employee_id, models.Employee.supervisor_id
        ).filter(models.Employee.supervisor_id.in_(supervisor_ids)).all()
        for employee_id, supervisor_id in employees:
            employees_by_supervisor.setdefault(supervisor_id, []).append(employee_id)
        record_rows = db.query(models.PerformanceRecord).join(
            models.Employee, models.Employee.employee_id == models.PerformanceRecord.employee_id
        ).filter(
            models.Employee.supervisor_id.in_(supervisor_ids)
        ).order_by(
            models.PerformanceRecord.recorded_at.desc(), models.PerformanceRecord.record_id.desc()
        ).all()
        for record in record_rows:
            latest_records.setdefault(record.employee_id, record)
    return [{
        "supervisor_id": supervisor.supervisor_id,
        "executive_id": supervisor.executive_id,
        "full_name": supervisor.full_name or f"Supervisor #{supervisor.supervisor_id}",
        "department_code": supervisor.department_code or "Not assigned",
        "branch_code": supervisor.branch_code,
        "team_size": len(employees_by_supervisor.get(supervisor.supervisor_id, [])),
        "employees_with_telemetry": sum(
            employee_id in latest_records
            for employee_id in employees_by_supervisor.get(supervisor.supervisor_id, [])
        ),
        "supervisor_appraisal_count": supervisor_appraisal_counts.get(supervisor.supervisor_id, 0),
        "team_kpi_averages": _aggregate_team_kpis(
            latest_records, employees_by_supervisor.get(supervisor.supervisor_id, [])
        ),
    } for supervisor in supervisors]


@app.post("/api/v1/executives/override-compliance")
def execute_compliance_override(
    payload: schemas.ExecutiveOverrideRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    if current_user.get("role") != "executive":
        raise HTTPException(status_code=403, detail="Only executives can trigger compliance overrides")
    if current_user.get("user_id") != payload.executive_id:
        raise HTTPException(status_code=403, detail="Access denied")

    report = db.query(models.AppraisalReport).join(
        models.Employee, models.AppraisalReport.employee_id == models.Employee.employee_id
    ).join(
        models.ImmediateSupervisor, models.Employee.supervisor_id == models.ImmediateSupervisor.supervisor_id
    ).filter(
        models.AppraisalReport.report_id == payload.report_id,
        models.ImmediateSupervisor.executive_id == payload.executive_id,
    ).with_for_update().first()
    if not report:
        raise HTTPException(status_code=404, detail="Appraisal report not found")

    justification = payload.justification.strip()
    if len(justification) < 10:
        raise HTTPException(status_code=422, detail="Provide at least 10 characters explaining this override action")
    if report.compliance_override_status == payload.compliance_override_status:
        action = "already applied" if payload.compliance_override_status else "not currently applied"
        raise HTTPException(status_code=409, detail=f"A compliance override is {action} for this report")

    previous_status = report.compliance_override_status
    audit = models.ComplianceOverrideAudit(
        report_id=report.report_id,
        executive_id=payload.executive_id,
        previous_status=previous_status,
        new_status=payload.compliance_override_status,
        justification=justification,
    )
    report.compliance_override_status = payload.compliance_override_status
    report.overriding_executive_id = payload.executive_id if payload.compliance_override_status else None
    report.compliance_override_reason = justification
    report.compliance_override_updated_at = datetime.now(timezone.utc)
    db.add(audit)
    db.commit()
    db.refresh(audit)

    return {
        "status": "success",
        "message": f"Compliance override {'applied' if payload.compliance_override_status else 'removed'} for report #{payload.report_id}",
        "report_id": report.report_id,
        "override_status": report.compliance_override_status,
        "reason": report.compliance_override_reason,
        "audit_event": {
            "audit_id": audit.audit_id,
            "executive_id": audit.executive_id,
            "previous_status": audit.previous_status,
            "new_status": audit.new_status,
            "justification": audit.justification,
            "created_at": audit.created_at,
        },
    }

# ---------------------------------------------------------
# 7. Authentication
PASSWORD_RESET_MINUTES = 30

def _password_policy_error(password: str) -> str | None:
    if len(password) < 12:
        return "Password must be at least 12 characters long."
    if len(password.encode("utf-8")) > 72:
        return "Password must be no more than 72 bytes."
    if not any(c.islower() for c in password):
        return "Password must include a lowercase letter."
    if not any(c.isupper() for c in password):
        return "Password must include an uppercase letter."
    if not any(c.isdigit() for c in password):
        return "Password must include a number."
    if not any(not c.isalnum() for c in password):
        return "Password must include a symbol."
    return None

@app.post("/api/v1/login", response_model=schemas.TokenResponse)
def login(credentials: schemas.LoginRequest, db: Session = Depends(get_db)):
    email = credentials.email.strip().lower()
    user = db.query(models.Employee).filter(
        models.Employee.email == email,
        models.Employee.is_active.is_(True),
    ).first()
    if not user or not auth.verify_password(credentials.password, user.password_hashed):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    role, user_id = user.user_type, user.employee_id
    if role == "supervisor":
        profile = db.query(models.ImmediateSupervisor).filter_by(emp_id=user.employee_id).first()
        if not profile:
            raise HTTPException(status_code=403, detail="Account role is not configured")
        user_id = profile.supervisor_id
    elif role == "executive":
        profile = db.query(models.ExecutiveManager).filter_by(emp_id=user.employee_id).first()
        if not profile:
            raise HTTPException(status_code=403, detail="Account role is not configured")
        user_id = profile.executive_id

    token = auth.create_access_token({
        "user_id": user_id, "employee_id": user.employee_id, "role": role,
        "token_version": user.auth_token_version
    })
    return {
        "access_token": token, "token_type": "bearer",
        "role": role, "user_id": user_id, "email": user.email,
    }

@app.get("/api/v1/auth/me")
def get_authenticated_profile(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    employee = db.query(models.Employee).filter_by(employee_id=current_user.get("employee_id")).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee profile not found for this account")
    # Only base employees belong to an immediate-supervisor reporting line.
    # Supervisor and executive identities are employee rows for authentication,
    # but use their role-specific profiles and hierarchy instead.
    is_base_employee = current_user.get("role") == "employee"
    supervisor = db.query(models.ImmediateSupervisor).filter_by(
        supervisor_id=employee.supervisor_id
    ).first() if is_base_employee and employee.supervisor_id is not None else None
    return {
        "employee_id": employee.employee_id,
        "user_id": current_user.get("user_id"),
        "role": current_user.get("role"),
        "full_name": employee.full_name,
        "email": employee.email,
        "department": employee.department,
        "job_title": employee.role,
        "supervisor_id": employee.supervisor_id if is_base_employee else None,
        "supervisor_name": supervisor.full_name if supervisor else None,
        "branch_location": supervisor.branch_code if supervisor else None,
    }


@app.post("/api/v1/forgot-password", status_code=status.HTTP_202_ACCEPTED)
def forgot_password(request: schemas.ForgotPasswordRequest, db: Session = Depends(get_db)):
    response = {"message": "If an account exists for that email, password reset instructions are available."}
    email = request.email.strip().lower()
    user = db.query(models.Employee).filter(
        models.Employee.email == email, models.Employee.is_active.is_(True)
    ).first()
    if not user:
        return response

    now = datetime.now(timezone.utc)
    db.query(models.PasswordResetToken).filter(
        models.PasswordResetToken.employee_id == user.employee_id,
        models.PasswordResetToken.consumed_at.is_(None),
    ).update({"consumed_at": now}, synchronize_session=False)
    raw_token = secrets.token_urlsafe(32)
    digest = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    db.add(models.PasswordResetToken(
        employee_id=user.employee_id,
        token_hashed=digest,
        expires_at=now + timedelta(minutes=PASSWORD_RESET_MINUTES),
    ))
    db.commit()
    reset_link = "http://localhost:5173/?reset_token=" + raw_token
    print("[DEV PASSWORD RESET] Email: " + user.email + " | Link: " + reset_link)
    return response

@app.post("/api/v1/reset-password")
def reset_password(request: schemas.ResetPasswordRequest, db: Session = Depends(get_db)):
    policy_error = _password_policy_error(request.new_password)
    if policy_error:
        raise HTTPException(status_code=422, detail=policy_error)

    digest = hashlib.sha256(request.token.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)
    reset_record = db.query(models.PasswordResetToken).filter(
        models.PasswordResetToken.token_hashed == digest,
        models.PasswordResetToken.consumed_at.is_(None),
        models.PasswordResetToken.expires_at > now,
    ).first()
    if not reset_record:
        raise HTTPException(status_code=400, detail="Reset link is invalid or expired.")
    user = db.query(models.Employee).filter(
        models.Employee.employee_id == reset_record.employee_id,
        models.Employee.is_active.is_(True),
    ).first()
    if not user:
        raise HTTPException(status_code=400, detail="Reset link is invalid or expired.")

    user.password_hashed = auth.hash_password(request.new_password)
    user.auth_token_version += 1
    reset_record.consumed_at = now
    db.query(models.PasswordResetToken).filter(
        models.PasswordResetToken.employee_id == user.employee_id,
        models.PasswordResetToken.consumed_at.is_(None),
    ).update({"consumed_at": now}, synchronize_session=False)
    db.commit()
    return {"message": "Password reset successfully. You can now sign in."}

from typing import Any, Protocol, cast

class SupportsGenerate(Protocol):
    def generate(self, *args: Any, **kwargs: Any) -> Any:
        ...

# ---------------------------------------------------------
# Organization administration
# ---------------------------------------------------------
@app.get("/api/v1/admin/overview")
def get_admin_overview(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    ensure_admin(current_user)
    accounts = {
        key: db.query(func.count(models.Employee.employee_id)).filter_by(user_type=key).scalar() or 0
        for key in ("employee", "supervisor", "executive", "admin")
    }
    accounts = {
        "employees": accounts["employee"],
        "supervisors": accounts["supervisor"],
        "executives": accounts["executive"],
        "admins": accounts["admin"],
        "active_accounts": db.query(func.count(models.Employee.employee_id)).filter_by(is_active=True).scalar() or 0,
        "total_accounts": db.query(func.count(models.Employee.employee_id)).scalar() or 0,
    }

    kpi_columns = [
        ("loan_volumes", models.PerformanceRecord.loan_volumes),
        ("transaction_accuracy", models.PerformanceRecord.transaction_accuracy),
        ("workplan_completion", models.PerformanceRecord.workplan_completion),
        ("tasks_on_time", models.PerformanceRecord.task_deadline_fulfillment_pct),
        ("accounts_opened", models.PerformanceRecord.accounts_opened),
        ("complaint_resolution", models.PerformanceRecord.complaint_resolution_rate_pct),
        ("customer_satisfaction", models.PerformanceRecord.customer_satisfaction),
        ("processing_errors", models.PerformanceRecord.error_frequencies),
        ("loan_processing_hours", models.PerformanceRecord.loan_processing_turnaround_hours),
        ("non_performing_credit", models.PerformanceRecord.non_performing_credit_pct),
        ("cash_reconciliation_errors", models.PerformanceRecord.cash_reconciliation_errors),
        ("compliance_incidents", models.PerformanceRecord.compliance_incidents),
        ("digital_channel_adoption", models.PerformanceRecord.digital_channel_adoption_pct),
    ]
    telemetry_result = db.query(
        func.count(models.PerformanceRecord.record_id),
        *[func.avg(column) for _, column in kpi_columns],
    ).one()
    telemetry = {
        "records_count": int(telemetry_result[0] or 0),
        "averages": {
            name: (round(float(value), 2) if value is not None else None)
            for (name, _), value in zip(kpi_columns, telemetry_result[1:])
        },
    }

    report_count, average_score = db.query(
        func.count(models.AppraisalReport.report_id),
        func.avg(models.AppraisalReport.unified_trust_score),
    ).one()
    feedback_count = db.query(func.count(models.UnstructuredFeedback.feedback_id)).scalar() or 0

    dimension_labels = {
        "communication": "Communication",
        "collaboration": "Collaboration",
        "compliance_awareness": "Compliance awareness",
        "learning_development": "Learning and development",
    }
    dimension_scores = {
        key: {"scores": [], "human_reviewed_count": 0, "ai_draft_count": 0}
        for key in dimension_labels
    }
    ai_reports = db.query(
        models.AIPerformanceReport.feedback_dimensions,
        models.AIPerformanceReport.report_status,
    ).all()
    for dimensions, report_status in ai_reports:
        if not isinstance(dimensions, dict):
            continue
        for key in dimension_labels:
            item = dimensions.get(key)
            score = item.get("score_1_5") if isinstance(item, dict) else None
            if isinstance(score, (int, float)) and not isinstance(score, bool) and 1 <= score <= 5:
                dimension_scores[key]["scores"].append(float(score))
                if report_status == "human_reviewed":
                    dimension_scores[key]["human_reviewed_count"] += 1
                else:
                    dimension_scores[key]["ai_draft_count"] += 1
    category_items = [
        {
            "category": key,
            "label": dimension_labels[key],
            "average_score": round(sum(values["scores"]) / len(values["scores"]), 2) if values["scores"] else None,
            "ratings_count": len(values["scores"]),
            "human_reviewed_count": values["human_reviewed_count"],
            "ai_draft_count": values["ai_draft_count"],
        }
        for key, values in dimension_scores.items()
    ]
    has_ratings = any(item["ratings_count"] for item in category_items)

    pipeline_runs = db.query(models.TrustScoreRun).order_by(
        models.TrustScoreRun.generated_at.desc()
    ).all()
    pipeline_classifications = db.query(models.FeedbackClassification).filter(
        models.FeedbackClassification.is_current.is_(True),
        models.FeedbackClassification.review_status == "auto_classified",
    ).all()
    direction_counts = {
        category: {
            direction: sum(
                row.category == category and row.predicted_direction == direction
                for row in pipeline_classifications
            )
            for direction in ("positive", "negative", "mixed", "neutral")
        }
        for category in REPORT_DIMENSIONS
    }
    reviewed_counts = {
        category: sum(
            row.category == category and row.review_status == "auto_classified" and row.is_current
            for row in pipeline_classifications
        )
        for category in REPORT_DIMENSIONS
    }
    pending_count = sum(row.review_status == "pending" for row in pipeline_classifications)
    ready_runs = [run for run in pipeline_runs if run.score_status == "ready" and run.trust_score is not None]
    pipeline_categories = []
    for key in REPORT_DIMENSIONS:
        scores = [
            float(run.feedback_groups[key]["score_0_100"])
            for run in ready_runs
            if isinstance(run.feedback_groups, dict)
            and isinstance(run.feedback_groups.get(key), dict)
            and run.feedback_groups[key].get("score_0_100") is not None
        ]
        pipeline_categories.append({
            "category": key,
            "label": dimension_labels[key],
            "average_score_0_100": round(sum(scores) / len(scores), 1) if scores else None,
            "scored_run_count": len(scores),
            "predicted_directions": direction_counts[key],
            "classified_answer_count": reviewed_counts[key],
        })
    pipeline_kpi_groups = []
    for key, label in (
        ("operational_quality", "Operational quality"),
        ("delivery_timeliness", "Delivery and timeliness"),
        ("customer_outcomes", "Customer outcomes"),
        ("risk_controls", "Risk and controls"),
    ):
        scores = [
            float(run.kpi_groups[key]["score_0_100"])
            for run in pipeline_runs
            if isinstance(run.kpi_groups, dict)
            and isinstance(run.kpi_groups.get(key), dict)
            and run.kpi_groups[key].get("score_0_100") is not None
        ]
        pipeline_kpi_groups.append({
            "category": key,
            "label": label,
            "average_score_0_100": round(sum(scores) / len(scores), 1) if scores else None,
            "sample_count": len(scores),
        })
    trust_pipeline = {
        "available": bool(pipeline_runs or pipeline_classifications),
        "runs_count": len(pipeline_runs),
        "scores_ready_count": len(ready_runs),
        "awaiting_review_count": 0,
        "incomplete_count": sum(run.score_status == "incomplete" for run in pipeline_runs),
        "average_trust_score": round(sum(float(run.trust_score) for run in ready_runs) / len(ready_runs), 1) if ready_runs else None,
        "pending_feedback_reviews": pending_count,
        "cash_zero_tolerance_alerts": sum(
            bool((run.data_coverage or {}).get("cash_reconciliation_zero_tolerance_alert"))
            for run in pipeline_runs
        ),
        "kpi_groups": pipeline_kpi_groups,
        "feedback_categories": pipeline_categories,
        "message": (
            "Trust Scores average four KPI groups and four automatically classified feedback categories from supervisor appraisal answers. Employee self-questionnaire answers are context for the supervisor and are not scored."
            if pipeline_runs or pipeline_classifications
            else "Run the appraisal pipeline for a team to classify submitted supervisor appraisal answers."
        ),
    }

    return {
        "accounts": accounts,
        "telemetry": telemetry,
        "reports": {
            "count": int(report_count or 0),
            "average_trust_score": round(float(average_score), 2) if average_score is not None else None,
        },
        "feedback_count": int(feedback_count),
        "ai_categories": {
            "available": has_ratings,
            "items": category_items,
            "message": (
                "Average 1–5 feedback ratings across saved AI appraisal reports. Draft ratings are provisional; counts distinguish them from human-reviewed reports."
                if has_ratings else "AI competency summaries will appear after an AI appraisal report has saved competency ratings."
            ),
        },
        "trust_pipeline": trust_pipeline,
    }


@app.get("/api/v1/admin/employees", response_model=List[schemas.AdminEmployeeResponse])
def list_admin_employees(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    ensure_admin(current_user)
    employees = db.query(models.Employee).order_by(
        models.Employee.user_type.asc(), models.Employee.full_name.asc()
    ).all()
    return [admin_employee_payload(db, employee) for employee in employees]


@app.post("/api/v1/admin/employees", response_model=schemas.AdminEmployeeResponse, status_code=201)
def create_admin_managed_employee(
    payload: schemas.AdminEmployeeCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    ensure_admin(current_user)
    if payload.user_type not in {"employee", "supervisor", "executive"}:
        raise HTTPException(status_code=422, detail="Account type must be employee, supervisor, or executive")
    password_error = _password_policy_error(payload.password)
    if password_error:
        raise HTTPException(status_code=422, detail=password_error)
    email = payload.email.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(status_code=422, detail="Enter a valid email address")
    if db.query(models.Employee).filter(func.lower(models.Employee.email) == email).first():
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    if payload.user_type == "employee" and payload.supervisor_id is not None:
        if not active_supervisor_profile(db, payload.supervisor_id):
            raise HTTPException(status_code=400, detail="Choose an active supervisor")
    elif payload.user_type == "supervisor":
        if not payload.branch_code or not payload.branch_code.strip():
            raise HTTPException(status_code=400, detail="Branch code is required for a supervisor")
        if payload.executive_id is None or not active_executive_profile(db, payload.executive_id):
            raise HTTPException(status_code=400, detail="Choose an active executive for this supervisor")
    elif payload.user_type == "executive" and (not payload.oversight_region or not payload.oversight_region.strip()):
        raise HTTPException(status_code=400, detail="Oversight region is required for an executive")

    employee = models.Employee(
        full_name=payload.full_name.strip(), email=email,
        password_hashed=auth.hash_password(payload.password),
        department=payload.department.strip(), role=payload.role.strip(),
        user_type=payload.user_type,
        supervisor_id=payload.supervisor_id if payload.user_type == "employee" else None,
    )
    db.add(employee)
    try:
        db.flush()
        if payload.user_type == "supervisor":
            db.add(models.ImmediateSupervisor(
                branch_code=payload.branch_code.strip(), executive_id=payload.executive_id,
                emp_id=employee.employee_id,
            ))
        elif payload.user_type == "executive":
            db.add(models.ExecutiveManager(
                emp_id=employee.employee_id, oversight_region=payload.oversight_region.strip(),
            ))
        db.commit()
        db.refresh(employee)
    except Exception:
        db.rollback()
        raise
    return admin_employee_payload(db, employee)


@app.patch("/api/v1/admin/employees/{employee_id}", response_model=schemas.AdminEmployeeResponse)
def update_admin_managed_employee(
    employee_id: int,
    payload: schemas.AdminEmployeeUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    ensure_admin(current_user)
    employee = db.query(models.Employee).filter_by(employee_id=employee_id).first()
    if not employee or employee.user_type == "admin":
        raise HTTPException(status_code=404, detail="Managed employee account not found")

    supplied = getattr(payload, "model_fields_set", getattr(payload, "__fields_set__", set()))
    updates = payload.model_dump(exclude_unset=True) if hasattr(payload, "model_dump") else payload.dict(exclude_unset=True)
    if "email" in supplied and payload.email is not None:
        email = payload.email.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            raise HTTPException(status_code=422, detail="Enter a valid email address")
        duplicate = db.query(models.Employee).filter(
            func.lower(models.Employee.email) == email,
            models.Employee.employee_id != employee_id,
        ).first()
        if duplicate:
            raise HTTPException(status_code=409, detail="An account with this email already exists")
        employee.email = email
    for field in ("full_name", "department", "role", "is_active"):
        if field in updates and updates[field] is not None:
            value = updates[field]
            setattr(employee, field, value.strip() if isinstance(value, str) else value)
    if updates.get("password"):
        password_error = _password_policy_error(updates["password"])
        if password_error:
            raise HTTPException(status_code=422, detail=password_error)
        employee.password_hashed = auth.hash_password(updates["password"])
        employee.auth_token_version += 1

    if employee.user_type == "employee":
        if "supervisor_id" in supplied:
            supervisor_id = payload.supervisor_id
            if supervisor_id is not None and not active_supervisor_profile(db, supervisor_id):
                raise HTTPException(status_code=400, detail="Choose an active supervisor")
            employee.supervisor_id = supervisor_id
        if supplied.intersection({"executive_id", "branch_code", "oversight_region"}):
            raise HTTPException(status_code=400, detail="Those hierarchy fields apply only to manager accounts")
    elif employee.user_type == "supervisor":
        profile = db.query(models.ImmediateSupervisor).filter_by(emp_id=employee.employee_id).first()
        if profile is None:
            raise HTTPException(status_code=409, detail="Supervisor profile is missing; repair it before editing")
        if "branch_code" in supplied:
            if not payload.branch_code or not payload.branch_code.strip():
                raise HTTPException(status_code=400, detail="Branch code cannot be blank")
            profile.branch_code = payload.branch_code.strip()
        if "executive_id" in supplied:
            if payload.executive_id is None or not active_executive_profile(db, payload.executive_id):
                raise HTTPException(status_code=400, detail="Choose an active executive")
            profile.executive_id = payload.executive_id
        if supplied.intersection({"supervisor_id", "oversight_region"}):
            raise HTTPException(status_code=400, detail="Those hierarchy fields do not apply to supervisors")
    elif employee.user_type == "executive":
        profile = db.query(models.ExecutiveManager).filter_by(emp_id=employee.employee_id).first()
        if profile is None:
            raise HTTPException(status_code=409, detail="Executive profile is missing; repair it before editing")
        if "oversight_region" in supplied:
            if not payload.oversight_region or not payload.oversight_region.strip():
                raise HTTPException(status_code=400, detail="Oversight region cannot be blank")
            profile.oversight_region = payload.oversight_region.strip()
        if supplied.intersection({"supervisor_id", "executive_id", "branch_code"}):
            raise HTTPException(status_code=400, detail="Those hierarchy fields do not apply to executives")

    try:
        db.commit()
        db.refresh(employee)
    except Exception:
        db.rollback()
        raise
    return admin_employee_payload(db, employee)
