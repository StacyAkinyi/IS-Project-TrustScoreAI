from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Employee(Base):
    __tablename__ = "employees"
    __table_args__ = (
        CheckConstraint(
            "user_type IN ('employee', 'supervisor', 'executive')",
            name="ck_employees_user_type",
        ),
    )

    employee_id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(160), nullable=False)
    email = Column(String(254), unique=True, index=True, nullable=False)
    password_hashed = Column(String(255), nullable=False)
    department = Column(String(100), nullable=False)
    role = Column(String(100), nullable=False)
    user_type = Column(String(20), nullable=False, default="employee")
    # The FK is added after table creation because supervisor profiles also
    # point back to their Employee row through ImmediateSupervisor.emp_id.
    supervisor_id = Column(
        Integer,
        ForeignKey("immediate_supervisors.sup_id", use_alter=True, name="fk_employees_supervisor"),
        nullable=True,
    )
    is_active = Column(Boolean, nullable=False, default=True)
    auth_token_version = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    supervisor_profile = relationship(
        "ImmediateSupervisor",
        foreign_keys=[supervisor_id],
        back_populates="staff",
    )
    executive_profile = relationship(
        "ExecutiveManager",
        foreign_keys="ExecutiveManager.emp_id",
        back_populates="employee_profile",
        uselist=False,
    )
    performance_records = relationship(
        "PerformanceRecord", back_populates="employee", cascade="all, delete-orphan"
    )
    feedback_entries = relationship(
        "UnstructuredFeedback",
        back_populates="employee",
        foreign_keys="UnstructuredFeedback.employee_id",
        cascade="all, delete-orphan",
    )
    appraisal_reports = relationship(
        "AppraisalReport", back_populates="employee", cascade="all, delete-orphan"
    )
    password_reset_tokens = relationship(
        "PasswordResetToken", back_populates="employee", cascade="all, delete-orphan"
    )

    @property
    def branch_location(self) -> str | None:
        return self.supervisor_profile.branch_code if self.supervisor_profile else None


class ExecutiveManager(Base):
    __tablename__ = "executive_managers"

    executive_id = Column(Integer, primary_key=True, index=True)
    emp_id = Column(Integer, ForeignKey("employees.employee_id"), unique=True, nullable=False)
    oversight_region = Column(String(100), nullable=False)

    employee_profile = relationship(
        "Employee", foreign_keys=[emp_id], back_populates="executive_profile"
    )
    supervisors = relationship("ImmediateSupervisor", back_populates="executive")
    overridden_reports = relationship("AppraisalReport", back_populates="overriding_executive")

    @property
    def full_name(self) -> str | None:
        return self.employee_profile.full_name if self.employee_profile else None


class ImmediateSupervisor(Base):
    __tablename__ = "immediate_supervisors"

    # Attribute name keeps existing API code readable; database column follows the diagram.
    supervisor_id = Column("sup_id", Integer, primary_key=True, index=True)
    branch_code = Column(String(30), nullable=False)
    executive_id = Column(Integer, ForeignKey("executive_managers.executive_id"), nullable=False)
    emp_id = Column(Integer, ForeignKey("employees.employee_id"), unique=True, nullable=False)

    executive = relationship("ExecutiveManager", back_populates="supervisors")
    employee_profile = relationship("Employee", foreign_keys=[emp_id], uselist=False)
    staff = relationship(
        "Employee", foreign_keys="Employee.supervisor_id", back_populates="supervisor_profile"
    )
    feedback_entries = relationship("UnstructuredFeedback", back_populates="supervisor")

    @property
    def full_name(self) -> str | None:
        return self.employee_profile.full_name if self.employee_profile else None

    @property
    def department_code(self) -> str | None:
        return self.employee_profile.department if self.employee_profile else None


class PerformanceRecord(Base):
    __tablename__ = "performance_records"
    __table_args__ = (
        CheckConstraint("loan_volumes >= 0", name="ck_performance_loan_volumes_nonnegative"),
        CheckConstraint("transaction_accuracy BETWEEN 0 AND 100", name="ck_performance_accuracy_range"),
        CheckConstraint("workplan_completion BETWEEN 0 AND 120", name="ck_performance_workplan_range"),
        CheckConstraint("error_frequencies >= 0", name="ck_performance_errors_nonnegative"),
        CheckConstraint("reliability_target IN (0, 1)", name="ck_performance_reliability_target"),
    )

    record_id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.employee_id"), nullable=False, index=True)
    loan_volumes = Column(Integer, nullable=False)
    transaction_accuracy = Column(Float, nullable=False)
    workplan_completion = Column(Float, nullable=False)
    error_frequencies = Column(Integer, nullable=False)
    # Additional banking KPIs from the proposal extend the ERD's core measures.
    loan_processing_turnaround_hours = Column(Float, nullable=False)
    accounts_opened = Column(Integer, nullable=False)
    non_performing_credit_pct = Column(Float, nullable=False)
    task_deadline_fulfillment_pct = Column(Float, nullable=False)
    cash_reconciliation_errors = Column(Integer, nullable=False)
    customer_satisfaction = Column(Float, nullable=False)
    compliance_incidents = Column(Integer, nullable=False)
    complaint_resolution_rate_pct = Column(Float, nullable=False)
    digital_channel_adoption_pct = Column(Float, nullable=False)
    feedback_text = Column(Text, nullable=True)
    truthfulness_weight = Column(Float, nullable=False, default=1.0)
    reliability_target = Column(Integer, nullable=False)
    recorded_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)

    employee = relationship("Employee", back_populates="performance_records")
    appraisal_mappings = relationship("AppraisalSourceMapping", back_populates="performance_record")


class UnstructuredFeedback(Base):
    __tablename__ = "unstructured_feedback"

    feedback_id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.employee_id"), nullable=False, index=True)
    supervisor_id = Column(Integer, ForeignKey("immediate_supervisors.sup_id"), nullable=True)
    author_employee_id = Column(Integer, ForeignKey("employees.employee_id"), nullable=True)
    narrative_text = Column(Text, nullable=False)
    sentiment_polarity_value = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    employee = relationship(
        "Employee", back_populates="feedback_entries", foreign_keys=[employee_id]
    )
    author = relationship("Employee", foreign_keys=[author_employee_id])
    supervisor = relationship("ImmediateSupervisor", back_populates="feedback_entries")
    appraisal_mappings = relationship(
        "AppraisalSourceMapping", back_populates="unstructured_feedback"
    )


class AppraisalReport(Base):
    __tablename__ = "appraisal_reports"
    __table_args__ = (
        CheckConstraint("unified_trust_score BETWEEN 0 AND 100", name="ck_report_score_range"),
    )

    report_id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.employee_id"), nullable=False, index=True)
    unified_trust_score = Column(Float, nullable=False)
    report_status = Column(String(30), nullable=False, default="generated")
    compliance_override_status = Column(Boolean, nullable=False, default=False)
    overriding_executive_id = Column(
        Integer, ForeignKey("executive_managers.executive_id"), nullable=True
    )
    generation_date = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)

    employee = relationship("Employee", back_populates="appraisal_reports")
    overriding_executive = relationship("ExecutiveManager", back_populates="overridden_reports")
    source_mappings = relationship(
        "AppraisalSourceMapping", back_populates="report", cascade="all, delete-orphan"
    )


class AppraisalSourceMapping(Base):
    __tablename__ = "appraisal_source_mappings"
    __table_args__ = (
        CheckConstraint(
            "(record_id IS NOT NULL AND feedback_id IS NULL) OR "
            "(record_id IS NULL AND feedback_id IS NOT NULL)",
            name="ck_source_mapping_one_source",
        ),
    )

    mapping_id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("appraisal_reports.report_id"), nullable=False, index=True)
    record_id = Column(Integer, ForeignKey("performance_records.record_id"), nullable=True)
    feedback_id = Column(Integer, ForeignKey("unstructured_feedback.feedback_id"), nullable=True)

    report = relationship("AppraisalReport", back_populates="source_mappings")
    performance_record = relationship("PerformanceRecord", back_populates="appraisal_mappings")
    unstructured_feedback = relationship(
        "UnstructuredFeedback", back_populates="appraisal_mappings"
    )


class PasswordResetToken(Base):
    """Hashed, expiring one-time tokens used by the upcoming password-reset flow."""

    __tablename__ = "password_reset_tokens"

    reset_id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.employee_id"), nullable=False, index=True)
    token_hashed = Column(String(255), unique=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    consumed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    employee = relationship("Employee", back_populates="password_reset_tokens")
