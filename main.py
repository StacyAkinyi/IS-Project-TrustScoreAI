from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
import joblib
import numpy as np
from datetime import datetime
from pymongo import MongoClient
from transformers import T5Tokenizer, T5ForConditionalGeneration

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

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    payload = auth.decode_access_token(token)
    if payload is None:
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


# Load your trained model at startup
nlp_tokenizer = T5Tokenizer.from_pretrained("./trustscore_question_model")
nlp_model = T5ForConditionalGeneration.from_pretrained("./trustscore_question_model")

@app.get("/api/v1/employees/{employee_id}/generate-prompt")
def generate_appraisal_prompt(employee_id: int, db: Session = Depends(get_db)):
    # 1. Fetch live telemetry from PostgreSQL
    record = db.query(models.PerformanceRecord).filter(models.PerformanceRecord.employee_id == employee_id).order_by(models.PerformanceRecord.recorded_at.desc()).first()
    
    if not record:
        return {"prompt": "How would you describe your overall performance and challenges this quarter?"}

    # 2. Format telemetry for the model
    input_text = f"loans: {record.loan_volumes}, accuracy: {record.transaction_accuracy}%, errors: {record.error_frequencies}"
    
    # 3. Generate the dynamic question
    input_ids = nlp_tokenizer(input_text, return_tensors="pt").input_ids
    outputs = nlp_model.generate(input_ids, max_length=50)
    generated_question = nlp_tokenizer.decode(outputs[0], skip_special_tokens=True)
    
    return {"prompt": generated_question}    

# ---------------------------------------------------------
# 2. Incoming Request Payloads
# ---------------------------------------------------------
class ComprehensiveAppraisalRequest(BaseModel):
    employee_id: int
    supervisor_id: int
    loan_volumes: int
    transaction_accuracy: float
    workplan_completion: float
    error_frequencies: int
    narrative_text: str

class ExecutiveOverrideRequest(BaseModel):
    report_id: int
    executive_id: int
    compliance_override_status: bool

# ---------------------------------------------------------
# 3. Appraisal & AI Inference Endpoints
# ---------------------------------------------------------
@app.get("/")
def health_check():
    return {"status": "TrustScoreAI System API is active and running."}


@app.post("/api/v1/submit-appraisal")
def submit_appraisal(payload: ComprehensiveAppraisalRequest, db: Session = Depends(get_db)):
    try:
        # 1. Machine Learning & NLP Inference Pipeline
        if 'rf_model' in globals() and 'tfidf_vectorizer' in globals():
            # Structure numerical array
            X_num = np.array([[
                payload.loan_volumes,
                payload.transaction_accuracy,
                payload.workplan_completion,
                payload.error_frequencies
            ]])
            
            # Vectorize the unstructured text
            X_text = tfidf_vectorizer.transform([payload.narrative_text]).toarray()
            
            # Concatenate and predict
            X_combined = np.hstack((X_num, X_text))
            ml_pred = float(rf_model.predict(X_combined)[0])
        else:
            # Fallback logic if models fail to load
            ml_pred = (payload.transaction_accuracy + payload.workplan_completion) / 2.0

        unified_score = round(ml_pred, 2)
        reliability_target = 1 if unified_score >= 70.0 else 0

        # 2. SQL Persistence: Performance Record (DBschema compliant)
        perf_record = models.PerformanceRecord(
            employee_id=payload.employee_id,
            loan_volumes=payload.loan_volumes,
            transaction_accuracy=payload.transaction_accuracy,
            workplan_completion=payload.workplan_completion,
            error_frequencies=payload.error_frequencies,
            feedback_text=payload.narrative_text,
            truthfulness_weight=1.0,
            reliability_target=reliability_target
        )
        db.add(perf_record)
        db.commit()
        db.refresh(perf_record)

        # 3. SQL Persistence: Appraisal Report (DBschema compliant)
        report = models.AppraisalReport(
            employee_id=payload.employee_id,
            unified_trust_score=unified_score,
            compliance_override_status=False
        )
        db.add(report)
        db.commit()
        db.refresh(report)

        # 4. Safe Mongo Logging (Prevents 500 error if Mongo is offline during tests)
        try:
            if 'mongo_db' in globals() and mongo_db is not None:
                mongo_db["unstructured_feedback"].insert_one({
                    "employee_id": payload.employee_id,
                    "supervisor_id": payload.supervisor_id,
                    "narrative_text": payload.narrative_text,
                    "report_id": report.report_id
                })
        except Exception:
            pass  # Fall back gracefully in test environment

        return {
            "status": "success",
            "employee_id": payload.employee_id,
            "report_id": report.report_id,
            "unified_trust_score": unified_score,
            "reliability_target": bool(reliability_target)
        }

    except Exception as e:
        db.rollback() # Rollback SQL transaction on failure
        raise HTTPException(status_code=500, detail=str(e))

# ---------------------------------------------------------
# 4. Employee Dashboard Endpoints
# ---------------------------------------------------------
@app.get("/api/v1/employees/{employee_id}", response_model=schemas.EmployeeResponse)
def get_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] == "employee" and current_user["user_id"] != employee_id:
        raise HTTPException(status_code=403, detail="Access denied")

    employee = db.query(models.Employee).filter(models.Employee.employee_id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee

@app.get("/api/v1/employees/{employee_id}/performance", response_model=List[schemas.PerformanceRecordResponse])
def get_employee_performance(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] == "employee" and current_user["user_id"] != employee_id:
        raise HTTPException(status_code=403, detail="Access denied")

    return db.query(models.PerformanceRecord).filter(
        models.PerformanceRecord.employee_id == employee_id
    ).all()

@app.get("/api/v1/employees/{employee_id}/reports", response_model=List[schemas.AppraisalReportResponse])
def get_employee_reports(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] == "employee" and current_user["user_id"] != employee_id:
        raise HTTPException(status_code=403, detail="Access denied")

    return db.query(models.AppraisalReport).filter(
        models.AppraisalReport.employee_id == employee_id
    ).all()

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
# 7. Authentication Endpoint
# ---------------------------------------------------------
@app.post("/api/v1/login", response_model=schemas.TokenResponse)
def login(credentials: schemas.LoginRequest, db: Session = Depends(get_db)):
    role_tables = [
        (models.Employee, "employee", "employee_id"),
        (models.ImmediateSupervisor, "supervisor", "supervisor_id"),
        (models.ExecutiveManager, "executive", "executive_id"),
    ]

    for model_class, role_name, id_attr in role_tables:
        user = db.query(model_class).filter(model_class.username == credentials.username).first()
        if user and auth.verify_password(credentials.password, user.hashed_password):
            user_id = getattr(user, id_attr)
            token = auth.create_access_token({"user_id": user_id, "role": role_name})
            return {
                "access_token": token,
                "token_type": "bearer",
                "role": role_name,
                "user_id": user_id
            }

    raise HTTPException(status_code=401, detail="Invalid username or password")