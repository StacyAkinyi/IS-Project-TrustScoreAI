import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import numpy as np

from main import app
from database import get_db, Base
import auth
import models

# ---------------------------------------------------------
# Test Database & Client Fixtures
# ---------------------------------------------------------
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_and_teardown_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    
    # Seed Test Users
    hashed_pw = auth.get_password_hash("password123")
    
    exec_user = models.ExecutiveManager(
        executive_id=1,
        username="exec_stacy",
        hashed_password=hashed_pw,
        full_name="Stacy Exec",
        oversight_region="Nairobi Region"
    )
    sup_user = models.ImmediateSupervisor(
        supervisor_id=1,
        executive_id=1,
        username="sup_john",
        hashed_password=hashed_pw,
        full_name="John Supervisor",
        department_code="DEPT_A"
    )
    emp_user = models.Employee(
        employee_id=1,
        supervisor_id=1,
        username="emp_alice",
        hashed_password=hashed_pw,
        full_name="Alice Employee",
        role="Loan Officer",
        branch_location="NBO-Central"
    )
    
    db.add_all([exec_user, sup_user, emp_user])
    db.commit()
    db.close()
    
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def employee_token():
    return auth.create_access_token({"user_id": 1, "role": "employee"})

@pytest.fixture
def supervisor_token():
    return auth.create_access_token({"user_id": 1, "role": "supervisor"})

@pytest.fixture
def executive_token():
    return auth.create_access_token({"user_id": 1, "role": "executive"})

# ---------------------------------------------------------
# Unit & Integration Test Cases
# ---------------------------------------------------------

def test_health_check():
    """Verify system status endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "TrustScoreAI System API is active and running."}


def test_login_success():
    """Verify user authentication and JWT generation."""
    response = client.post("/api/v1/login", json={
        "username": "emp_alice",
        "password": "password123"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["role"] == "employee"
    assert data["user_id"] == 1


def test_login_failure():
    """Verify invalid credentials return 401 Unauthorized."""
    response = client.post("/api/v1/login", json={
        "username": "emp_alice",
        "password": "wrongpassword"
    })
    assert response.status_code == 401


def test_submit_comprehensive_appraisal():
    """Verify ML pipeline vectorization, SQL/Mongo persistence, and score calculation."""
    payload = {
        "employee_id": 1,
        "supervisor_id": 1,
        "loan_volumes": 120,
        "transaction_accuracy": 96.5,
        "workplan_completion": 92.0,
        "error_frequencies": 1,
        "narrative_text": "Consistently exceeds monthly volume targets and strictly adheres to KYC protocols."
    }
    
    response = client.post("/api/v1/submit-appraisal", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["employee_id"] == 1
    assert "unified_trust_score" in data
    assert "reliability_target" in data


def test_role_based_access_employee_dashboard(employee_token):
    """Verify employees can access their own profile."""
    headers = {"Authorization": f"Bearer {employee_token}"}
    response = client.get("/api/v1/employees/1", headers=headers)
    assert response.status_code == 200
    assert response.json()["full_name"] == "Alice Employee"


def test_role_based_access_unauthorized_profile(employee_token):
    """Verify employees cannot view other employees' profiles (403 Forbidden)."""
    headers = {"Authorization": f"Bearer {employee_token}"}
    response = client.get("/api/v1/employees/99", headers=headers)
    assert response.status_code == 403


def test_executive_compliance_override(executive_token):
    """Verify executives can execute compliance overrides."""
    # First submit an appraisal to create a report
    appraisal_payload = {
        "employee_id": 1,
        "supervisor_id": 1,
        "loan_volumes": 80,
        "transaction_accuracy": 85.0,
        "workplan_completion": 70.0,
        "error_frequencies": 4,
        "narrative_text": "Struggles with meeting volume deadlines and minor KYC compliance oversight noted."
    }
    app_res = client.post("/api/v1/submit-appraisal", json=appraisal_payload)
    report_id = app_res.json()["report_id"]

    # Trigger executive override
    override_payload = {
        "report_id": report_id,
        "executive_id": 1,
        "compliance_override_status": True
    }
    headers = {"Authorization": f"Bearer {executive_token}"}
    response = client.post("/api/v1/executives/override-compliance", json=override_payload, headers=headers)
    
    assert response.status_code == 200
    assert response.json()["override_status"] is True


def test_non_executive_cannot_override_compliance(employee_token):
    """Verify non-executive roles cannot trigger compliance overrides."""
    override_payload = {
        "report_id": 1,
        "executive_id": 1,
        "compliance_override_status": True
    }
    headers = {"Authorization": f"Bearer {employee_token}"}
    response = client.post("/api/v1/executives/override-compliance", json=override_payload, headers=headers)
    assert response.status_code == 403






if __name__ == "__main__":
    import pytest
    import sys
    sys.exit(pytest.main(["-v", "test_main.py"]))