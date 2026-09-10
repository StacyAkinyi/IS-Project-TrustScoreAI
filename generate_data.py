import pandas as pd
import numpy as np
import random
from datetime import datetime
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

BRANCHES = [
    'NBO-Central', 'NBO-Westlands', 'NBO-Upperhill', 'MSA-Island', 
    'MSA-Nyali', 'KSM-Central', 'NKU-CBD', 'ELD-Core', 
    'KTL-Branch', 'THK-Industrial'
]

DEPARTMENTS = [
    'Retail Banking', 'Credit Processing', 'Operations', 'Compliance', 
    'Treasury', 'IT Risk', 'Customer Service', 'Wealth Management', 
    'Corporate Banking', 'Trade Finance'
]

REGIONS = ['Nairobi Region', 'Coast Region', 'Western Region']
EMPLOYEE_ROLES = ['Teller', 'Loan Officer', 'Customer Success', 'Analyst']

# Trait-Specific Narrative Text Banks for Signal Generation
TRAIT_TEXT_BANKS = {
    'compliance': {
        'pos': ["Strictly adheres to KYC protocols.", "Zero compliance audit findings.", "Demonstrates exemplary regulatory compliance."],
        'neg': ["Minor KYC compliance oversight noted.", "Fails to verify documentation thoroughly.", "Frequent audit exceptions flagged."]
    },
    'productivity': {
        'pos': ["Consistently exceeds monthly volume targets.", "High output speed on ledger entries.", "Completes workplans well ahead of schedule."],
        'neg': ["Struggles with meeting volume deadlines.", "Behind on quarterly workplan milestones.", "Low transaction processing speed."]
    },
    'collaboration': {
        'pos': ["Excellent teamwork during month-end reconciliation.", "Actively assists peers with cross-departmental tasks.", "Fosters strong inter-branch collaboration."],
        'neg': ["Needs improvement in peer collaboration.", "Works in isolation and resists group efforts.", "Reluctant to share operational workloads."]
    },
    'integrity': {
        'pos': ["Consistently acts with high integrity and transparency.", "Upholds ethical standards during audit checks.", "Honest and accountable in error reporting."],
        'neg': ["Exhibits inconsistent ethical transparency.", "Attempts to conceal minor ledger errors.", "Questionable accountability under pressure."]
    },
    'adaptability': {
        'pos': ["Adapts quickly to new banking software rollouts.", "Handles branch workflow shifts smoothly.", "Highly resilient during system updates."],
        'neg': ["Struggles to adapt to procedural changes.", "Resistant to adopting updated compliance systems.", "Fails to pivot during operational shifts."]
    }
}

# ==========================================
# 1. Generate Hierarchical Users
# ==========================================
print("Generating hierarchical user data...")

df_executives = pd.DataFrame([{
    'executive_id': exec_id,
    'full_name': fake.name(),
    'oversight_region': random.choice(REGIONS)
} for exec_id in range(1, NUM_EXECUTIVES + 1)])

df_supervisors = pd.DataFrame([{
    'supervisor_id': sup_id,
    'executive_id': random.randint(1, NUM_EXECUTIVES),
    'full_name': fake.name(),
    'department_code': random.choice(DEPARTMENTS)
} for sup_id in range(1, NUM_SUPERVISORS + 1)])

employees_list = [{
    'employee_id': emp_id,
    'supervisor_id': random.randint(1, NUM_SUPERVISORS),
    'full_name': fake.name(),
    'role': random.choice(EMPLOYEE_ROLES),
    'branch_location': random.choice(BRANCHES),
    'gt_collaboration': random.choice([1, 1, 1, 0]),
    'gt_integrity': random.choice([1, 1, 1, 0]),
    'gt_adaptability': random.choice([1, 1, 0])
} for emp_id in range(1, NUM_EMPLOYEES + 1)]

df_employees = pd.DataFrame(employees_list)

# ==========================================
# 2. Generate Quantitative Metrics & Performance Records
# ==========================================
print("Generating performance_records.csv...")
kpi_data = []
record_id = 1
start_date = datetime(2025, 1, 1)

for emp in employees_list:
    emp_id = emp['employee_id']
    # Define baseline employee capability level (0=Low, 1=Medium, 2=High)
    base_capability = np.random.choice([0, 1, 2], p=[0.25, 0.50, 0.25])

    for month_offset in range(NUM_MONTHS):
        eval_date = start_date + pd.DateOffset(months=month_offset)
        
        # Draw realistic KPIs according to capability tier
        if base_capability == 2:
            tx_accuracy = max(50.0, min(100.0, np.random.normal(loc=96.0, scale=2.5)))
            wp_completion = max(40.0, min(100.0, np.random.normal(loc=94.0, scale=4.0)))
            err_freq = max(0, int(np.random.poisson(lam=0.8)))
            loan_vols = max(10, int(np.random.normal(loc=135, scale=20)))
            summary_feedback = random.choice(TRAIT_TEXT_BANKS['productivity']['pos'])
        elif base_capability == 1:
            tx_accuracy = max(50.0, min(100.0, np.random.normal(loc=88.0, scale=4.5)))
            wp_completion = max(40.0, min(100.0, np.random.normal(loc=83.0, scale=7.0)))
            err_freq = max(0, int(np.random.poisson(lam=2.5)))
            loan_vols = max(10, int(np.random.normal(loc=95, scale=20)))
            summary_feedback = random.choice(TRAIT_TEXT_BANKS['compliance']['pos'])
        else:
            tx_accuracy = max(50.0, min(100.0, np.random.normal(loc=76.0, scale=7.0)))
            wp_completion = max(40.0, min(100.0, np.random.normal(loc=68.0, scale=10.0)))
            err_freq = max(0, int(np.random.poisson(lam=5.0)))
            loan_vols = max(10, int(np.random.normal(loc=55, scale=20)))
            summary_feedback = random.choice(TRAIT_TEXT_BANKS['compliance']['neg'])

        # Inject 12% realistic noise boundary overlap to avoid ML overfitting (100% accuracy)
        if random.random() < 0.12:
            reliability_target = random.choice([0, 1, 2])
        else:
            reliability_target = base_capability

        target_compliance = 1 if (tx_accuracy >= 90.0 and err_freq <= 2) else 0
        target_productivity = 1 if (wp_completion >= 80.0 and loan_vols >= 90) else 0

        kpi_data.append({
            'record_id': record_id,
            'employee_id': emp_id,
            'loan_volumes': loan_vols,
            'transaction_accuracy': round(tx_accuracy, 2),
            'workplan_completion': round(wp_completion, 2),
            'error_frequencies': err_freq,
            'feedback_text': summary_feedback,
            'truthfulness_weight': round(random.uniform(0.85, 1.0), 2),
            'reliability_target': reliability_target,
            'target_compliance': target_compliance,
            'target_productivity': target_productivity,
            'target_collaboration': emp['gt_collaboration'],
            'target_integrity': emp['gt_integrity'],
            'target_adaptability': emp['gt_adaptability'],
            'recorded_at': eval_date.strftime('%Y-%m-%d %H:%M:%S')
        })
        record_id += 1

df_kpis = pd.DataFrame(kpi_data)

# ==========================================
# 3. Generate Qualitative Text (MongoDB: unstructured_feedback)
# ==========================================
print("Generating unstructured_feedback.csv for MongoDB...")
feedback_data = []
feedback_id = 1

for emp in employees_list:
    emp_id = emp['employee_id']
    num_reviews = random.randint(2, 4)
    
    emp_kpis = df_kpis[df_kpis['employee_id'] == emp_id]
    emp_targets = {
        'compliance': emp_kpis['target_compliance'].mode()[0],
        'productivity': emp_kpis['target_productivity'].mode()[0],
        'collaboration': emp['gt_collaboration'],
        'integrity': emp['gt_integrity'],
        'adaptability': emp['gt_adaptability']
    }

    for _ in range(num_reviews):
        is_peer = random.choice([True, False])
        sup_id_val = None if is_peer else emp['supervisor_id']
        author_id_val = random.choice([e['employee_id'] for e in employees_list if e['employee_id'] != emp_id]) if is_peer else None

        trait_sampled = random.choice(list(TRAIT_TEXT_BANKS.keys()))
        trait_status = emp_targets[trait_sampled]
        
        narrative = random.choice(TRAIT_TEXT_BANKS[trait_sampled]['pos'] if trait_status == 1 else TRAIT_TEXT_BANKS[trait_sampled]['neg'])
        sentiment = round(random.uniform(0.4, 0.95) if trait_status == 1 else random.uniform(-0.9, -0.2), 2)

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

# ==========================================
# Save Output Datasets Matched to Schema
# ==========================================
df_executives.to_csv('synthetic_executive_manager.csv', index=False)
df_supervisors.to_csv('synthetic_immediate_supervisor.csv', index=False)
df_employees[['employee_id', 'supervisor_id', 'full_name', 'role', 'branch_location']].to_csv('synthetic_employee.csv', index=False)
df_kpis[['record_id', 'employee_id', 'loan_volumes', 'transaction_accuracy', 'workplan_completion', 'error_frequencies', 'feedback_text', 'truthfulness_weight', 'reliability_target', 'recorded_at']].to_csv('synthetic_performance_records.csv', index=False)
df_feedback.to_csv('synthetic_unstructured_feedback.csv', index=False)

print("✓ Synthetic multi-trait dataset generated successfully and saved to disk!")