from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional, Any
import hashlib
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

# ---------------------------------------------------------
# 1. Load Pre-Trained Machine Learning Models
# ---------------------------------------------------------
try:
    rf_model = joblib.load('trust_score_rf_model.pkl')
    tfidf_vectorizer = joblib.load('tfidf_vectorizer.pkl')
    print("✓ Machine Learning pipeline loaded successfully.")
except FileNotFoundError:
    print("Warning: .pkl files not found. Ensure models are saved in the root directory.")




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


QUESTION_BANK_PATH = Path(__file__).resolve().parent / "data" / "appraisal_question_bank.json"
with QUESTION_BANK_PATH.open(encoding="utf-8-sig") as question_bank_file:
    APPRAISAL_QUESTION_BANK = json.load(question_bank_file)


def _build_reflection_questions(record):
    if record is None:
        return random.sample(APPRAISAL_QUESTION_BANK["no_data"], k=3)

    candidates = []
    for metric in QUESTION_METRICS:
        value = _metric_value(record, metric)
        state = _metric_status(record, metric)
        if value is not None and state:
            candidates.append({"metric": metric, "value": value, "state": state.lower()})

    if not candidates:
        return random.sample(APPRAISAL_QUESTION_BANK["no_data"], k=3)

    # Sampling metrics without replacement makes the mix of question states
    # reflect the employee's current Safe/Warning/Danger distribution.
    selected = random.sample(candidates, k=min(3, len(candidates)))
    questions = []
    for item in selected:
        state = item["state"]
        template = random.choice(APPRAISAL_QUESTION_BANK[state])
        questions.append(template.format(
            metric=item["metric"]["label"],
            value=_format_metric_value(item["value"], item["metric"]),
        ))

    while len(questions) < 3:
        questions.append(random.choice(APPRAISAL_QUESTION_BANK["context"]))
    return questions[:3]

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
    return {
        "employee_id": employee_id,
        "questions": _build_reflection_questions(latest_record),
        "based_on_latest_record": latest_record is not None,
        "method": "random question-bank sampling weighted by current KPI states",
    }


# ---------------------------------------------------------
# 5. Supervisor Dashboard Endpoints
# ---------------------------------------------------------
@app.get("/api/v1/supervisors/{supervisor_id}", response_model=schemas.SupervisorResponse)
def get_supervisor(
    supervisor_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] == "employee":
        raise HTTPException(status_code=403, detail="Access denied")

    supervisor = db.query(models.ImmediateSupervisor).filter(
        models.ImmediateSupervisor.supervisor_id == supervisor_id
    ).first()
    if not supervisor:
        raise HTTPException(status_code=404, detail="Supervisor not found")
    return supervisor

@app.get("/api/v1/supervisors/{supervisor_id}/employees", response_model=List[schemas.EmployeeResponse])
def get_supervisor_employees(
    supervisor_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] == "employee":
        raise HTTPException(status_code=403, detail="Access denied")

    return db.query(models.Employee).filter(
        models.Employee.supervisor_id == supervisor_id
    ).all()

@app.get("/api/v1/supervisors/{supervisor_id}/team-reports", response_model=List[schemas.AppraisalReportResponse])
def get_supervisor_team_reports(
    supervisor_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] == "employee":
        raise HTTPException(status_code=403, detail="Access denied")

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
    if current_user["role"] in ("employee", "supervisor"):
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
    if current_user["role"] in ("employee", "supervisor"):
        raise HTTPException(status_code=403, detail="Access denied")

    return db.query(models.AppraisalReport).join(
        models.Employee, models.AppraisalReport.employee_id == models.Employee.employee_id
    ).join(
        models.ImmediateSupervisor, models.Employee.supervisor_id == models.ImmediateSupervisor.supervisor_id
    ).filter(
        models.ImmediateSupervisor.executive_id == executive_id
    ).all()

@app.post("/api/v1/executives/override-compliance")
def execute_compliance_override(
    payload: ExecutiveOverrideRequest, 
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] != "executive":
        raise HTTPException(status_code=403, detail="Only executives can trigger compliance overrides")

    report = db.query(models.AppraisalReport).filter_by(report_id=payload.report_id).first()
    if not report:
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

