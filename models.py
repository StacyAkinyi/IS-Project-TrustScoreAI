from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class ExecutiveManager(Base):
    __tablename__ = "executive_managers"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    oversight_region = Column(String, nullable=False)
    username = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)

    supervisors = relationship("ImmediateSupervisor", back_populates="executive")


class ImmediateSupervisor(Base):
    __tablename__ = "immediate_supervisors"

    id = Column(Integer, primary_key=True, index=True)
    executive_id = Column(Integer, ForeignKey("executive_managers.id"), nullable=False)
    full_name = Column(String, nullable=False)
    department_code = Column(String, nullable=False)
    username = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)

    executive = relationship("ExecutiveManager", back_populates="supervisors")
    employees = relationship("Employee", back_populates="supervisor")


class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    supervisor_id = Column(Integer, ForeignKey("immediate_supervisors.id"), nullable=False)
    full_name = Column(String, nullable=False)
    role = Column(String, nullable=False)
    branch_location = Column(String, nullable=False)
    username = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)

    supervisor = relationship("ImmediateSupervisor", back_populates="employees")
    performance_records = relationship("PerformanceRecord", back_populates="employee")
    feedback_entries = relationship(
        "UnstructuredFeedback",
        back_populates="employee",
        foreign_keys="UnstructuredFeedback.employee_id"
    )


class PerformanceRecord(Base):
    __tablename__ = "performance_records"

    record_id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    loan_volumes = Column(Integer, nullable=False)
    transaction_accuracy = Column(Float, nullable=False)
    workplan_completion = Column(Float, nullable=False)
    error_frequencies = Column(Integer, nullable=False)
    feedback_text = Column(Text, nullable=True)
    truthfulness_weight = Column(Float, default=1.0)
    reliability_target = Column(Integer, nullable=False)

    employee = relationship("Employee", back_populates="performance_records")


class UnstructuredFeedback(Base):
    __tablename__ = "unstructured_feedback"

    feedback_id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    supervisor_id = Column(Integer, ForeignKey("immediate_supervisors.id"), nullable=True)
    author_employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    narrative_text = Column(Text, nullable=False)
    sentiment_polarity_value = Column(Float, nullable=True)

    employee = relationship("Employee", back_populates="feedback_entries", foreign_keys=[employee_id])

class AppraisalReport(Base):
    __tablename__ = "appraisal_reports"

    report_id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    unified_trust_score = Column(Float, nullable=False)
    compliance_override_status = Column(Boolean, default=False)
    overriding_executive_id = Column(Integer, ForeignKey("executive_managers.id"), nullable=True)
    generation_date = Column(DateTime, default=datetime.utcnow)


class AppraisalSourceMapping(Base):
    __tablename__ = "appraisal_source_mappings"

    mapping_id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("appraisal_reports.report_id"), nullable=False)
    record_id = Column(Integer, ForeignKey("performance_records.record_id"), nullable=True)
    feedback_id = Column(Integer, ForeignKey("unstructured_feedback.feedback_id"), nullable=True)
    