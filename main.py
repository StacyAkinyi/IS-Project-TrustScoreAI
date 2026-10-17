from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from zoneinfo import ZoneInfo
from pydantic import BaseModel
from dotenv import load_dotenv
from openai import OpenAI, OpenAIError
from typing import List, Optional, Any, Literal
import hashlib
import os
import json
import random
from pathlib import Path
import secrets
import joblib
import numpy as np
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient

import models
from models import Base
import schemas
import auth
from database import engine, get_db
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

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

# MongoDB Connection
MONGO_URI = "mongodb://localhost:27017/"
mongo_client = MongoClient(MONGO_URI)
mongo_db = mongo_client["trustscore_mongo"]

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

# ---------------------------------------------------------
# 1. Load Pre-Trained Machine Learning Models
# ---------------------------------------------------------
try:
    rf_model = joblib.load('trust_score_rf_model.pkl')
    tfidf_vectorizer = joblib.load('tfidf_vectorizer.pkl')
    print("✓ Machine Learning pipeline loaded successfully.")
except FileNotFoundError:
    print("Warning: .pkl files not found. Ensure models are saved in the root directory.")




SUPERVISOR_APPRAISAL_QUESTIONS = [
    {"id": "procedure_adherence", "type": "yes_no", "prompt": "Did the employee follow the documented procedures relevant to their role during this review period?"},
    {"id": "accuracy_expectations", "type": "yes_no", "prompt": "Did the employee meet the agreed accuracy expectations, based on available work evidence?"},
    {"id": "timeliness_expectations", "type": "yes_no", "prompt": "Did the employee meet agreed deadlines for assigned work?"},
    {"id": "risk_escalation", "type": "yes_no", "prompt": "Did the employee escalate material errors, customer concerns, or compliance risks through the expected channels?"},
    {"id": "team_contribution", "type": "yes_no", "prompt": "Did the employee meet the agreed expectations for respectful collaboration and customer service?"},
    {"id": "evidence_achievements", "type": "open", "prompt": "What are up to two specific achievements from this period, and what evidence supports them?"},
    {"id": "evidence_strengths", "type": "open", "prompt": "Which role-related strengths did you observe? Give a specific work example for each."},
    {"id": "context_barriers", "type": "open", "prompt": "What work-related barriers or changing conditions affected results, and what context should be considered?"},
    {"id": "development_goal", "type": "open", "prompt": "What is one practical development goal for the next six months, and how will progress be observed?"},
    {"id": "support_needed", "type": "open", "prompt": "What support, coaching, tools, or workload changes would help the employee succeed?"},
]


def current_review_period():
    today = datetime.now(ZoneInfo("Africa/Nairobi"))
    return f"{today.year}-H{1 if today.month <= 6 else 2}"


QUESTION_METRICS = [
    {"key": "transaction_accuracy", "label": "transaction accuracy", "unit": "%", "max": 100, "direction": "high", "decimals": 1},
    {"key": "workplan_completion", "label": "workplan completion", "unit": "%", "max": 120, "direction": "high", "decimals": 1},
    {"key": "task_deadline_fulfillment_pct", "label": "tasks completed on time", "unit": "%", "max": 100, "direction": "high", "decimals": 1},
    {"key": "complaint_resolution_rate_pct", "label": "complaint resolution", "unit": "%", "max": 100, "direction": "high", "decimals": 1},
    {"key": "customer_satisfaction", "label": "customer satisfaction", "unit": " / 5", "max": 5, "direction": "high", "decimals": 2},
    {"key": "error_frequencies", "label": "processing errors", "unit": "", "max": 15, "direction": "low", "decimals": 0},
    {"key": "loan_processing_turnaround_hours", "label": "loan processing time", "unit": " hours", "max": 96, "direction": "low", "decimals": 1},
    {"key": "non_performing_credit_pct", "label": "non-performing credit", "unit": "%", "max": 18, "direction": "low", "decimals": 1},
    {"key": "cash_reconciliation_errors", "label": "cash reconciliation errors", "unit": "", "max": 10, "direction": "low", "decimals": 0},
    {"key": "compliance_incidents", "label": "compliance incidents", "unit": "", "max": 4, "direction": "low", "decimals": 0},
]


def _metric_value(record, metric):
    value = getattr(record, metric["key"], None)
    return float(value) if value is not None else None


def _format_metric_value(value, metric):
    return f"{value:.{metric['decimals']}f}{metric['unit']}"


def _metric_status(record, metric):
    value = _metric_value(record, metric)
    if value is None:
        return None
    normalized = value / metric["max"]
    if metric["direction"] == "high":
        return "Danger" if normalized < 1 / 3 else "Warning" if normalized < 2 / 3 else "Safe"
    return "Safe" if normalized <= 1 / 3 else "Warning" if normalized <= 2 / 3 else "Danger"


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
        normalized = average / metric["max"]
        if metric["direction"] == "high":
            state = "Danger" if normalized < 1 / 3 else "Warning" if normalized < 2 / 3 else "Safe"
        else:
            state = "Safe" if normalized <= 1 / 3 else "Warning" if normalized <= 2 / 3 else "Danger"
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
    if current_user.get("employee_id") != employee_id:
        raise HTTPException(status_code=403, detail="Access denied")

    latest_record = db.query(models.PerformanceRecord).filter(
        models.PerformanceRecord.employee_id == employee_id
    ).order_by(models.PerformanceRecord.recorded_at.desc()).first()
    question_snapshot = _build_reflection_questions(latest_record)
    return {
        "employee_id": employee_id,
        "questions": [item["text"] for item in question_snapshot],
        "question_snapshot": question_snapshot,
        "based_on_latest_record": latest_record is not None,
        "method": "random question-bank sampling weighted by current KPI states",
    }


class SelfAppraisalSubmission(BaseModel):
    generated_questions: List[str]
    question_snapshot: List[dict]
    feedback_text: str


@app.post("/evaluate-employee/")
def save_self_appraisal(
    payload: SelfAppraisalSubmission,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") != "employee":
        raise HTTPException(status_code=403, detail="Only employees can submit a self-appraisal")
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

    employee_id = current_user["employee_id"]
    employee = db.query(models.Employee).filter(
        models.Employee.employee_id == employee_id,
        models.Employee.is_active.is_(True),
    ).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee account not found")

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
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    ensure_supervisor_access(db, current_user, supervisor_id)
    if current_user.get("role") != "supervisor":
        raise HTTPException(status_code=403, detail="Only the assigned supervisor can issue this appraisal")
    return {"period_code": current_review_period(), "questions": SUPERVISOR_APPRAISAL_QUESTIONS}


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
    if len(payload.answers) != 10:
        raise HTTPException(status_code=422, detail="The semiannual form requires exactly 10 answers")
    answers_by_id = {answer.get("question_id"): answer.get("answer") for answer in payload.answers}
    expected_ids = {question["id"] for question in SUPERVISOR_APPRAISAL_QUESTIONS}
    if set(answers_by_id) != expected_ids:
        raise HTTPException(status_code=422, detail="The form answers do not match the current appraisal questions")
    snapshot = []
    yes_count = 0
    for question in SUPERVISOR_APPRAISAL_QUESTIONS:
        answer = answers_by_id[question["id"]]
        if question["type"] == "yes_no":
            if not isinstance(answer, bool):
                raise HTTPException(status_code=422, detail="Answer each yes/no question with Yes or No")
            yes_count += int(answer)
        else:
            if not isinstance(answer, str) or len(answer.strip()) < 10 or len(answer) > 3000:
                raise HTTPException(status_code=422, detail="Each open response must contain 10 to 3,000 characters")
            answer = answer.strip()
        snapshot.append({**question, "answer": answer})
    record = models.SupervisorAppraisal(
        employee_id=employee.employee_id,
        supervisor_id=supervisor_id,
        period_code=current_review_period(),
        answers_snapshot=snapshot,
        yes_count=yes_count,
    )
    try:
        db.add(record)
        db.commit()
        db.refresh(record)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A supervisor appraisal is already submitted for this employee in this half-year period")
    return {"appraisal_id": record.appraisal_id, "employee_id": record.employee_id,
            "period_code": record.period_code, "yes_count": record.yes_count,
            "employee_notified_at": record.employee_notified_at,
            "message": "The appraisal is saved and available in the employee dashboard."}


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
    return [{"appraisal_id": row.appraisal_id, "employee_id": row.employee_id,
             "employee_name": full_name, "period_code": row.period_code,
             "answers": row.answers_snapshot, "yes_count": row.yes_count,
             "review_request_text": row.review_request_text,
             "review_requested_at": row.review_requested_at,
             "review_edit_count": row.review_edit_count,
             "satisfied_at": row.satisfied_at,
             "status": "satisfied" if row.satisfied_at else ("review_requested" if row.review_requested_at and row.review_edit_count == 0 else ("reviewed" if row.review_edit_count else "awaiting_employee")),
             "created_at": row.created_at} for row, full_name in rows]


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
    return [{"appraisal_id": row.appraisal_id, "period_code": row.period_code,
             "answers": row.answers_snapshot, "yes_count": row.yes_count,
             "employee_notified_at": row.employee_notified_at,
             "review_request_text": row.review_request_text,
             "review_requested_at": row.review_requested_at,
             "review_edit_count": row.review_edit_count,
             "satisfied_at": row.satisfied_at,
             "status": "satisfied" if row.satisfied_at else ("review_requested" if row.review_requested_at and row.review_edit_count == 0 else ("reviewed" if row.review_edit_count else "awaiting_employee")),
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
    if len(payload.answers) != 10:
        raise HTTPException(status_code=422, detail="The semiannual form requires exactly 10 answers")
    answers_by_id = {answer.get("question_id"): answer.get("answer") for answer in payload.answers}
    if set(answers_by_id) != {question["id"] for question in SUPERVISOR_APPRAISAL_QUESTIONS}:
        raise HTTPException(status_code=422, detail="The form answers do not match the current appraisal questions")
    snapshot = []
    yes_count = 0
    for question in SUPERVISOR_APPRAISAL_QUESTIONS:
        answer = answers_by_id[question["id"]]
        if question["type"] == "yes_no":
            if not isinstance(answer, bool):
                raise HTTPException(status_code=422, detail="Answer each yes/no question with Yes or No")
            yes_count += int(answer)
        else:
            if not isinstance(answer, str) or len(answer.strip()) < 10 or len(answer) > 3000:
                raise HTTPException(status_code=422, detail="Each open response must contain 10 to 3,000 characters")
            answer = answer.strip()
        snapshot.append({**question, "answer": answer})
    record.answers_snapshot = snapshot
    record.yes_count = yes_count
    record.review_edit_count = 1
    db.commit()
    return {"status": "reviewed", "message": "The appraisal was revised once and returned to the employee."}


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
    latest_reports = {}
    if employee_ids:
        reports = db.query(models.AppraisalReport).filter(
            models.AppraisalReport.employee_id.in_(employee_ids)
        ).order_by(models.AppraisalReport.generation_date.desc()).all()
        for report in reports:
            latest_reports.setdefault(report.employee_id, report)
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
        report = latest_reports.get(employee.employee_id)
        overview.append({"employee_id": employee.employee_id, "full_name": employee.full_name,
                         "role": employee.role, "recorded_at": record.recorded_at if record else None,
                         "trust_score": report.unified_trust_score if report else None,
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

    return db.query(models.AppraisalReport).join(
        models.Employee, models.AppraisalReport.employee_id == models.Employee.employee_id
    ).join(
        models.ImmediateSupervisor, models.Employee.supervisor_id == models.ImmediateSupervisor.supervisor_id
    ).filter(
        models.ImmediateSupervisor.executive_id == executive_id
    ).all()

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
    if current_user["role"] != "executive":
        raise HTTPException(status_code=403, detail="Only executives can trigger compliance overrides")
    if current_user.get("user_id") != payload.executive_id:
        raise HTTPException(status_code=403, detail="Access denied")

    report = db.query(models.AppraisalReport).filter_by(report_id=payload.report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Appraisal report not found")
    belongs_to_region = db.query(models.AppraisalReport).join(
        models.Employee, models.AppraisalReport.employee_id == models.Employee.employee_id
    ).join(
        models.ImmediateSupervisor, models.Employee.supervisor_id == models.ImmediateSupervisor.supervisor_id
    ).filter(
        models.AppraisalReport.report_id == payload.report_id,
        models.ImmediateSupervisor.executive_id == payload.executive_id,
    ).first()
    if not belongs_to_region:
        raise HTTPException(status_code=404, detail="Appraisal report not found")
    belongs_to_region = db.query(models.AppraisalReport).join(
        models.Employee, models.AppraisalReport.employee_id == models.Employee.employee_id
    ).join(
        models.ImmediateSupervisor, models.Employee.supervisor_id == models.ImmediateSupervisor.supervisor_id
    ).filter(
        models.AppraisalReport.report_id == payload.report_id,
        models.ImmediateSupervisor.executive_id == payload.executive_id,
    ).first()
    if not belongs_to_region:
        raise HTTPException(status_code=404, detail="Appraisal report not found")

    report.compliance_override_status = payload.compliance_override_status
    report.overriding_executive_id = payload.executive_id
    db.commit()

    return {
        "status": "success", 
        "message": f"Compliance override updated for report #{payload.report_id}",
        "override_status": payload.compliance_override_status
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

