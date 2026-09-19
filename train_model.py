import pandas as pd
import numpy as np
import joblib
from pymongo import MongoClient
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from database import engine

MONGO_URI = "mongodb://localhost:27017/"
MONGO_DB_NAME = "trustscore_mongo"

def compute_truthfulness_weights(df):
    weights = []
    negative_keywords = ['struggles', 'delays', 'errors', 'overlooks', 'minor', 'needs improvement']
    
    for idx, row in df.iterrows():
        text = str(row['narrative_text']).lower()
        accuracy = row['transaction_accuracy']
        source_credibility = 0.9  
        has_negative_tone = any(word in text for word in negative_keywords)
        
        consistency_penalty = 0.7 if (has_negative_tone and accuracy > 95.0) else 1.0
        weights.append(source_credibility * consistency_penalty)
        
    return np.array(weights)

def train_trust_score_model():
    print("Loading evaluation record datasets from PostgreSQL and MongoDB...")
    
    # 1. Fetch individual performance evaluation records (2,400 rows)
    perf_df = pd.read_sql_table("performance_records", con=engine)
    
    # 2. Fetch qualitative feedback from MongoDB
    mongo_client = MongoClient(MONGO_URI)
    mongo_db = mongo_client[MONGO_DB_NAME]
    feedback_docs = list(mongo_db["unstructured_feedback"].find({}, {"_id": 0}))
    feedback_df = pd.DataFrame(feedback_docs)
    mongo_client.close()

    # Aggregate feedback per employee to attach to monthly evaluation records
    feedback_agg = feedback_df.groupby('employee_id').agg({
        'narrative_text': lambda x: ' '.join(x.dropna())
    }).reset_index()

    # Merge performance records with feedback narratives
    df = pd.merge(perf_df, feedback_agg, on='employee_id', how='left')
    df['narrative_text'] = df['narrative_text'].fillna(df['feedback_text'].fillna(""))

    # Extract record-level feature vectors
    X_num = df[['loan_volumes', 'transaction_accuracy', 'workplan_completion', 'error_frequencies']].values
    text_data = df['narrative_text'].values
    y = df['reliability_target'].values

    print("Computing Review Truthfulness Weights...")
    truth_weights = compute_truthfulness_weights(df)

    print("Vectorizing qualitative feedback...")
    tfidf = TfidfVectorizer(stop_words='english', max_features=25)
    X_text_raw = tfidf.fit_transform(text_data).toarray()
    X_text_weighted = X_text_raw * truth_weights[:, np.newaxis]

    X_combined = np.hstack((X_num, X_text_weighted))

    # Regularized Random Forest Classifier
    rf_classifier = RandomForestClassifier(
        n_estimators=100,
        max_depth=5,
        min_samples_leaf=10,
        min_samples_split=20,
        random_state=42
    )

    # 5-Fold Stratified Cross-Validation on all 2,400 evaluation records
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores = cross_val_score(rf_classifier, X_combined, y, cv=skf, scoring='accuracy')

    print(f"\n--- Record-Level Cross-Validation Results ---")
    print(f"5-Fold Accuracy Scores: {np.round(cv_scores * 100, 2)}")
    print(f"Mean CV Accuracy: {cv_scores.mean() * 100:.2f}% (+/- {cv_scores.std() * 100:.2f}%)")

    # Train final model across complete dataset
    rf_classifier.fit(X_combined, y)

    # Export serialized artifacts
    joblib.dump(rf_classifier, 'trust_score_rf_model.pkl')
    joblib.dump(tfidf, 'tfidf_vectorizer.pkl')
    print("\n✓ Model trained and saved successfully as 'trust_score_rf_model.pkl'!")

if __name__ == "__main__":
    train_trust_score_model()