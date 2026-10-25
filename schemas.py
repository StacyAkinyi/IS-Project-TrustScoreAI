from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

# --- Hierarchical User Schemas ---
class ExecutiveManagerCreate(BaseModel):
    full_name: str
    oversight_region: str

class ImmediateSupervisorCreate(BaseModel):
    executive_id: int
    full_name: str
    department_code: str

class EmployeeCreate(BaseModel):
    supervisor_id: int
    full_name: str
    role: str
    branch_location: str

# --- Response Schemas (Primary Keys Aligned with DB Schema) ---
class EmployeeResponse(BaseModel):
    employee_id: int
    supervisor_id: Optional[int] = None
    full_name: str
    role: str
    branch_location: Optional[str] = None

    class Config:
        from_attributes = True

class SupervisorResponse(BaseModel):
    supervisor_id: int
    executive_id: int
    full_name: str
    department_code: str
    branch_code: Optional[str] = None
    team_kpi_averages: list[dict] = []
    team_size: int = 0
    employees_with_telemetry: int = 0
    supervisor_appraisal_count: int = 0

    class Config:
        from_attributes = True

class ExecutiveResponse(BaseModel):
    executive_id: int
    full_name: str
    oversight_region: str

    class Config:
        from_attributes = True

# --- Processing & Appraisal Schemas ---
class AppraisalInput(BaseModel):
    employee_id: int
    supervisor_id: int
    loan_volumes: int
    transaction_accuracy: float
    workplan_completion: float
    error_frequencies: int
    narrative_text: str

class PerformanceRecordCreate(BaseModel):
    employee_id: int
    loan_volumes: int
    transaction_accuracy: float
    workplan_completion: float
    error_frequencies: int
    feedback_text: Optional[str] = None
    truthfulness_weight: float = 1.0
    reliability_target: int

class PerformanceRecordResponse(BaseModel):
    record_id: int
    employee_id: int
    loan_volumes: int
    transaction_accuracy: float
    workplan_completion: float
    error_frequencies: int
    loan_processing_turnaround_hours: float
    accounts_opened: int
    non_performing_credit_pct: float
    task_deadline_fulfillment_pct: float
    cash_reconciliation_errors: int
    customer_satisfaction: float
    compliance_incidents: int
    complaint_resolution_rate_pct: float
    digital_channel_adoption_pct: float
    feedback_text: Optional[str] = None
    truthfulness_weight: float
    reliability_target: int
    recorded_at: datetime

    class Config:
        from_attributes = True

class UnstructuredFeedbackCreate(BaseModel):
    employee_id: int
    supervisor_id: Optional[int] = None
    author_employee_id: Optional[int] = None
    narrative_text: str

class AppraisalReportResponse(BaseModel):
    report_id: int
    employee_id: int
    unified_trust_score: float
    report_status: str = "generated"
    compliance_override_status: bool
    overriding_executive_id: Optional[int] = None
    compliance_override_reason: Optional[str] = None
    compliance_override_updated_at: Optional[datetime] = None
    override_audit: list[dict] = Field(default_factory=list)
    generation_date: datetime

    class Config:
        from_attributes = True

class AppraisalSourceMappingCreate(BaseModel):
    report_id: int
    record_id: Optional[int] = None
    feedback_id: Optional[int] = None

class AppraisalSourceMappingResponse(BaseModel):
    mapping_id: int
    report_id: int
    record_id: Optional[int] = None
    feedback_id: Optional[int] = None

    class Config:
        from_attributes = True

# --- Authentication Schemas ---
class SupervisorAppraisalSubmission(BaseModel):
    employee_id: int
    answers: list[dict]
    form_number: int = 1

class ReviewClarificationRequest(BaseModel):
    message: str


class ScheduleAppraisalMeeting(BaseModel):
    scheduled_at: datetime

class ExecutiveOverrideRequest(BaseModel):
    report_id: int
    executive_id: int
    compliance_override_status: bool
    justification: str = Field(min_length=10, max_length=2000)

class LoginRequest(BaseModel):
    email: str
    password: str

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: int
    email: str

class AdminEmployeeResponse(BaseModel):
    employee_id: int
    full_name: str
    email: str
    department: str
    role: str
    user_type: str
    is_active: bool
    supervisor_id: Optional[int] = None
    supervisor_name: Optional[str] = None
    supervisor_profile_id: Optional[int] = None
    executive_id: Optional[int] = None
    executive_name: Optional[str] = None
    branch_code: Optional[str] = None
    oversight_region: Optional[str] = None
    created_at: datetime


class AdminEmployeeCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=12, max_length=72)
    department: str = Field(min_length=2, max_length=100)
    role: str = Field(min_length=2, max_length=100)
    user_type: str
    supervisor_id: Optional[int] = Field(default=None, ge=1)
    executive_id: Optional[int] = Field(default=None, ge=1)
    branch_code: Optional[str] = Field(default=None, max_length=30)
    oversight_region: Optional[str] = Field(default=None, max_length=100)


class AdminEmployeeUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=160)
    email: Optional[str] = Field(default=None, min_length=5, max_length=254)
    password: Optional[str] = Field(default=None, min_length=12, max_length=72)
    department: Optional[str] = Field(default=None, min_length=2, max_length=100)
    role: Optional[str] = Field(default=None, min_length=2, max_length=100)
    is_active: Optional[bool] = None
    supervisor_id: Optional[int] = Field(default=None, ge=1)
    executive_id: Optional[int] = Field(default=None, ge=1)
    branch_code: Optional[str] = Field(default=None, max_length=30)
    oversight_region: Optional[str] = Field(default=None, max_length=100)
