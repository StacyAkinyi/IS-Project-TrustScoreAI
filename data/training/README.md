# Human review data for the TrustScoreAI model

These are blank templates. Copy them to `trust_score_reference_labels.csv` and `feedback_dimension_annotations.csv` before adding reviewed examples. Do not fill them with generated random scores or add names, emails, or protected personal data.

- `trust_score_reference_labels.csv`: one overall target per employee and half-year. Record two independent scores and the adjudicated score. Set `label_status` to `approved` only after review; use `insufficient_evidence` when evidence is inadequate. Set `dataset_source` to `real_anonymized` or `synthetic_demo`.
- `feedback_dimension_annotations.csv`: one row per reviewed feedback item. Rate only dimensions supported by relevant evidence. Leave a dimension blank when evidence is insufficient. Set `dataset_source` consistently.

Training excludes `synthetic_demo` rows by default. Use `--include-demo-data` only to demonstrate the pipeline; demo results are not evidence of model accuracy or fairness. See `docs/TRUST_SCORE_RUBRIC.md` for draft definitions and score anchors. Have the rubric reviewed and versioned before collecting labels. Keep these files access-controlled because they contain work performance judgments.
