from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from fastapi import FastAPI

# Assuming your models and schemas are saved in `models.py` and `schemas.py`
from models import User, KPIMetric, NarrativeFeedback, TrustGrade, SessionLocal
from schemas import (
    UserCreate, UserResponse, 
    KPICreate, KPIResponse, 
    NarrativeFeedbackCreate, NarrativeFeedbackResponse, 
    TrustGradeCreate, TrustGradeResponse
)
app = FastAPI(title="TrustScoreAI API", version="1.0")

# Mount the router we created earlier
router = APIRouter(prefix="/api/v1", tags=["TrustScoreAI Core API"])
app.include_router(router)

# ==========================================
# Database Dependency
# ==========================================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==========================================
# 1. User Endpoints (Hierarchical Access)
# ==========================================
@router.post("/users/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    # Check if email already exists
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # In a real app, hash the password before saving!
    new_user = User(**user.model_dump())
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.get("/users/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

# ==========================================
# 2. KPI Metrics Endpoints (Quantitative Data)
# ==========================================
@router.post("/kpis/", response_model=KPIResponse, status_code=status.HTTP_201_CREATED)
def log_kpi_metric(kpi: KPICreate, db: Session = Depends(get_db)):
    # Verify user exists
    user = db.query(User).filter(User.user_id == kpi.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    new_kpi = KPIMetric(**kpi.model_dump())
    db.add(new_kpi)
    db.commit()
    db.refresh(new_kpi)
    return new_kpi

@router.get("/users/{user_id}/kpis/", response_model=List[KPIResponse])
def get_employee_kpis(user_id: int, db: Session = Depends(get_db)):
    """Fetches continuous quantitative banking features like loan volumes for a specific employee."""
    kpis = db.query(KPIMetric).filter(KPIMetric.user_id == user_id).all()
    return kpis

# ==========================================
# 3. Narrative Feedback Endpoints (Qualitative Data)
# ==========================================
@router.post("/feedback/", response_model=NarrativeFeedbackResponse, status_code=status.HTTP_201_CREATED)
def submit_feedback(feedback: NarrativeFeedbackCreate, db: Session = Depends(get_db)):
    # This endpoint captures multi-source review narratives for the NLP pipeline
    new_feedback = NarrativeFeedback(**feedback.model_dump())
    db.add(new_feedback)
    db.commit()
    db.refresh(new_feedback)
    return new_feedback

@router.get("/users/{user_id}/feedback/", response_model=List[NarrativeFeedbackResponse])
def get_employee_feedback(user_id: int, db: Session = Depends(get_db)):
    feedback_records = db.query(NarrativeFeedback).filter(NarrativeFeedback.user_id == user_id).all()
    return feedback_records

# ==========================================
# 4. Trust Grade Endpoints (ML Outputs)
# ==========================================
@router.post("/trust-grades/", response_model=TrustGradeResponse, status_code=status.HTTP_201_CREATED)
def generate_trust_grade(grade: TrustGradeCreate, db: Session = Depends(get_db)):
    """Stores the final computed reliability score from the Random Forest engine."""
    new_grade = TrustGrade(**grade.model_dump())
    db.add(new_grade)
    db.commit()
    db.refresh(new_grade)
    return new_grade

@router.get("/users/{user_id}/trust-grades/", response_model=List[TrustGradeResponse])
def get_employee_trust_grades(user_id: int, db: Session = Depends(get_db)):
    """Returns the unified trust scores for the hierarchical dashboards."""
    grades = db.query(TrustGrade).filter(TrustGrade.user_id == user_id).all()
    return grades