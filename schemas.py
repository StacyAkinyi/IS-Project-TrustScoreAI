from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional
from datetime import date, datetime
from decimal import Decimal

# ==========================================
# 1. User Schemas
# ==========================================
class UserBase(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    # Restricting roles to the three specific tiers needed for the hierarchical dashboard
    role: str = Field(..., pattern="^(Employee|Supervisor|Executive)$") 
    branch_code: Optional[str] = None
    department: Optional[str] = None
    hire_date: Optional[date] = None
    is_active: bool = True

class UserCreate(UserBase):
    password: str # Required only when creating a user, never returned in responses

class UserResponse(UserBase):
    user_id: int
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True) # Enables reading from SQLAlchemy models

# ==========================================
# 2. KPI Metrics Schemas
# ==========================================
class KPIBase(BaseModel):
    evaluation_period: date
    loan_processing_volumes: Decimal = Field(default=Decimal('0.00'), max_digits=10, decimal_places=2)
    account_creation_volumes: int = Field(default=0)
    cash_reconciliation_error_freq: Decimal = Field(default=Decimal('0.00'), max_digits=5, decimal_places=2)
    non_performing_credit_pct: Decimal = Field(default=Decimal('0.00'), max_digits=5, decimal_places=2)
    task_deadline_fulfilment_rate: Decimal = Field(default=Decimal('0.00'), max_digits=5, decimal_places=2)
    daily_ledger_balancing_speed: Decimal = Field(default=Decimal('0.00'), max_digits=5, decimal_places=2)
    transaction_accuracy_rate: Decimal = Field(default=Decimal('0.00'), max_digits=5, decimal_places=2)
    target_achievement_rate: Decimal = Field(default=Decimal('0.00'), max_digits=5, decimal_places=2)

class KPICreate(KPIBase):
    user_id: int

class KPIResponse(KPIBase):
    metric_id: int
    user_id: int
    recorded_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

# ==========================================
# 3. Narrative Feedback Schemas
# ==========================================
class NarrativeFeedbackBase(BaseModel):
    raw_narrative: Optional[str] = None
    supervisor_notes: Optional[str] = None
    peer_evaluations: Optional[str] = None
    compliance_behavior_notes: Optional[str] = None
    behavioral_integrity_notes: Optional[str] = None
    professional_accountability_notes: Optional[str] = None
    collaboration_notes: Optional[str] = None

class NarrativeFeedbackCreate(NarrativeFeedbackBase):
    user_id: int
    evaluator_id: int

class NarrativeFeedbackResponse(NarrativeFeedbackBase):
    feedback_id: int
    user_id: int
    evaluator_id: Optional[int]
    feedback_date: datetime
    sentiment_processed_status: bool
    
    model_config = ConfigDict(from_attributes=True)

# ==========================================
# 4. Trust Grade / ML Appraisal Schemas
# ==========================================
class TrustGradeBase(BaseModel):
    final_reliability_score: Decimal = Field(..., max_digits=5, decimal_places=2)
    ml_precision_weights: Optional[Decimal] = Field(None, max_digits=5, decimal_places=4)
    parsed_sentiment_bounds: Optional[Decimal] = Field(None, max_digits=5, decimal_places=4)
    classification_accuracy: Optional[Decimal] = Field(None, max_digits=5, decimal_places=4)
    macro_f1_score: Optional[Decimal] = Field(None, max_digits=5, decimal_places=4)
    root_mean_squared_error: Optional[Decimal] = Field(None, max_digits=5, decimal_places=4)
    dashboard_visibility_tier: str = Field(default="Executive")
    model_version: Optional[str] = None
    executive_approval_status: bool = False

class TrustGradeCreate(TrustGradeBase):
    user_id: int

class TrustGradeResponse(TrustGradeBase):
    report_id: int
    user_id: int
    report_generation_date: datetime
    
    model_config = ConfigDict(from_attributes=True)