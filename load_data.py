import pandas as pd
from database import SessionLocal
import models
import auth

db = SessionLocal()

try:
    # ==========================================
    # 1. Executive Managers (no dependencies)
    # ==========================================
    print("Loading executive managers...")
    df_exec = pd.read_csv('synthetic_executive_manager.csv')
    for _, row in df_exec.iterrows():
        db.add(models.ExecutiveManager(
            id=int(row['executive_id']),
            full_name=row['full_name'],
            oversight_region=row['oversight_region'],
            username=f"exec{int(row['executive_id'])}",
            hashed_password=auth.hash_password("password123")
        ))
    db.commit()

    # ==========================================
    # 2. Immediate Supervisors (depend on executives)
    # ==========================================
    print("Loading immediate supervisors...")
    df_sup = pd.read_csv('synthetic_immediate_supervisor.csv')
    for _, row in df_sup.iterrows():
        db.add(models.ImmediateSupervisor(
            id=int(row['supervisor_id']),
            executive_id=int(row['executive_id']),
            full_name=row['full_name'],
            department_code=row['department_code'],
            username=f"sup{int(row['supervisor_id'])}",
            hashed_password=auth.hash_password("password123")
        ))
    db.commit()

    # ==========================================
    # 3. Employees (depend on supervisors)
    # ==========================================
    print("Loading employees...")
    df_emp = pd.read_csv('synthetic_employee.csv')
    for _, row in df_emp.iterrows():
        db.add(models.Employee(
            id=int(row['employee_id']),
            supervisor_id=int(row['supervisor_id']),
            full_name=row['full_name'],
            role=row['role'],
            branch_location=row['branch_location'],
            username=f"emp{int(row['employee_id'])}",
            hashed_password=auth.hash_password("password123")
        ))
    db.commit()

    # ==========================================
    # 4. Performance Records (depend on employees)
    # ==========================================
    print("Loading performance records...")
    df_perf = pd.read_csv('synthetic_performance_records.csv')
    for _, row in df_perf.iterrows():
        db.add(models.PerformanceRecord(
            record_id=int(row['record_id']),
            employee_id=int(row['employee_id']),
            loan_volumes=int(row['loan_volumes']),
            transaction_accuracy=float(row['transaction_accuracy']),
            workplan_completion=float(row['workplan_completion']),
            error_frequencies=int(row['error_frequencies']),
            feedback_text=row['feedback_text'] if pd.notna(row['feedback_text']) else None,
            truthfulness_weight=float(row['truthfulness_weight']),
            reliability_target=int(row['reliability_target'])
        ))
    db.commit()

    # ==========================================
    # 5. Unstructured Feedback (depend on employees)
    # ==========================================
    print("Loading unstructured feedback...")
    df_fb = pd.read_csv('synthetic_unstructured_feedback.csv')
    for _, row in df_fb.iterrows():
        db.add(models.UnstructuredFeedback(
            feedback_id=int(row['feedback_id']),
            employee_id=int(row['employee_id']),
            supervisor_id=int(row['supervisor_id']) if pd.notna(row['supervisor_id']) else None,
            author_employee_id=int(row['author_employee_id']) if pd.notna(row['author_employee_id']) else None,
            narrative_text=row['narrative_text'],
            sentiment_polarity_value=float(row['sentiment_polarity_value'])
        ))
    db.commit()

    print("All synthetic data loaded successfully into PostgreSQL!")

except Exception as e:
    db.rollback()
    print(f"Error loading data: {e}")
    raise
finally:
    db.close()