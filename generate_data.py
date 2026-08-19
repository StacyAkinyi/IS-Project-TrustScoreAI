import pandas as pd
import numpy as np

def generate_synthetic_banking_data(num_records=1000):
    np.random.seed(42)
    
    # Generate unique employee identifiers for operational staff & agents
    employee_ids = [f"EMP_{i:04d}" for i in range(1, num_records + 1)]
    
    # Quantitative Key Performance Indicators (KPIs)
    loan_volumes = np.random.randint(10, 150, size=num_records)
    transaction_accuracy = np.random.uniform(85.0, 100.0, size=num_records)
    workplan_completion = np.random.uniform(50.0, 100.0, size=num_records)
    error_frequencies = np.random.poisson(lam=2, size=num_records)
    
    # Qualitative Supervisor Feedback Notes (for the NLP Pipeline)
    feedback_pool = [
        "Consistently meets targets and handles client queries with high integrity.",
        "Struggles with meeting task deadlines and balancing cash reconciliation errors.",
        "Excellent collaboration skills, highly compliant with banking regulations.",
        "Needs supervision on loan processing volumes; frequent documentation delays.",
        "Exemplary adherence to security protocols, maintains exceptional audit scores.",
        "Occasionally overlooks compliance details during high-pressure transaction cycles."
    ]
    feedback_notes = np.random.choice(feedback_pool, size=num_records)
    
    # Compute a composite performance score to derive the reliable target label (1 = Reliable, 0 = Needs Improvement)
    performance_score = ((loan_volumes / 150) * 0.4 + 
                         (transaction_accuracy / 100) * 0.4 + 
                         (workplan_completion / 100) * 0.2)
    reliable_target = np.where(performance_score > 0.75, 1, 0)

    # Assemble into a pandas DataFrame
    df = pd.DataFrame({
        'Employee_ID': employee_ids,
        'Loan_Volumes': loan_volumes,
        'Transaction_Accuracy': transaction_accuracy,
        'Workplan_Completion': workplan_completion,
        'Error_Frequencies': error_frequencies,
        'Feedback_Text': feedback_notes,
        'Target': reliable_target
    })
    
    # Save to CSV for the training pipeline
    df.to_csv('synthetic_banking_data.csv', index=False)
    print(f"Successfully generated {num_records} synthetic records and saved to 'synthetic_banking_data.csv'.")

if __name__ == "__main__":
    generate_synthetic_banking_data()