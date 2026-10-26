from datetime import datetime, timezone

from sqlalchemy import UniqueConstraint
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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Employee(Base):
    __tablename__ = "employees"
    __table_args__ = (
        CheckConstraint(
            "user_type IN ('employee', 'supervisor', 'executive', 'admin')",
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
    # Set only for base employees. Supervisor and executive accounts are also
    # employee identity rows, but their reporting relationships use their own
    # role-specific profile tables rather than this employee-to-supervisor link.
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
        CheckConstraint("data_source IN ('real_anonymized', 'synthetic_demo', 'unknown')", name="ck_performance_data_source"),
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
    data_source = Column(String(30), nullable=False, default="unknown")
    recorded_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)

    employee = relationship("Employee", back_populates="performance_records")
    appraisal_mappings = relationship("AppraisalSourceMapping", back_populates="performance_record")


class UnstructuredFeedback(Base):
    __tablename__ = "unstructured_feedback"
    __table_args__ = (
        CheckConstraint("data_source IN ('real_anonymized', 'synthetic_demo', 'unknown')", name="ck_feedback_data_source"),
    )

    feedback_id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.employee_id"), nullable=False, index=True)
    supervisor_id = Column(Integer, ForeignKey("immediate_supervisors.sup_id"), nullable=True)
    author_employee_id = Column(Integer, ForeignKey("employees.employee_id"), nullable=True)
    supervisor_appraisal_id = Column(
        Integer, ForeignKey("supervisor_appraisals.appraisal_id", ondelete="SET NULL"), nullable=True, index=True
    )
    narrative_text = Column(Text, nullable=False)
    question_snapshot = Column(JSONB, nullable=True)
    sentiment_polarity_value = Column(Float, nullable=True)
    data_source = Column(String(30), nullable=False, default="unknown")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    employee = relationship(
        "Employee", back_populates="feedback_entries", foreign_keys=[employee_id]
    )
    author = relationship("Employee", foreign_keys=[author_employee_id])
    supervisor = relationship("ImmediateSupervisor", back_populates="feedback_entries")
    appraisal_mappings = relationship(
        "AppraisalSourceMapping", back_populates="unstructured_feedback"
    )


class SupervisorAppraisal(Base):
    __tablename__ = "supervisor_appraisals"
    __table_args__ = (
        UniqueConstraint("employee_id", "period_code", "form_number", name="uq_supervisor_appraisal_employee_period_form"),
        CheckConstraint("yes_count BETWEEN 0 AND 5", name="ck_supervisor_appraisal_yes_count"),
        CheckConstraint("form_number IN (1, 2)", name="ck_supervisor_appraisal_form_number"),
    )

    appraisal_id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.employee_id"), nullable=False, index=True)
    supervisor_id = Column(Integer, ForeignKey("immediate_supervisors.sup_id"), nullable=False, index=True)
    period_code = Column(String(7), nullable=False)
    form_number = Column(Integer, nullable=False, default=1)
    answers_snapshot = Column(JSONB, nullable=False)
    yes_count = Column(Integer, nullable=False)
    employee_notified_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    review_request_text = Column(Text, nullable=True)
    review_requested_at = Column(DateTime(timezone=True), nullable=True)
    review_edit_count = Column(Integer, nullable=False, default=0)
    satisfied_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class AppraisalMeeting(Base):
    __tablename__ = "appraisal_meetings"
    __table_args__ = (
        UniqueConstraint("appraisal_id", name="uq_appraisal_meeting_per_appraisal"),
        CheckConstraint(
            "status IN ('pending_confirmation', 'confirmed')",
            name="ck_appraisal_meeting_status",
        ),
    )

    meeting_id = Column(Integer, primary_key=True, index=True)
    appraisal_id = Column(Integer, ForeignKey("supervisor_appraisals.appraisal_id"), nullable=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.employee_id"), nullable=False, index=True)
    supervisor_id = Column(Integer, ForeignKey("immediate_supervisors.sup_id"), nullable=False, index=True)
    scheduled_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(30), nullable=False, default="pending_confirmation")
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


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
    compliance_override_reason = Column(Text, nullable=True)
    compliance_override_updated_at = Column(DateTime(timezone=True), nullable=True)
    generation_date = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)

    employee = relationship("Employee", back_populates="appraisal_reports")
    overriding_executive = relationship("ExecutiveManager", back_populates="overridden_reports")
    source_mappings = relationship(
        "AppraisalSourceMapping", back_populates="report", cascade="all, delete-orphan"
    )


class FeedbackClassification(Base):
    """Stored automatic model classifications for supervisor appraisal answers."""
    __tablename__ = "feedback_classifications"
    __table_args__ = (
        CheckConstraint(
            "source_type IN ('supervisor_appraisal', 'employee_followup')",
            name="ck_feedback_classification_source_type",
        ),
        CheckConstraint(
            "category IN ('communication', 'collaboration', 'compliance_awareness', 'learning_development')",
            name="ck_feedback_classification_category",
        ),
        CheckConstraint(
            "predicted_direction IN ('negative', 'positive', 'mixed', 'neutral')",
            name="ck_feedback_classification_predicted_direction",
        ),
        CheckConstraint(
            "review_status IN ('pending', 'confirmed', 'excluded', 'auto_classified', 'superseded')",
            name="ck_feedback_classification_review_status",
        ),
        CheckConstraint(
            "confirmed_direction IS NULL OR confirmed_direction IN ('negative', 'positive', 'mixed', 'neutral')",
            name="ck_feedback_classification_confirmed_direction",
        ),
        CheckConstraint(
            "(supervisor_appraisal_id IS NOT NULL AND feedback_id IS NULL) OR "
            "(supervisor_appraisal_id IS NULL AND feedback_id IS NOT NULL)",
            name="ck_feedback_classification_one_source",
        ),
        UniqueConstraint(
            "supervisor_appraisal_id", "item_key", "category",
            name="uq_feedback_classification_supervisor_item_category",
        ),
        UniqueConstraint(
            "feedback_id", "item_key", "category",
            name="uq_feedback_classification_employee_item_category",
        ),
    )

    classification_id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.employee_id"), nullable=False, index=True)
    source_type = Column(String(30), nullable=False)
    supervisor_appraisal_id = Column(
        Integer, ForeignKey("supervisor_appraisals.appraisal_id", ondelete="CASCADE"), nullable=True
    )
    feedback_id = Column(
        Integer, ForeignKey("unstructured_feedback.feedback_id", ondelete="CASCADE"), nullable=True
    )
    item_key = Column(String(120), nullable=False)
    category = Column(String(40), nullable=False)
    statement_text = Column(Text, nullable=False)
    predicted_direction = Column(String(20), nullable=False)
    confidence = Column(Float, nullable=False)
    probabilities = Column(JSONB, nullable=False)
    review_status = Column(String(20), nullable=False, default="auto_classified", index=True)
    is_current = Column(Boolean, nullable=False, default=False, index=True)
    confirmed_direction = Column(String(20), nullable=True)
    reviewed_by_employee_id = Column(Integer, ForeignKey("employees.employee_id"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    model_version = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)


class TrustScoreRun(Base):
    """Period-level KPI and automatically classified supervisor-feedback scores."""
    __tablename__ = "trust_score_runs"
    __table_args__ = (
        CheckConstraint(
            "period_type IN ('quarterly', 'semiannual', 'annual')",
            name="ck_trust_score_run_period_type",
        ),
        CheckConstraint(
            "score_status IN ('ready', 'awaiting_review', 'incomplete')",
            name="ck_trust_score_run_status",
        ),
        CheckConstraint(
            "trust_score IS NULL OR trust_score BETWEEN 0 AND 100",
            name="ck_trust_score_run_score_range",
        ),
        UniqueConstraint(
            "employee_id", "period_type", "period_code",
            name="uq_trust_score_run_employee_period",
        ),
    )

    run_id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.employee_id"), nullable=False, index=True)
    generated_by_employee_id = Column(Integer, ForeignKey("employees.employee_id"), nullable=False)
    period_type = Column(String(20), nullable=False)
    period_code = Column(String(12), nullable=False, index=True)
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    kpi_groups = Column(JSONB, nullable=False)
    feedback_groups = Column(JSONB, nullable=False)
    data_coverage = Column(JSONB, nullable=False)
    trust_score = Column(Float, nullable=True)
    score_status = Column(String(20), nullable=False, default="incomplete", index=True)
    generated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)


class AIPerformanceReport(Base):
    __tablename__ = "ai_performance_reports"
    __table_args__ = (
        CheckConstraint("period_type IN ('quarterly', 'semiannual', 'annual')", name="ck_ai_report_period_type"),
        CheckConstraint("report_status IN ('ai_draft', 'human_reviewed')", name="ck_ai_report_status"),
    )

    report_id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.employee_id"), nullable=False, index=True)
    generated_by_employee_id = Column(Integer, ForeignKey("employees.employee_id"), nullable=False, index=True)
    period_type = Column(String(20), nullable=False)
    period_code = Column(String(12), nullable=False, index=True)
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    telemetry_groups = Column(JSONB, nullable=False)
    feedback_dimensions = Column(JSONB, nullable=False)
    narrative = Column(JSONB, nullable=False)
    data_coverage = Column(JSONB, nullable=False)
    report_status = Column(String(30), nullable=False, default="ai_draft")
    model_name = Column(String(100), nullable=False)
    generated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)


class ComplianceOverrideAudit(Base):
    __tablename__ = "compliance_override_audit"

    audit_id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("appraisal_reports.report_id"), nullable=False, index=True)
    executive_id = Column(Integer, ForeignKey("executive_managers.executive_id"), nullable=False, index=True)
    previous_status = Column(Boolean, nullable=False)
    new_status = Column(Boolean, nullable=False)
    justification = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)


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
