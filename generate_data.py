import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta

# Set random seed for reproducibility
np.random.seed(42)
random.seed(42)

# ==========================================
# Configuration & Constants
# ==========================================
NUM_EMPLOYEES = 200
NUM_MONTHS = 12
ROLES = ['Employee', 'Supervisor', 'Executive']
ROLE_PROBS = [0.80, 0.15, 0.05]
BRANCHES = ['NBO-01', 'NBO-02', 'MSA-01', 'KSM-01']
DEPARTMENTS = ['Retail Banking', 'Credit Processing', 'Operations', 'Compliance']

# Mock textual snippets for NLP dataset
POSITIVE_NOTES = ["Consistently meets targets.", "Shows strong integrity.", "Excellent collaboration skills."]
NEGATIVE_NOTES = ["Missed deadlines frequently.", "Compliance oversight noted.", "Needs improvement in peer collaboration."]
COMPLIANCE_NOTES = ["Strictly follows AML protocols.", "Minor KYC errors detected.", "Perfect adherence to regulatory guidelines."]

# ==========================================
# 1. Generate Employee Profiles (employee_dim.csv)
# ==========================================
print("Generating employee_dim.csv...")
employee_data = []
for user_id in range(1, NUM_EMPLOYEES + 1):
    role = np.random.choice(ROLES, p=ROLE_PROBS)
    employee_data.append({
        'user_id': user_id,
        'first_name': f"User_{user_id}_First",
        'last_name': f"User_{user_id}_Last",
        'email': f"user{user_id}@trustscoreai.bank.ke",
        'role': role,
        'branch_code': random.choice(BRANCHES),
        'department': random.choice(DEPARTMENTS),
        'hire_date': (datetime.now() - timedelta(days=random.randint(365, 3650))).strftime('%Y-%m-%d'),
        'is_active': np.random.choice([True, False], p=[0.95, 0.05])
    })

df_employees = pd.DataFrame(employee_data)
df_employees.to_csv('employee_dim.csv', index=False)

# Extract lists of IDs by role for relational mapping
employee_ids = df_employees[df_employees['role'] == 'Employee']['user_id'].tolist()
supervisor_ids = df_employees[df_employees['role'] == 'Supervisor']['user_id'].tolist()

# ==========================================
# 2. Generate Quantitative Metrics (numerical_kpis.csv)
# ==========================================
print("Generating numerical_kpis.csv...")
kpi_data = []
metric_id = 1
start_date = datetime(2025, 1, 1)

for user_id in df_employees['user_id']:
    # Generate 12 months of KPI data per user
    for month_offset in range(NUM_MONTHS):
        eval_date = start_date + pd.DateOffset(months=month_offset)
        
        # Simulating operational variables with realistic banking variances
        loan_vols = max(0, np.random.normal(loc=150000, scale=50000))
        accounts = max(0, int(np.random.normal(loc=45, scale=15)))
        error_freq = max(0, min(100, np.random.normal(loc=2.5, scale=1.0))) # Cash reconciliation errors
        np_credit_pct = max(0, min(100, np.random.normal(loc=3.0, scale=1.5))) 
        deadline_rate = max(0, min(100, np.random.normal(loc=85.0, scale=10.0)))
        ledger_speed = max(0, min(100, np.random.normal(loc=90.0, scale=5.0)))
        tx_accuracy = max(0, min(100, np.random.normal(loc=98.0, scale=2.0)))
        target_achieved = max(0, min(100, np.random.normal(loc=88.0, scale=12.0)))
        
        kpi_data.append({
            'metric_id': metric_id,
            'user_id': user_id,
            'evaluation_period': eval_date.strftime('%Y-%m-%d'),
            'loan_processing_volumes': round(loan_vols, 2),
            'account_creation_volumes': accounts,
            'cash_reconciliation_error_freq': round(error_freq, 2),
            'non_performing_credit_pct': round(np_credit_pct, 2),
            'task_deadline_fulfilment_rate': round(deadline_rate, 2),
            'daily_ledger_balancing_speed': round(ledger_speed, 2),
            'transaction_accuracy_rate': round(tx_accuracy, 2),
            'target_achievement_rate': round(target_achieved, 2)
        })
        metric_id += 1

df_kpis = pd.DataFrame(kpi_data)
df_kpis.to_csv('numerical_kpis.csv', index=False)

# ==========================================
# 3. Generate Qualitative Text (textual_reviews.csv)
# ==========================================
print("Generating textual_reviews.csv...")
feedback_data = []
feedback_id = 1

# Generate 2-3 feedback records per employee
for user_id in employee_ids:
    num_reviews = random.randint(2, 3)
    for _ in range(num_reviews):
        evaluator = random.choice(supervisor_ids)
        feedback_date = start_date + timedelta(days=random.randint(0, 360))
        
        feedback_data.append({
            'feedback_id': feedback_id,
            'user_id': user_id,
            'evaluator_id': evaluator,
            'feedback_date': feedback_date.strftime('%Y-%m-%d %H:%M:%S'),
            'raw_narrative': random.choice(POSITIVE_NOTES + NEGATIVE_NOTES),
            'supervisor_notes': random.choice(POSITIVE_NOTES + NEGATIVE_NOTES),
            'peer_evaluations': random.choice(POSITIVE_NOTES),
            'compliance_behavior_notes': random.choice(COMPLIANCE_NOTES),
            'behavioral_integrity_notes': "Displayed standard banking ethics.",
            'professional_accountability_notes': "Handled cash registers responsibly.",
            'collaboration_notes': "Worked well during the end-of-month reconciliation.",
        })
        feedback_id += 1

df_feedback = pd.DataFrame(feedback_data)
df_feedback.to_csv('textual_reviews.csv', index=False)

print("Data generation complete! Saved to employee_dim.csv, numerical_kpis.csv, and textual_reviews.csv.")