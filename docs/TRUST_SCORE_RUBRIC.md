# TrustScoreAI rubric and annotation plan (draft)

This is a proposal for review, not an approved employment or regulatory standard. Validate the measures and anchors with your lecturer and relevant banking stakeholders before operational use.

## Model pipeline

1. Aggregate the employee's telemetry over one half-year period.
2. Normalize eligible KPIs to 0–100 using their defined measurement ranges and direction, then group related KPIs.
3. Have trained reviewers annotate work-related evidence in feedback on the NLP dimensions below. Missing or irrelevant evidence is **unrated**, not a score of 1/5.
4. Have two reviewers independently assign an overall reference score using the shared rubric. Resolve large disagreements and retain both original scores plus the adjudicated score.
5. Train a Random Forest Regressor to estimate the overall reference score from the grouped telemetry and NLP dimension features. Keep the original evidence and scores available for human review.

The regressor must not use employee name, email, age, gender, ethnicity, health, family status, or other protected/personal attributes. Do not use raw sentiment polarity as a performance score. Exclude raw loan volume from the initial model because workload and job assignment can differ by role.

## Draft telemetry groups

Each input KPI is normalized to 0–100. Higher-is-better metrics increase the normalized value; lower-is-better metrics are inverted. Average available normalized KPIs within each group. Keep the component values and data coverage so a group average is explainable.

- **Operational quality:** transaction accuracy; inverse processing error frequency; inverse cash reconciliation errors.
- **Delivery and timeliness:** workplan completion; tasks completed on time; inverse loan processing time.
- **Customer outcomes:** customer satisfaction; complaint resolution.
- **Risk and controls:** inverse non-performing credit; inverse compliance incidents.

These ranges are technical normalization ranges, not bank targets. Review them against role-specific expectations. Do not treat missing KPI data as zero.

## Draft NLP dimensions

Annotate evidence in each feedback item, using the text and relevant context only:

- **Communication:** clear, relevant, respectful work communication and follow-through.
- **Collaboration:** observable contribution to colleagues or team work.
- **Compliance awareness:** observable use of required procedures and appropriate escalation; this does not replace recorded incident data.
- **Learning and development:** observable use of coaching, training, or agreed development actions.

Use a 1–5 scale only when the feedback contains relevant evidence. A dimension with no usable evidence is blank/unrated. Save a short evidence span and annotator ID for review. A negative or positive tone alone is not evidence of performance.

## Draft overall reference score anchors

Reviewers assign a score from 0 to 100 after considering the role expectations, grouped evidence, context, and evidence coverage. These anchors are a starting point and must be calibrated before use:

- **0–20:** repeated, verified gaps on essential agreed duties; identify support and context.
- **21–40:** performance often falls below agreed role expectations, supported by specific evidence.
- **41–60:** mixed or inconsistent results across the period.
- **61–80:** generally meets agreed role expectations, supported by evidence.
- **81–100:** consistently exceeds agreed role expectations with sustained, specific evidence.

Insufficient evidence is not a low score. Mark the label as `insufficient_evidence` and do not train on it. Do not infer intent, honesty, personality, or future potential from wording or sentiment.

## Label review process

Use two independent reviewers where possible. Record reviewer scores separately. If the scores differ materially, have a third reviewer adjudicate and record the final score and rationale. Review disagreements by role, department, branch, language, source type, and protected-group data where lawful and appropriate. Have human reviewers approve questionable model outputs; keep an appeal path for employees.

## Training rows

A final trust-score training row is one employee and one half-year period. Its target is `adjudicated_score_0_100`; its feature inputs are the grouped telemetry values plus period-level NLP ratings. Split evaluation data by employee, not by monthly row, to reduce leakage. Do not train until the annotations are reviewed and there are enough distinct employees and periods for a meaningful evaluation.
