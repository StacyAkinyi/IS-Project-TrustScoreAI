import psycopg2
from psycopg2 import sql
import os

# Database Connection Configuration
DB_CONFIG = {
    "dbname": "trust_score_ai_db",
    "user": "postgres",
    "password": "Bambino.0",  
    "host": "127.0.0.1",
    "port": "5432",
    
}

def create_database_and_tables():
    """
    Initializes the PostgreSQL database schema for TrustScoreAI, 
    setting up relational tables for Users, Performance Metrics, and Appraisals.
    """
    try:
        # Step 1: Connect to default postgres database to create our project database if it doesn't exist
        conn = psycopg2.connect(
            dbname="postgres",
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"]
        )
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Check if database exists, create if missing
        cursor.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s", (DB_CONFIG["dbname"],))
        exists = cursor.fetchone()
        if not exists:
            cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(DB_CONFIG["dbname"])))
            print(f"Database '{DB_CONFIG['dbname']}' created successfully!")
        
        cursor.close()
        conn.close()

        # Step 2: Connect to the project database and create relational schema tables
        project_conn = psycopg2.connect(**DB_CONFIG)
        project_cursor = project_conn.cursor()

        # Users Table (Hierarchical roles: Employee, Supervisor, Executive)
        project_cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id SERIAL PRIMARY KEY,
                employee_code VARCHAR(50) UNIQUE NOT NULL,
                full_name VARCHAR(100) NOT NULL,
                role VARCHAR(30) CHECK (role IN ('Employee', 'Supervisor', 'Executive')) NOT NULL,
                branch_location VARCHAR(100) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Quantitative KPIs and Qualitative Review Logs Table
        project_cursor.execute("""
            CREATE TABLE IF NOT EXISTS performance_records (
                record_id SERIAL PRIMARY KEY,
                employee_code VARCHAR(50) REFERENCES users(employee_code),
                loan_volumes INT NOT NULL,
                transaction_accuracy FLOAT NOT NULL,
                workplan_completion FLOAT NOT NULL,
                error_frequencies INT NOT NULL,
                feedback_text TEXT,
                truthfulness_weight FLOAT DEFAULT 1.0,
                reliability_target INT CHECK (reliability_target IN (0, 1)),
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        project_conn.commit()
        project_cursor.close()
        project_conn.close()
        print("PostgreSQL relational schema tables ('users', 'performance_records') initialized successfully!")

    except Exception as e:
        print(f"Database connection or schema creation failed: {e}")
        print("Tip: Make sure your PostgreSQL service is running and credentials in DB_CONFIG are accurate.")

if __name__ == "__main__":
    create_database_and_tables()