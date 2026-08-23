from sqlalchemy import create_engine, Column, Integer, String, Boolean, Date, Numeric, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import declarative_base, relationship, sessionmaker


DATABASE_URL = "postgresql://postgres:Bambino.0@localhost:5433/trustscoreai_db"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class User(Base):
    __tablename__ = 'tbl_users'

    user_id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False) # 'Employee', 'Supervisor', 'Executive'
    branch_code = Column(String(20))
    department = Column(String(50))
    hire_date = Column(Date)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    kpis = relationship("KPIMetric", back_populates="user", cascade="all, delete-orphan")
    trust_grades = relationship("TrustGrade", back_populates="user", cascade="all, delete-orphan")
    feedback_received = relationship("NarrativeFeedback", foreign_keys='NarrativeFeedback.user_id', back_populates="employee", cascade="all, delete-orphan")
    feedback_given = relationship("NarrativeFeedback", foreign_keys='NarrativeFeedback.evaluator_id', back_populates="evaluator")

class KPIMetric(Base):
    __tablename__ = 'tbl_kpis'

    metric_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('tbl_users.user_id', ondelete="CASCADE"), nullable=False)
    evaluation_period = Column(Date, nullable=False)
    loan_processing_volumes = Column(Numeric(10, 2), default=0.00)
    account_creation_volumes = Column(Integer, default=0)
    cash_reconciliation_error_freq = Column(Numeric(5, 2), default=0.00)
    non_performing_credit_pct = Column(Numeric(5, 2), default=0.00)
    task_deadline_fulfilment_rate = Column(Numeric(5, 2), default=0.00)
    daily_ledger_balancing_speed = Column(Numeric(5, 2), default=0.00)
    transaction_accuracy_rate = Column(Numeric(5, 2), default=0.00)
    target_achievement_rate = Column(Numeric(5, 2), default=0.00)
    recorded_at = Column(DateTime, server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="kpis")

class NarrativeFeedback(Base):
    __tablename__ = 'tbl_narrativefeedback'

    feedback_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('tbl_users.user_id', ondelete="CASCADE"), nullable=False)
    evaluator_id = Column(Integer, ForeignKey('tbl_users.user_id', ondelete="SET NULL"))
    feedback_date = Column(DateTime, server_default=func.now())
    raw_narrative = Column(Text)
    supervisor_notes = Column(Text)
    peer_evaluations = Column(Text)
    compliance_behavior_notes = Column(Text)
    behavioral_integrity_notes = Column(Text)
    professional_accountability_notes = Column(Text)
    collaboration_notes = Column(Text)
    sentiment_processed_status = Column(Boolean, default=False)

    # Relationships
    employee = relationship("User", foreign_keys=[user_id], back_populates="feedback_received")
    evaluator = relationship("User", foreign_keys=[evaluator_id], back_populates="feedback_given")

class TrustGrade(Base):
    __tablename__ = 'tbl_trustgrades'

    report_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('tbl_users.user_id', ondelete="CASCADE"), nullable=False)
    report_generation_date = Column(DateTime, server_default=func.now())
    final_reliability_score = Column(Numeric(5, 2), nullable=False)
    ml_precision_weights = Column(Numeric(5, 4))
    parsed_sentiment_bounds = Column(Numeric(5, 4))
    classification_accuracy = Column(Numeric(5, 4))
    macro_f1_score = Column(Numeric(5, 4))
    root_mean_squared_error = Column(Numeric(5, 4))
    dashboard_visibility_tier = Column(String(20), default='Executive')
    model_version = Column(String(50))
    executive_approval_status = Column(Boolean, default=False)

    # Relationships
    user = relationship("User", back_populates="trust_grades")

# Run this to create the tables in the database if they don't exist yet
if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created successfully!")
