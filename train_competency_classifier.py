"""Train and export the notebook's multi-label appraisal competency model.

Usage:
  python train_competency_classifier.py path\to\appraisal_labels.xlsx

This refits both TF-IDF appraisal classifiers on the adjudicated workbook. It
uses the validation-selected competency thresholds reported by the grouped
holdout evaluation and saves artifacts using the local scikit-learn version.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import joblib
import pandas as pd
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.multiclass import OneVsRestClassifier
from sklearn.pipeline import Pipeline

ROOT = Path(__file__).resolve().parent
DIRECTIONS = ["negative", "positive", "mixed", "neutral"]
CATEGORIES = [
    "collaboration",
    "communication",
    "compliance_awareness",
    "learning_development",
]
# From the notebook's validation-only threshold selection. The test set was not
# used to choose these cutoffs.
THRESHOLDS = {
    "collaboration": 0.50,
    "communication": 0.50,
    "compliance_awareness": 0.40,
    "learning_development": 0.40,
}
MODEL_PATH = ROOT / "trustscore_competency_model.joblib"
METADATA_PATH = ROOT / "trustscore_competency_model_metadata.json"
DIRECTION_MODEL_PATH = ROOT / "trustscore_direction_model.joblib"
DIRECTION_METADATA_PATH = ROOT / "trustscore_direction_model_metadata.json"
REQUIRED = {"appraisal_statement", "category", "adjudicated_relevant", "adjudicated_direction"}


def make_model() -> Pipeline:
    return Pipeline([
        ("tfidf", TfidfVectorizer(
            ngram_range=(1, 2),
            min_df=1,
            sublinear_tf=True,
            strip_accents="unicode",
        )),
        ("classifier", OneVsRestClassifier(LogisticRegression(
            class_weight="balanced",
            max_iter=2000,
            random_state=42,
        ))),
    ])


def read_labels(path: Path, requested_sheet: str | None) -> pd.DataFrame:
    if path.suffix.lower() in {".xlsx", ".xls"}:
        book = pd.ExcelFile(path)
        sheet_names = [requested_sheet] if requested_sheet else book.sheet_names
        for sheet in sheet_names:
            if sheet not in book.sheet_names:
                continue
            candidate = pd.read_excel(path, sheet_name=sheet)
            if REQUIRED.issubset(candidate.columns):
                print(f"Using worksheet: {sheet}")
                return candidate
        raise SystemExit(
            "No worksheet contains the required columns: " + ", ".join(sorted(REQUIRED))
        )
    frame = pd.read_csv(path)
    missing = REQUIRED - set(frame.columns)
    if missing:
        raise SystemExit("Missing columns: " + ", ".join(sorted(missing)))
    return frame


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workbook", type=Path, help="Annotated statement workbook or CSV")
    parser.add_argument("--sheet", help="Worksheet name; otherwise the script finds the labeled sheet")
    args = parser.parse_args()
    if not args.workbook.exists():
        raise SystemExit(f"Training file not found: {args.workbook}")

    data = read_labels(args.workbook, args.sheet).copy()
    data["appraisal_statement"] = data["appraisal_statement"].fillna("").astype(str).str.strip()
    has_text_group_id = "text_group_id" in data.columns
    if has_text_group_id:
        data["text_group_id"] = data["text_group_id"].astype(str).str.strip()
    else:
        def stable_text_id(value: str) -> str:
            normalized = re.sub(r"\s+", " ", value.casefold()).strip()
            return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:20]
        data["text_group_id"] = data["appraisal_statement"].map(stable_text_id)
    data["category"] = data["category"].astype(str).str.strip().str.lower()
    data["direction"] = data["adjudicated_direction"].fillna("").astype(str).str.strip().str.lower()
    data["label"] = data["adjudicated_relevant"].astype(str).str.strip().str.lower().map(
        {"yes": 1, "no": 0, "true": 1, "false": 0, "1": 1, "0": 0}
    )
    if data["label"].isna().any():
        raise SystemExit("Unexpected or missing adjudicated_relevant values; expected yes/no.")
    data = data[data["category"].isin(CATEGORIES) & data["appraisal_statement"].ne("")].copy()
    if data.empty:
        raise SystemExit("No labeled appraisal statements remain after cleaning.")

    direction_pairs = data[data["label"].eq(1)].groupby(["text_group_id", "category"])["direction"].nunique()
    direction_conflicts = direction_pairs[direction_pairs > 1]
    if not direction_conflicts.empty:
        raise SystemExit(
            f"Found {len(direction_conflicts)} relevant statement/category pairs with conflicting directions; resolve them first."
        )
    pair_counts = data.groupby(["text_group_id", "category"])["label"].nunique()
    conflicts = pair_counts[pair_counts > 1]
    if not conflicts.empty:
        raise SystemExit(
            f"Found {len(conflicts)} statement/category pairs with conflicting labels; resolve them first."
        )
    data = data.drop_duplicates(["text_group_id", "category"], keep="first")

    text_counts = data.groupby("text_group_id")["appraisal_statement"].nunique()
    if has_text_group_id and (text_counts > 1).any():
        raise SystemExit("A text_group_id maps to multiple statement texts; fix IDs before training.")
    statements = data.drop_duplicates("text_group_id").set_index("text_group_id")["appraisal_statement"]
    labels = data.pivot(index="text_group_id", columns="category", values="label")
    labels = labels.reindex(index=statements.index, columns=CATEGORIES).fillna(0).astype(int)
    if labels.nunique().eq(1).any():
        unusable = labels.columns[labels.nunique().eq(1)].tolist()
        raise SystemExit("Each competency needs both relevant and not-relevant examples: " + ", ".join(unusable))

    model = make_model()
    model.fit(statements.astype(str).tolist(), labels)
    bundle = {
        "model": model,
        "categories": CATEGORIES,
        "thresholds": THRESHOLDS,
        "model_version": "tfidf-ovr-appraisal-competencies-v1",
    }
    joblib.dump(bundle, MODEL_PATH)
    metadata = {
        "task": "multi-label appraisal competency classification",
        "categories": CATEGORIES,
        "thresholds": THRESHOLDS,
        "threshold_source": "validation split from appraisal_nlp_baseline_colab.ipynb",
        "model": "word TF-IDF (1,2) + One-vs-Rest Logistic Regression",
        "training_statement_count": int(len(statements)),
        "training_pair_count": int(len(data)),
        "scikit_learn_version": sklearn.__version__,
        "statement_id_source": "workbook text_group_id" if has_text_group_id else "SHA-256 of normalized statement text",
        "reported_grouped_test": {
            "micro_f1": 0.97,
            "macro_f1": 0.97,
            "note": "Reported by the notebook's grouped holdout evaluation; the exported model is refit on all supplied labeled statements.",
        },
    }
    METADATA_PATH.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    direction_rows = data[
        data["label"].eq(1) & data["direction"].isin(DIRECTIONS)
    ].copy()
    if direction_rows["direction"].nunique() < 2:
        raise SystemExit("The direction model requires at least two labeled direction classes.")
    direction_text = (
        direction_rows["category"] + " [SEP] " + direction_rows["appraisal_statement"]
    )
    direction_model = Pipeline([
        ("tfidf", TfidfVectorizer(
            ngram_range=(1, 2),
            min_df=1,
            sublinear_tf=True,
            strip_accents="unicode",
        )),
        ("classifier", LogisticRegression(
            class_weight="balanced",
            max_iter=2000,
            random_state=42,
        )),
    ])
    direction_model.fit(direction_text, direction_rows["direction"])
    joblib.dump(direction_model, DIRECTION_MODEL_PATH)
    direction_classifier = direction_model.named_steps["classifier"]
    direction_metadata = {
        "task": "appraisal direction classification",
        "model_version": "tfidf-appraisal-direction-v1",
        "class_order": [str(label) for label in direction_classifier.classes_],
        "input_format": "lowercase category + ' [SEP] ' + cleaned appraisal statement",
        "input_scope": "Supervisor appraisal answers only; employee self-questionnaires are context for the supervisor and are not classified or scored.",
        "scoring_policy": {
            "positive": "automatic score contribution of 100",
            "negative": "automatic score contribution of 0",
            "mixed": "no numerical score",
            "neutral": "no numerical score",
            "human_confirmation_required": False,
        },
        "training_row_count": int(len(direction_rows)),
        "scikit_learn_version": sklearn.__version__,
        "historical_grouped_test": {
            "accuracy": 0.80,
            "macro_f1": 0.72,
            "note": "Earlier grouped holdout result from the supplied notebook; the exported model is refit on all labeled rows.",
        },
    }
    DIRECTION_METADATA_PATH.write_text(
        json.dumps(direction_metadata, indent=2), encoding="utf-8"
    )
    print(f"Trained on {len(statements)} unique statements ({len(data)} statement/category pairs).")
    print(f"Trained direction model on {len(direction_rows)} relevant labeled answers.")
    print(f"Saved models: {MODEL_PATH} and {DIRECTION_MODEL_PATH}")
    print(f"Saved metadata: {METADATA_PATH} and {DIRECTION_METADATA_PATH}")


if __name__ == "__main__":
    main()
