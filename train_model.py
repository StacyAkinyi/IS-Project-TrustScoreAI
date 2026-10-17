"""Train the PostgreSQL-backed unified Trust Score Random Forest Regressor.

Training requires human-reviewed labels in data/training. Synthetic rows are
excluded unless --include-demo-data is explicitly supplied.
"""
import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.pipeline import make_pipeline
from sqlalchemy import text

from database import engine

ROOT = Path(__file__).resolve().parent
TRAINING_DIR = ROOT / "data" / "training"
TARGET_FILE = TRAINING_DIR / "trust_score_reference_labels.csv"
FEEDBACK_LABELS_FILE = TRAINING_DIR / "feedback_dimension_annotations.csv"
MODEL_FILE = ROOT / "trust_score_regressor.pkl"

METRIC_RANGES = {
    # (minimum, maximum, direction); these are data normalization bounds, not bank policy.
    "transaction_accuracy": (0, 100, "high"),
    "error_frequencies": (0, 15, "low"),
    "cash_reconciliation_errors": (0, 10, "low"),
    "workplan_completion": (0, 120, "high"),
    "task_deadline_fulfillment_pct": (0, 100, "high"),
    "loan_processing_turnaround_hours": (0, 96, "low"),
    "customer_satisfaction": (1, 5, "high"),
    "complaint_resolution_rate_pct": (0, 100, "high"),
    "non_performing_credit_pct": (0, 18, "low"),
    "compliance_incidents": (0, 4, "low"),
}
GROUPS = {
    "operational_quality": ["transaction_accuracy", "error_frequencies", "cash_reconciliation_errors"],
    "delivery_timeliness": ["workplan_completion", "task_deadline_fulfillment_pct", "loan_processing_turnaround_hours"],
    "customer_outcomes": ["customer_satisfaction", "complaint_resolution_rate_pct"],
    "risk_controls": ["non_performing_credit_pct", "compliance_incidents"],
}
FEEDBACK_DIMENSIONS = {
    "feedback_communication": "communication_1_5",
    "feedback_collaboration": "collaboration_1_5",
    "feedback_compliance_awareness": "compliance_awareness_1_5",
    "feedback_learning_development": "learning_development_1_5",
}
FEATURES = list(GROUPS) + list(FEEDBACK_DIMENSIONS) + ["telemetry_month_count"]


def _normalize(series, low, high, direction):
    values = pd.to_numeric(series, errors="coerce").clip(lower=low, upper=high)
    score = (values - low) * (100.0 / (high - low))
    return score if direction == "high" else 100.0 - score


def _require_file(path, description):
    if not path.exists():
        raise SystemExit(f"Missing {path}. Copy and fill the {description} template first.")
    frame = pd.read_csv(path)
    if frame.empty:
        raise SystemExit(f"{path} has headers but no reviewed rows yet. Add labeled examples before training.")
    return frame


def _load_telemetry_features(include_demo_data=False):
    columns = ["employee_id", "recorded_at", "data_source", *METRIC_RANGES.keys()]
    query = text("SELECT " + ", ".join(columns) + " FROM performance_records")
    with engine.connect() as connection:
        telemetry = pd.read_sql_query(query, connection)
    if telemetry.empty:
        raise SystemExit("PostgreSQL has no performance_records to build score features from.")
    allowed_sources = ["real_anonymized", "synthetic_demo"] if include_demo_data else ["real_anonymized"]
    telemetry = telemetry[telemetry["data_source"].isin(allowed_sources)].copy()
    if telemetry.empty:
        raise SystemExit("No eligible telemetry rows found. Training uses real_anonymized rows by default; old rows marked unknown and synthetic_demo rows are excluded.")
    telemetry["recorded_at"] = pd.to_datetime(telemetry["recorded_at"], utc=True, errors="coerce")
    telemetry = telemetry.dropna(subset=["employee_id", "recorded_at"])
    telemetry["period_code"] = telemetry["recorded_at"].dt.year.astype(str) + np.where(
        telemetry["recorded_at"].dt.month <= 6, "-H1", "-H2"
    )
    normalized = {}
    for name, (low, high, direction) in METRIC_RANGES.items():
        normalized[name] = _normalize(telemetry[name], low, high, direction)
    for group_name, members in GROUPS.items():
        telemetry[group_name] = pd.concat([normalized[name] for name in members], axis=1).mean(axis=1)
    features = telemetry.groupby(["employee_id", "period_code", "data_source"], as_index=False).agg(
        **{name: (name, "mean") for name in GROUPS},
        telemetry_month_count=("recorded_at", "nunique"),
    ).rename(columns={"data_source": "dataset_source"})
    return features


def _load_feedback_features(include_demo_data=False):
    annotations = _require_file(FEEDBACK_LABELS_FILE, "feedback annotation")
    required = {"employee_id", "period_code", "dataset_source", *FEEDBACK_DIMENSIONS.values()}
    missing = required - set(annotations.columns)
    if missing:
        raise SystemExit(f"Feedback annotations are missing columns: {', '.join(sorted(missing))}")
    allowed_sources = ["real_anonymized", "synthetic_demo"] if include_demo_data else ["real_anonymized"]
    annotations = annotations[annotations["dataset_source"].isin(allowed_sources)].copy()
    if annotations.empty:
        raise SystemExit("No eligible feedback annotations are available. Synthetic annotations are excluded by default.")
    for feature, source in FEEDBACK_DIMENSIONS.items():
        ratings = pd.to_numeric(annotations[source], errors="coerce")
        invalid = ratings.notna() & ~ratings.between(1, 5)
        if invalid.any():
            raise SystemExit(f"{source} contains ratings outside 1–5.")
        annotations[feature] = (ratings - 1) * 25.0
    return annotations.groupby(["employee_id", "period_code", "dataset_source"], as_index=False)[list(FEEDBACK_DIMENSIONS)].mean()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--include-demo-data", action="store_true", help="include synthetic_demo reference labels for a software demonstration only")
    args = parser.parse_args()

    labels = _require_file(TARGET_FILE, "overall score label")
    required = {"employee_id", "period_code", "reviewer_1_score_0_100", "reviewer_2_score_0_100", "adjudicated_score_0_100", "label_status", "dataset_source", "rubric_version"}
    missing = required - set(labels.columns)
    if missing:
        raise SystemExit(f"Reference labels are missing columns: {', '.join(sorted(missing))}")
    labels = labels[labels["label_status"] == "approved"].copy()
    allowed_sources = ["real_anonymized", "synthetic_demo"] if args.include_demo_data else ["real_anonymized"]
    labels = labels[labels["dataset_source"].isin(allowed_sources)]
    if labels.empty:
        raise SystemExit("No approved real_anonymized score labels found. Demo labels require the explicit --include-demo-data option.")
    for name in ["reviewer_1_score_0_100", "reviewer_2_score_0_100", "adjudicated_score_0_100"]:
        labels[name] = pd.to_numeric(labels[name], errors="coerce")
        if labels[name].isna().any() or not labels[name].between(0, 100).all():
            raise SystemExit(f"Approved labels must have valid values from 0 to 100 in {name}.")
    if labels.duplicated(["employee_id", "period_code"]).any():
        raise SystemExit("Reference labels must have one approved row per employee and half-year period.")

    features = _load_telemetry_features(args.include_demo_data).merge(
        _load_feedback_features(args.include_demo_data),
        on=["employee_id", "period_code", "dataset_source"], how="left"
    )
    dataset = labels.merge(features, on=["employee_id", "period_code", "dataset_source"], how="inner")
    if len(dataset) < 10 or dataset["employee_id"].nunique() < 5:
        raise SystemExit("Need at least 10 approved employee-period labels from at least 5 distinct employees before training.")
    if dataset[list(FEEDBACK_DIMENSIONS)].notna().sum().min() == 0:
        raise SystemExit("Each NLP dimension needs at least one reviewed rating before training the unified model.")

    X = dataset[FEATURES]
    y = dataset["adjudicated_score_0_100"]
    groups = dataset["employee_id"]
    folds = min(5, groups.nunique())
    model = make_pipeline(
        SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True),
        RandomForestRegressor(
            n_estimators=300,
            max_depth=8,
            min_samples_leaf=2,
            max_features=0.8,
            random_state=42,
            n_jobs=-1,
        ),
    )
    predictions = cross_val_predict(model, X, y, groups=groups, cv=GroupKFold(n_splits=folds))
    print(f"Grouped cross-validation ({folds} folds; employees kept within one fold)")
    print(f"Examples: {len(dataset)} across {groups.nunique()} employees")
    print(f"MAE: {mean_absolute_error(y, predictions):.2f} points")
    print(f"RMSE: {mean_squared_error(y, predictions) ** 0.5:.2f} points")
    print(f"R²: {r2_score(y, predictions):.3f}")
    model.fit(X, y)
    joblib.dump({"model": model, "features": FEATURES, "rubric_version": sorted(labels["rubric_version"].astype(str).unique())}, MODEL_FILE)
    print(f"Saved prototype regressor to {MODEL_FILE}")
    print("Review model quality and subgroup error before using it for any employee-facing decision.")


if __name__ == "__main__":
    main()
