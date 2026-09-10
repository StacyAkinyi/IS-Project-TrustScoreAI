from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
import joblib
import numpy as np
from datetime import datetime
from typing import List



# Import your custom modules
import models
import schemas
import auth
from database import engine, get_db
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    payload = auth.decode_access_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload  # contains {"user_id": ..., "role": ..., "exp": ...}

# Initialize all database tables defined in models.py
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="TrustScoreAI System API",
    description="Backend gateway routing quantitative KPIs and qualitative text to the ML engine."
)

# ---------------------------------------------------------
# 1. Load Pre-Trained Machine Learning Models
# ---------------------------------------------------------
try:
    rf_model = joblib.load('trust_score_rf_model.pkl')
    tfidf_vectorizer = joblib.load('tfidf_vectorizer.pkl')
    print("Machine Learning pipeline loaded successfully.")
except FileNotFoundError:
    print("Warning: .pkl files not found. Ensure your models are trained and saved in the root directory.")


# ---------------------------------------------------------
# 2. Define the Incoming Request Payload
# ---------------------------------------------------------
class ComprehensiveAppraisalRequest(BaseModel):
    employee_id: int
    supervisor_id: int
    loan_volumes: int
    transaction_accuracy: float
    workplan_completion: float
    error_frequencies: int
    narrative_text: str


# ---------------------------------------------------------
# 3. API Endpoints
# ---------------------------------------------------------
@app.get("/")
def health_check():
    return {"status": "TrustScoreAI System API is active and running."}

@app.post("/api/v1/submit-appraisal")
def submit_comprehensive_appraisal(
    data: ComprehensiveAppraisalRequest, 
    db: Session = Depends(get_db)
):
    """
    Ingests performance metrics and qualitative text, passes them through the 
    Random Forest and NLP pipelines, and logs the transactional data across 
    the PostgreSQL hierarchical schema.
    """
    try:
        # --- A. Machine Learning & NLP Inference ---
        # 1. Structure the numerical array
        X_num = np.array([[
            data.loan_volumes, 
            data.transaction_accuracy, 
            data.workplan_completion, 
            data.error_frequencies
        ]])
        
        # 2. Vectorize the unstructured text
        X_text = tfidf_vectorizer.transform([data.narrative_text]).toarray()
        
        # 3. Concatenate and predict
        X_combined = np.hstack((X_num, X_text))
        prediction = int(rf_model.predict(X_combined)[0])
        probability = float(np.max(rf_model.predict_proba(X_combined)))
        unified_score = round(probability * 100, 2)


        # --- B. Database Persistence Layer (SQLAlchemy ORM) ---
        
        # 1. Insert into performance_records
        new_record = models.PerformanceRecord(
            employee_id=data.employee_id,
            loan_volumes=data.loan_volumes,
            transaction_accuracy=data.transaction_accuracy,
            workplan_completion=data.workplan_completion,
            error_frequencies=data.error_frequencies,
            feedback_text=data.narrative_text,
            reliability_target=prediction
        )
        db.add(new_record)
        db.commit()
        db.refresh(new_record)

        # 2. Insert into unstructured_feedback
        new_feedback = models.UnstructuredFeedback(
            employee_id=data.employee_id,
            supervisor_id=data.supervisor_id,
            narrative_text=data.narrative_text,
            sentiment_polarity_value=probability
        )
        db.add(new_feedback)
        db.commit()
        db.refresh(new_feedback)

        # 3. Insert into appraisal_reports
        new_report = models.AppraisalReport(
            employee_id=data.employee_id,
            unified_trust_score=unified_score,
            compliance_override_status=False
        )
        db.add(new_report)
        db.commit()
        db.refresh(new_report)

        # 4. Insert into the junction table (appraisal_source_mapping)
        new_mapping = models.AppraisalSourceMapping(
            report_id=new_report.report_id,
            record_id=new_record.record_id,
            feedback_id=new_feedback.feedback_id
        )
        db.add(new_mapping)
        db.commit()

        # --- C. Return the Final Response ---
        return {
            "status": "success",
            "report_id": new_report.report_id,
            "employee_id": data.employee_id,
            "unified_trust_score": unified_score,
            "prediction_class": prediction,
            "message": "Appraisal processed and securely logged across relational tables."
        }

    except Exception as e:
        db.rollback()
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
    # Employees can only view themselves; supervisors/executives can view any employee
    if current_user["role"] == "employee" and current_user["user_id"] != employee_id:
        raise HTTPException(status_code=403, detail="You can only view your own profile")

    employee = db.query(models.Employee).filter(models.Employee.id == employee_id).first()
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
        raise HTTPException(status_code=403, detail="You can only view your own performance records")

    records = db.query(models.PerformanceRecord).filter(
        models.PerformanceRecord.employee_id == employee_id
    ).all()
    return records


@app.get("/api/v1/employees/{employee_id}/reports", response_model=List[schemas.AppraisalReportResponse])
def get_employee_reports(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] == "employee" and current_user["user_id"] != employee_id:
        raise HTTPException(status_code=403, detail="You can only view your own reports")

    reports = db.query(models.AppraisalReport).filter(
        models.AppraisalReport.employee_id == employee_id
    ).all()
    return reports  

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
        raise HTTPException(status_code=403, detail="Employees cannot access supervisor data")
    if current_user["role"] == "supervisor" and current_user["user_id"] != supervisor_id:
        raise HTTPException(status_code=403, detail="You can only view your own profile")

    supervisor = db.query(models.ImmediateSupervisor).filter(
        models.ImmediateSupervisor.id == supervisor_id
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
        raise HTTPException(status_code=403, detail="Employees cannot access supervisor data")
    if current_user["role"] == "supervisor" and current_user["user_id"] != supervisor_id:
        raise HTTPException(status_code=403, detail="You can only view your own team")

    employees = db.query(models.Employee).filter(
        models.Employee.supervisor_id == supervisor_id
    ).all()
    return employees


@app.get("/api/v1/supervisors/{supervisor_id}/team-reports", response_model=List[schemas.AppraisalReportResponse])
def get_supervisor_team_reports(
    supervisor_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] == "employee":
        raise HTTPException(status_code=403, detail="Employees cannot access supervisor data")
    if current_user["role"] == "supervisor" and current_user["user_id"] != supervisor_id:
        raise HTTPException(status_code=403, detail="You can only view your own team's reports")

    reports = db.query(models.AppraisalReport).join(
        models.Employee, models.AppraisalReport.employee_id == models.Employee.id
    ).filter(
        models.Employee.supervisor_id == supervisor_id
    ).all()
    return reports


# ---------------------------------------------------------
# 6. Executive Dashboard Endpoints
# ---------------------------------------------------------

@app.get("/api/v1/executives/{executive_id}", response_model=schemas.ExecutiveResponse)
def get_executive(
    executive_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] in ("employee", "supervisor"):
        raise HTTPException(status_code=403, detail="Only executives can access this data")
    if current_user["role"] == "executive" and current_user["user_id"] != executive_id:
        raise HTTPException(status_code=403, detail="You can only view your own profile")

    executive = db.query(models.ExecutiveManager).filter(
        models.ExecutiveManager.id == executive_id
    ).first()
    if not executive:
        raise HTTPException(status_code=404, detail="Executive not found")
    return executive


@app.get("/api/v1/executives/{executive_id}/supervisors", response_model=List[schemas.SupervisorResponse])
def get_executive_supervisors(
    executive_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] in ("employee", "supervisor"):
        raise HTTPException(status_code=403, detail="Only executives can access this data")
    if current_user["role"] == "executive" and current_user["user_id"] != executive_id:
        raise HTTPException(status_code=403, detail="You can only view your own org")

    supervisors = db.query(models.ImmediateSupervisor).filter(
        models.ImmediateSupervisor.executive_id == executive_id
    ).all()
    return supervisors


@app.get("/api/v1/executives/{executive_id}/employees", response_model=List[schemas.EmployeeResponse])
def get_executive_employees(
    executive_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] in ("employee", "supervisor"):
        raise HTTPException(status_code=403, detail="Only executives can access this data")
    if current_user["role"] == "executive" and current_user["user_id"] != executive_id:
        raise HTTPException(status_code=403, detail="You can only view your own org")

    employees = db.query(models.Employee).join(
        models.ImmediateSupervisor, models.Employee.supervisor_id == models.ImmediateSupervisor.id
    ).filter(
        models.ImmediateSupervisor.executive_id == executive_id
    ).all()
    return employees


@app.get("/api/v1/executives/{executive_id}/reports", response_model=List[schemas.AppraisalReportResponse])
def get_executive_reports(
    executive_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] in ("employee", "supervisor"):
        raise HTTPException(status_code=403, detail="Only executives can access this data")
    if current_user["role"] == "executive" and current_user["user_id"] != executive_id:
        raise HTTPException(status_code=403, detail="You can only view your own org")

    reports = db.query(models.AppraisalReport).join(
        models.Employee, models.AppraisalReport.employee_id == models.Employee.id
    ).join(
        models.ImmediateSupervisor, models.Employee.supervisor_id == models.ImmediateSupervisor.id
    ).filter(
        models.ImmediateSupervisor.executive_id == executive_id
    ).all()
    return reports

# ---------------------------------------------------------
# 7. Authentication
# ---------------------------------------------------------

@app.post("/api/v1/login", response_model=schemas.TokenResponse)
def login(credentials: schemas.LoginRequest, db: Session = Depends(get_db)):
    role_tables = [
        (models.Employee, "employee"),
        (models.ImmediateSupervisor, "supervisor"),
        (models.ExecutiveManager, "executive"),
    ]

    for model_class, role_name in role_tables:
        user = db.query(model_class).filter(model_class.username == credentials.username).first()
        if user and auth.verify_password(credentials.password, user.hashed_password):
            token = auth.create_access_token({"user_id": user.id, "role": role_name})
            return {
                "access_token": token,
                "token_type": "bearer",
                "role": role_name,
                "user_id": user.id
            }

    raise HTTPException(status_code=401, detail="Invalid username or password")