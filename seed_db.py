import pandas as pd
from pymongo import MongoClient
from sqlalchemy import text
from database import engine, SessionLocal, Base
import models
import auth

MONGO_URI = "mongodb://localhost:27017/"
MONGO_DB_NAME = "trustscore_mongo"

def seed_databases():
    print("Wiping PostgreSQL schema with CASCADE to clear legacy foreign key dependencies...")
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE;"))
        conn.execute(text("CREATE SCHEMA public;"))

    print("Recreating clean relational database schema...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    mongo_client = MongoClient(MONGO_URI)
    mongo_db = mongo_client[MONGO_DB_NAME]

    try:
        # 1. Executive Managers
        print("Loading executive managers into PostgreSQL...")
        df_exec = pd.read_csv('synthetic_executive_manager.csv')
        for _, row in df_exec.iterrows():
            db.add(models.ExecutiveManager(
                executive_id=int(row['executive_id']),
                full_name=row['full_name'],
                oversight_region=row['oversight_region'],
                username=f"exec{int(row['executive_id'])}",
                hashed_password=auth.hash_password("password123")
            ))
        db.commit()

        # 2. Immediate Supervisors
        print("Loading immediate supervisors into PostgreSQL...")
        df_sup = pd.read_csv('synthetic_immediate_supervisor.csv')
        for _, row in df_sup.iterrows():
            db.add(models.ImmediateSupervisor(
                supervisor_id=int(row['supervisor_id']),
                executive_id=int(row['executive_id']),
                full_name=row['full_name'],
                department_code=row['department_code'],
                username=f"sup{int(row['supervisor_id'])}",
                hashed_password=auth.hash_password("password123")
            ))
        db.commit()

        # 3. Employees
        print("Loading employees into PostgreSQL...")
        df_emp = pd.read_csv('synthetic_employee.csv')
        for _, row in df_emp.iterrows():
            db.add(models.Employee(
                employee_id=int(row['employee_id']),
                supervisor_id=int(row['supervisor_id']),
                full_name=row['full_name'],
                role=row['role'],
                branch_location=row['branch_location'],
                username=f"emp{int(row['employee_id'])}",
                hashed_password=auth.hash_password("password123")
            ))
        db.commit()

        # 4. Performance Records
        print("Loading performance records into PostgreSQL...")
        df_perf = pd.read_csv('synthetic_performance_records.csv')
        for _, row in df_perf.iterrows():
            feedback_val = row['feedback_text'] if 'feedback_text' in row and pd.notna(row['feedback_text']) else None
            truth_weight = float(row['truthfulness_weight']) if 'truthfulness_weight' in row and pd.notna(row['truthfulness_weight']) else 1.0
            rel_target = int(row['reliability_target']) if 'reliability_target' in row and pd.notna(row['reliability_target']) else 1

            db.add(models.PerformanceRecord(
                record_id=int(row['record_id']),
                employee_id=int(row['employee_id']),
                loan_volumes=int(row['loan_volumes']),
                transaction_accuracy=float(row['transaction_accuracy']),
                workplan_completion=float(row['workplan_completion']),
                error_frequencies=int(row['error_frequencies']),
                feedback_text=feedback_val,
                truthfulness_weight=truth_weight,
                reliability_target=rel_target
            ))
        db.commit()

        # 5. Unstructured Feedback (PostgreSQL)
        print("Loading unstructured feedback into PostgreSQL...")
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

        # 6. Unstructured Feedback Documents (MongoDB Store)
        print("Loading unstructured feedback documents into MongoDB...")
        feedback_collection = mongo_db['unstructured_feedback']
        feedback_collection.delete_many({})
        mongo_docs = df_fb.where(pd.notnull(df_fb), None).to_dict(orient='records')
        if mongo_docs:
            feedback_collection.insert_many(mongo_docs)

        print("\n✓ Database seeding completed successfully across PostgreSQL and MongoDB!")

    except Exception as e:
        db.rollback()
        print(f"Error seeding databases: {e}")
        raise
    finally:
        db.close()
        mongo_client.close()

if __name__ == "__main__":
    seed_databases()