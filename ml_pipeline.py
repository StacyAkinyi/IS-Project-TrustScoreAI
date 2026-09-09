import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import accuracy_score, classification_report
import joblib

def compute_truthfulness_weights(df):
    """
    Computes a credibility weight for each review based on the consistency 
    between qualitative text sentiment and quantitative accuracy.
    """
    weights = []
    negative_keywords = ['struggles', 'delays', 'errors', 'overlooks', 'minor', 'needs improvement']
    
    for idx, row in df.iterrows():
        text = str(row['narrative_text']).lower()
        accuracy = row['transaction_accuracy']
        
        # Base weight assigned to the reviewer source
        source_credibility = 0.9  
        
        has_negative_tone = any(word in text for word in negative_keywords)
        
        # Consistency penalty check: 
        # If the text has a negative tone but transaction accuracy is extremely high (>95%), 
        # it might indicate subjective/harsh bias, reducing truthfulness.
        if has_negative_tone and accuracy > 95.0:
            consistency_penalty = 0.7 
        else:
            consistency_penalty = 1.0
            
        final_weight = source_credibility * consistency_penalty
        weights.append(final_weight)
        
    return np.array(weights)

def train_trust_score_model():
    print("Loading synthetic multi-table datasets...")
    try:
        kpi_df = pd.read_csv('synthetic_performance_records.csv')
        feedback_df = pd.read_csv('synthetic_unstructured_feedback.csv')
    except FileNotFoundError:
        print("Error: Dataset CSVs not found. Please run generate_data.py first!")
        return

    print("Aggregating hierarchical data per employee...")
    
    # 1. Aggregate the monthly numerical KPIs into an average per employee
    kpi_agg = kpi_df.groupby('employee_id').agg({
        'loan_volumes': 'mean',
        'transaction_accuracy': 'mean',
        'workplan_completion': 'mean',
        'error_frequencies': 'mean',
        'reliability_target': lambda x: x.mode()[0] # Take the most frequent target
    }).reset_index()

    # 2. Aggregate the multiple text reviews into a single combined document per employee
    feedback_agg = feedback_df.groupby('employee_id').agg({
        'narrative_text': lambda x: ' '.join(x.dropna())
    }).reset_index()

    # 3. Merge both data streams into a single matrix
    df = pd.merge(kpi_agg, feedback_agg, on='employee_id', how='inner')

    # Define features and target variable
    X_num = df[['loan_volumes', 'transaction_accuracy', 'workplan_completion', 'error_frequencies']].values
    text_data = df['narrative_text'].values
    y = df['reliability_target'].values

    print("Computing Review Truthfulness Weights...")
    truth_weights = compute_truthfulness_weights(df)

    print("Initializing TF-IDF Vectorizer for qualitative feedback...")
    tfidf = TfidfVectorizer(stop_words='english', max_features=50)
    X_text_raw = tfidf.fit_transform(text_data).toarray()

    # Apply Truthfulness Weighting
    X_text_weighted = X_text_raw * truth_weights[:, np.newaxis]

    # Combine quantitative metrics and weighted text token matrices
    X_combined = np.hstack((X_num, X_text_weighted))

    # Split dataset into training and testing subsets (70% train, 30% test)
    X_train, X_test, y_train, y_test = train_test_split(X_combined, y, test_size=0.3, random_state=42)

    print("Training Random Forest Classifier model with Truth-Weighted NLP Features...")
    rf_classifier = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42)
    rf_classifier.fit(X_train, y_train)

    # Evaluate model performance
    predictions = rf_classifier.predict(X_test)
    acc = accuracy_score(y_test, predictions)
    
    print("\n--- Model Training Results (with Truthfulness Weighting) ---")
    print(f"Accuracy Score: {acc * 100:.2f}%")
    print("\nClassification Report:\n", classification_report(y_test, predictions))

    # Save trained models
    joblib.dump(rf_classifier, 'trust_score_rf_model.pkl')
    joblib.dump(tfidf, 'tfidf_vectorizer.pkl')
    print("Trained model and vectorizer successfully saved to disk as .pkl files!")

if __name__ == "__main__":
    train_trust_score_model()