import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, accuracy_score
from scipy.sparse import hstack

# ==========================================
# 1. Data Ingestion & Integration
# ==========================================
print("Loading synthetic datasets...")
df_employees = pd.read_csv('employee_dim.csv')
df_kpis = pd.read_csv('numerical_kpis.csv')
df_feedback = pd.read_csv('textual_reviews.csv')

# Aggregate KPIs per employee (calculating the mean across the 12 evaluation months)
kpi_summary = df_kpis.groupby('user_id').agg({
    'loan_processing_volumes': 'mean',
    'account_creation_volumes': 'mean',
    'cash_reconciliation_error_freq': 'mean',
    'non_performing_credit_pct': 'mean',
    'task_deadline_fulfilment_rate': 'mean',
    'daily_ledger_balancing_speed': 'mean',
    'transaction_accuracy_rate': 'mean',
    'target_achievement_rate': 'mean'
}).reset_index()

# Combine multi-source unstructured feedback per employee into a single text block
feedback_summary = df_feedback.groupby('user_id').agg({
    'raw_narrative': lambda x: ' '.join(x.dropna())
}).reset_index()

# Merge all features into a unified dataset
df_merged = pd.merge(kpi_summary, feedback_summary, on='user_id', how='left')
df_merged['raw_narrative'] = df_merged['raw_narrative'].fillna("")

# Generate a synthetic target class label ('Reliability_Tier') for model training
# In a real-world scenario, this would be based on historical HR disciplinary/promotion logs
conditions = [
    (df_merged['target_achievement_rate'] >= 90) & (df_merged['cash_reconciliation_error_freq'] <= 2.0),
    (df_merged['target_achievement_rate'] >= 75) & (df_merged['cash_reconciliation_error_freq'] <= 4.0)
]
choices = ['High Performer', 'Reliable']
df_merged['Reliability_Tier'] = np.select(conditions, choices, default='At Risk')

# ==========================================
# 2. Data Preprocessing Pipelines
# ==========================================
print("Executing parallel preprocessing pipelines...")

# Quantitative Pipeline: Min-Max Normalization
scaler = MinMaxScaler()
numeric_features = [
    'loan_processing_volumes', 'account_creation_volumes', 'cash_reconciliation_error_freq',
    'non_performing_credit_pct', 'task_deadline_fulfilment_rate', 'daily_ledger_balancing_speed',
    'transaction_accuracy_rate', 'target_achievement_rate'
]
X_numeric = scaler.fit_transform(df_merged[numeric_features])

# Qualitative Pipeline: NLP Tokenization & TF-IDF Vectorization
tfidf = TfidfVectorizer(stop_words='english', max_features=100) # Stripping computational stop-words
X_text = tfidf.fit_transform(df_merged['raw_narrative'])

# Concatenate the scaled numerical matrix with the dense TF-IDF vector matrix
X_combined = hstack([X_numeric, X_text])
y = df_merged['Reliability_Tier']

# ==========================================
# 3. Model Training & Hyperparameter Tuning
# ==========================================
# Seventy-Thirty split-partitioning for training and isolation benchmarking
X_train, X_test, y_train, y_test = train_test_split(X_combined, y, test_size=0.30, random_state=42)

print("Training the Random Forest ensemble classifier...")
# Optimizing tree construction via Gini impurity, max tree depth, and estimators
rf_classifier = RandomForestClassifier(
    n_estimators=200, 
    max_depth=15, 
    criterion='gini', 
    random_state=42,
    class_weight='balanced'
)
rf_classifier.fit(X_train, y_train)

# ==========================================
# 4. Model Validation and Testing
# ==========================================
print("Evaluating predictive accuracy...")
y_pred = rf_classifier.predict(X_test)

# Benchmarking classification accuracy, macro-averaged precision, recall scores, and F1-score
acc = accuracy_score(y_test, y_pred)
report = classification_report(y_test, y_pred)

print("-" * 50)
print(f"Classification Accuracy: {acc:.4f}")
print("-" * 50)
print("Detailed Validation Metrics (Precision, Recall, F1-Score):")
print(report)