from pydantic import BaseModel
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

# --- Processing & Appraisal Schemas ---
class PerformanceRecordCreate(BaseModel):
    employee_id: int
    loan_volumes: int
    transaction_accuracy: float
    workplan_completion: float
    error_frequencies: int
    feedback_text: Optional[str] = None
    truthfulness_weight: float = 1.0
    reliability_target: int

class UnstructuredFeedbackCreate(BaseModel):
    employee_id: int
    supervisor_id: Optional[int] = None
    author_employee_id: Optional[int] = None
    narrative_text: str

class AppraisalReportResponse(BaseModel):
    report_id: int
    employee_id: int
    unified_trust_score: float
    compliance_override_status: bool
    overriding_executive_id: Optional[int] = None
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
class EmployeeResponse(BaseModel):
    id: int
    supervisor_id: int
    full_name: str
    role: str
    branch_location: str

    class Config:
        from_attributes = True


class PerformanceRecordResponse(BaseModel):
    record_id: int
    employee_id: int
    loan_volumes: int
    transaction_accuracy: float
    workplan_completion: float
    error_frequencies: int
    feedback_text: Optional[str] = None
    reliability_target: int

    class Config:
        from_attributes = True  
              
class SupervisorResponse(BaseModel):
    id: int
    executive_id: int
    full_name: str
    department_code: str

    class Config:
        from_attributes = True        

class ExecutiveResponse(BaseModel):
    id: int
    full_name: str
    oversight_region: str

    class Config:
        from_attributes = True
class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: int
                