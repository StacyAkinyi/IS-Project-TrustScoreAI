import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta
from niafaker import NiaFaker

# Set random seeds for reproducibility
np.random.seed(42)
random.seed(42)

fake = NiaFaker("ke", seed=42)

# ==========================================
# Configuration & Constants
# ==========================================
NUM_EXECUTIVES = 3
NUM_SUPERVISORS = 15
NUM_EMPLOYEES = 200
NUM_MONTHS = 12

# Exactly 10 Branches
BRANCHES = [
    'NBO-Central', 'NBO-Westlands', 'NBO-Upperhill', 'MSA-Island', 
    'MSA-Nyali', 'KSM-Central', 'NKU-CBD', 'ELD-Core', 
    'KTL-Branch', 'THK-Industrial'
]

# Exactly 10 Departments
DEPARTMENTS = [
    'Retail Banking', 'Credit Processing', 'Operations', 'Compliance', 
    'Treasury', 'IT Risk', 'Customer Service', 'Wealth Management', 
    'Corporate Banking', 'Trade Finance'
]

REGIONS = ['Nairobi Region', 'Coast Region', 'Western Region']
EMPLOYEE_ROLES = ['Teller', 'Loan Officer', 'Customer Success', 'Analyst']

# Mock textual snippets for NLP dataset
POSITIVE_NOTES = [
    "Consistently meets targets with high integrity.",
    "Shows strong ethical compliance and teamwork.",
    "Excellent collaboration skills during month-end reconciliation."
]
NEGATIVE_NOTES = [
    "Struggles with meeting deadlines.",
    "Minor KYC compliance oversight noted.",
    "Needs improvement in peer collaboration and ledger speed."
]

# ==========================================
# 1. Generate Hierarchical Users
# ==========================================
print("Generating hierarchical user data...")

# A. Executive Managers
executives_data = []
for exec_id in range(1, NUM_EXECUTIVES + 1):
    executives_data.append({
        'executive_id': exec_id,
        'full_name': fake.name(),
        'oversight_region': random.choice(REGIONS)
    })
df_executives = pd.DataFrame(executives_data)

# B. Immediate Supervisors
supervisors_data = []
for sup_id in range(1, NUM_SUPERVISORS + 1):
    supervisors_data.append({
        'supervisor_id': sup_id,
        'executive_id': random.randint(1, NUM_EXECUTIVES),
        'full_name': fake.name(),
        'department_code': random.choice(DEPARTMENTS)
    })
df_supervisors = pd.DataFrame(supervisors_data)

# C. Employees
employees_data = []
for emp_id in range(1, NUM_EMPLOYEES + 1):
    employees_data.append({
        'employee_id': emp_id,
        'supervisor_id': random.randint(1, NUM_SUPERVISORS),
        'full_name': fake.name(),
        'role': random.choice(EMPLOYEE_ROLES),
        'branch_location': random.choice(BRANCHES)
    })
df_employees = pd.DataFrame(employees_data)

# Export User Tables
df_executives.to_csv('synthetic_executive_manager.csv', index=False)
df_supervisors.to_csv('synthetic_immediate_supervisor.csv', index=False)
df_employees.to_csv('synthetic_employee.csv', index=False)


# ==========================================
# 2. Generate Quantitative Metrics (performance_records)
# ==========================================
print("Generating performance_records.csv...")
kpi_data = []
record_id = 1
start_date = datetime(2025, 1, 1)

for emp_id in df_employees['employee_id']:
    # Generate multiple records per employee
    for month_offset in range(NUM_MONTHS):
        eval_date = start_date + pd.DateOffset(months=month_offset)
        
        # Simulating operational variables
        loan_vols = max(0, int(np.random.normal(loc=120, scale=30)))
        tx_accuracy = max(50.0, min(100.0, np.random.normal(loc=95.0, scale=4.0)))
        wp_completion = max(40.0, min(100.0, np.random.normal(loc=88.0, scale=10.0)))
        err_freq = max(0, int(np.random.poisson(lam=2)))
        
        # Compute target (1 = Reliable, 0 = Needs Improvement)
        score = (tx_accuracy * 0.4) + (wp_completion * 0.4) - (err_freq * 5)
        reliability_target = 1 if score > 75 else 0

        # Adding optional feedback directly to the record 
        inline_feedback = random.choice(POSITIVE_NOTES + NEGATIVE_NOTES) if random.random() > 0.5 else None

        kpi_data.append({
            'record_id': record_id,
            'employee_id': emp_id,
            'loan_volumes': loan_vols,
            'transaction_accuracy': round(tx_accuracy, 2),
            'workplan_completion': round(wp_completion, 2),
            'error_frequencies': err_freq,
            'feedback_text': inline_feedback,
            'truthfulness_weight': round(random.uniform(0.8, 1.0), 2),
            'reliability_target': reliability_target,
            'recorded_at': eval_date.strftime('%Y-%m-%d %H:%M:%S')
        })
        record_id += 1

df_kpis = pd.DataFrame(kpi_data)
df_kpis.to_csv('synthetic_performance_records.csv', index=False)


# ==========================================
# 3. Generate Qualitative Text (unstructured_feedback)
# ==========================================
print("Generating unstructured_feedback.csv...")
feedback_data = []
feedback_id = 1

for emp_id in df_employees['employee_id']:
    # Each employee gets 2-3 pieces of unstructured feedback
    num_reviews = random.randint(2, 3)
    
    # Type-safe native Python extraction (Bypasses pandas .values linter errors)
    emp_supervisor = next(emp['supervisor_id'] for emp in employees_data if emp['employee_id'] == emp_id)

    for _ in range(num_reviews):
        is_peer_review = random.choice([True, False])
        
        if is_peer_review:
            # Peer review: supervisor_id is None, author_employee_id has a value
            sup_id_val = None
            author_id_val = random.choice([e['employee_id'] for e in employees_data if e['employee_id'] != emp_id])
        else:
            # Manager review: supervisor_id has value, author_employee_id is None
            sup_id_val = emp_supervisor
            author_id_val = None

        narrative = random.choice(POSITIVE_NOTES + NEGATIVE_NOTES)
        # Mock sentiment polarity (-1.0 to 1.0)
        sentiment = round(random.uniform(0.5, 1.0) if narrative in POSITIVE_NOTES else random.uniform(-1.0, 0.0), 2)

        feedback_data.append({
            'feedback_id': feedback_id,
            'employee_id': emp_id,
            'supervisor_id': sup_id_val,
            'author_employee_id': author_id_val,
            'narrative_text': narrative,
            'sentiment_polarity_value': sentiment
        })
        feedback_id += 1

df_feedback = pd.DataFrame(feedback_data)
df_feedback.to_csv('synthetic_unstructured_feedback.csv', index=False)

print("Data generation complete! 5 relational CSV files created successfully for the TrustScoreAI System.")