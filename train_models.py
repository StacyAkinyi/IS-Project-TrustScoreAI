import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import accuracy_score, classification_report
import joblib

def compute_truthfulness_weights(df):
    """
    Computes a truthfulness/credibility weight for each review based on:
    1. Historical Rater Credibility (simulated reviewer rating weight)
    2. Consistency check between qualitative text sentiment and quantitative accuracy.
    """
    weights = []
    for idx, row in df.iterrows():
        text = str(row['Feedback_Text']).lower()
        accuracy = row['Transaction_Accuracy']
        
        # Base weight assigned to the reviewer source
        source_credibility = 0.9  
        
        # Consistency penalty check: 
        # If text contains negative words ('struggles', 'delays', 'errors') 
        # but quantitative transaction accuracy is extremely high (>95%), 
        # it might indicate subjective/harsh bias, reducing truthfulness.
        negative_keywords = ['struggles', 'delays', 'errors', 'overlooks']
        has_negative_tone = any(word in text for word in negative_keywords)
        
        if has_negative_tone and accuracy > 95.0:
            # Possible discrepancy or harsh bias
            consistency_penalty = 0.7 
        else:
            consistency_penalty = 1.0
            
        final_weight = source_credibility * consistency_penalty
        weights.append(final_weight)
        
    return np.array(weights)

def train_trust_score_model():
    print("Loading synthetic banking dataset...")
    try:
        df = pd.read_csv('synthetic_banking_data.csv')
    except FileNotFoundError:
        print("Error: 'synthetic_banking_data.csv' not found. Please run generate_data.py first!")
        return

    # Define features and target variable
    X_num = df[['Loan_Volumes', 'Transaction_Accuracy', 'Workplan_Completion', 'Error_Frequencies']].values
    text_data = df['Feedback_Text'].values
    y = df['Target'].values

    print("Computing Review Truthfulness Weights...")
    truth_weights = compute_truthfulness_weights(df)

    print("Initializing TF-IDF Vectorizer for qualitative feedback...")
    tfidf = TfidfVectorizer(stop_words='english', max_features=50)
    X_text_raw = tfidf.fit_transform(text_data).toarray()

    # Apply Truthfulness Weighting: Scale the TF-IDF features by the computed truthfulness weight vector
    # This ensures biased or low-credibility text inputs have a diluted impact on the model.
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

    # Save trained models, vectorizer, and weight configurations
    joblib.dump(rf_classifier, 'trust_score_rf_model.pkl')
    joblib.dump(tfidf, 'tfidf_vectorizer.pkl')
    print("Trained truth-weighted model and vectorizer successfully saved to disk!")

if __name__ == "__main__":
    train_trust_score_model()