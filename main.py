from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import joblib
import numpy as np
import psycopg2

app = FastAPI(
    title="TrustScoreAI Backend API",
    description="Automated Employee Appraisal & Professional Reliability Scoring Engine for the Banking Sector",
    version="1.0.0"
)

# Database Connection Settings
DB_CONFIG = {
    "dbname": "trust_score_ai_db",
    "user": "postgres",
    "password": "Bambino.0",
    "host": "127.0.0.1",
    "port": "5432",
    "sslmode": "disable"
}

# Load Pre-trained Machine Learning Model and TF-IDF Vectorizer
try:
    rf_model = joblib.load('trust_score_rf_model.pkl')
    tfidf_vectorizer = joblib.load('tfidf_vectorizer.pkl')
    print("Machine learning models loaded successfully into FastAPI memory.")
except Exception as e:
    print(f"Warning: Model files not found. Please run train_models.py first! Error: {e}")

# Define Request Body Structure (Pydantic Model)
class AppraisalRequest(BaseModel):
    employee_code: str
    loan_volumes: int
    transaction_accuracy: float
    workplan_completion: float
    error_frequencies: int
    feedback_text: str

@app.get("/")
def home():
    return {"message": "Welcome to the TrustScoreAI API engine. Documentation is available at /docs"}

@app.post("/evaluate-employee/")
def evaluate_employee(data: AppraisalRequest):
    """
    Ingests live employee quantitative KPIs and qualitative feedback,
    computes truth-weighted NLP and Random Forest reliability classifications,
    stores the results in PostgreSQL, and returns the evaluation outcome.
    """
    try:
        # 1. Format Numerical Features
        X_num = np.array([[data.loan_volumes, data.transaction_accuracy, 
                           data.workplan_completion, data.error_frequencies]])
        
        # 2. Process Text Feedback via TF-IDF Vectorizer
        X_text = tfidf_vectorizer.transform([data.feedback_text]).toarray()
        
        # 3. Combine Features for Random Forest Prediction
        X_combined = np.hstack((X_num, X_text))
        
        # 4. Predict Reliability Class (1 = Reliable, 0 = Needs Improvement)
        prediction = int(rf_model.predict(X_combined)[0])
        probability = float(np.max(rf_model.predict_proba(X_combined)))
        
        # Determine status label
        status_label = "Reliable / High-Performing" if prediction == 1 else "Needs Improvement / Intervention Required"

        # 5. Persist record into PostgreSQL database
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO performance_records 
            (employee_code, loan_volumes, transaction_accuracy, workplan_completion, error_frequencies, feedback_text, reliability_target)
            VALUES (%s, %s, %s, %s, %s, %s, %s);
        """, (
            data.employee_code, 
            data.loan_volumes, 
            data.transaction_accuracy, 
            data.workplan_completion, 
            data.error_frequencies, 
            data.feedback_text, 
            prediction
        ))
        
        conn.commit()
        cursor.close()
        conn.close()

        return {
            "status": "success",
            "employee_code": data.employee_code,
            "prediction_class": prediction,
            "evaluation_result": status_label,
            "confidence_score": round(probability * 100, 2),
            "message": "Appraisal record processed and securely logged to PostgreSQL database."
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))