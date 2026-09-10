import pandas as pd
from sqlalchemy import create_engine
from pymongo import MongoClient

# Database Connection Configurations
POSTGRES_URI = "postgresql://postgres:Bambino.0@localhost:5433/trust_score_ai_db"
MONGO_URI = "mongodb://localhost:27017/"
MONGO_DB_NAME = "trustscore_mongo"

def seed_databases():
    print("Initializing database connections...")
    engine = create_engine(POSTGRES_URI)
    mongo_client = MongoClient(MONGO_URI)
    mongo_db = mongo_client[MONGO_DB_NAME]

    # ==========================================
    # 1. Populate PostgreSQL Relational Database
    # ==========================================
    print("\n--- Seeding PostgreSQL Database ---")
    
    # Load synthetic CSV files
    df_exec = pd.read_csv('synthetic_executive_manager.csv')
    df_sup = pd.read_csv('synthetic_immediate_supervisor.csv')
    df_emp = pd.read_csv('synthetic_employee.csv')
    df_kpi = pd.read_csv('synthetic_performance_records.csv')

    # Seed in foreign key dependency order
    df_exec.to_sql('executive_manager', con=engine, if_exists='append', index=False)
    print("✓ Populated table: executive_manager")

    df_sup.to_sql('immediate_supervisor', con=engine, if_exists='append', index=False)
    print("✓ Populated table: immediate_supervisor")

    df_emp.to_sql('employee', con=engine, if_exists='append', index=False)
    print("✓ Populated table: employee")

    # Filter out ML training targets to match exact performance_records PostgreSQL schema
    pg_schema_columns = [
        'record_id', 'employee_id', 'loan_volumes', 'transaction_accuracy',
        'workplan_completion', 'error_frequencies', 'feedback_text',
        'truthfulness_weight', 'reliability_target', 'recorded_at'
    ]
    
    # Ensure optional fields exist if omitted from generation
    if 'feedback_text' not in df_kpi.columns:
        df_kpi['feedback_text'] = None

    df_kpi_sql = df_kpi[[col for col in pg_schema_columns if col in df_kpi.columns]]
    df_kpi_sql.to_sql('performance_records', con=engine, if_exists='append', index=False)
    print("✓ Populated table: performance_records")

    # ==========================================
    # 2. Populate MongoDB Document Database
    # ==========================================
    print("\n--- Seeding MongoDB Document Store ---")
    
    df_feedback = pd.read_csv('synthetic_unstructured_feedback.csv')

    # Convert pandas NaNs to None for BSON null compliance
    feedback_docs = df_feedback.where(pd.notnull(df_feedback), None).to_dict(orient='records')

    # Target collection and reset previous data
    feedback_collection = mongo_db['unstructured_feedback']
    feedback_collection.delete_many({}) 
    
    if feedback_docs:
        feedback_collection.insert_many(feedback_docs)
        print(f"✓ Populated collection 'unstructured_feedback' ({len(feedback_docs)} documents inserted)")

    print("\nBoth PostgreSQL and MongoDB databases have been seeded successfully!")

if __name__ == "__main__":
    seed_databases()