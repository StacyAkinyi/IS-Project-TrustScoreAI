# Feedback annotation guide

This guide explains how to label feedback for the draft TrustScoreAI model. It supports research and human review; it is not an employment policy or a bank standard. Have the rubric reviewed by your lecturer and relevant stakeholders before collecting labels.

## What a reviewer labels

Create one annotation row per feedback item in `data/training/feedback_dimension_annotations.csv`. Use the anonymized `feedback_id`, employee ID, half-year period, and dataset source. Do not copy employee names, email addresses, or other identifying details into the annotation file. Keep the source feedback in its access-controlled system and use the ID to trace it when an authorized reviewer needs to audit a label.

Reviewers independently rate only the four draft dimensions below. A score describes the specific work-related evidence in that feedback item, not the employee's personality or overall value. Leave a dimension blank when the feedback does not contain enough relevant evidence. Set `evidence_adequate` to `false` if the item contains no usable work-related evidence for these dimensions; do not turn missing evidence into a low score.

## Shared 1–5 anchors

Apply these anchors separately to each dimension, using only evidence relevant to that dimension:

| Rating | Meaning | Evidence standard |
|---|---|---|
| 1 | Clear, specific evidence of a substantial gap | The feedback identifies an observable work action or outcome and enough context to understand the gap. |
| 2 | Some evidence of a gap | At least one observable example supports a concern, but scope, consistency, or impact is limited or unclear. |
| 3 | Mixed or meets the stated expectation | Specific evidence supports adequate performance, or the item contains a balanced mix of positive and corrective evidence. |
| 4 | Strong evidence of effective practice | Specific work examples show effective behavior or outcomes beyond a single unsupported general claim. |
| 5 | Consistent, substantial evidence of highly effective practice | Multiple concrete examples or a sustained outcome support this rating. |
| Unrated | Not enough relevant evidence | The item is vague, unrelated to the dimension, based only on tone/opinion, or contains no observable example. Leave the cell blank. |

Do not treat the scale as a count of positive or negative words. A statement such as “great attitude” or “difficult person” is not sufficient evidence by itself. A useful evidence span names a work action, context, and result where available. Keep the span short and quote only the words needed to support the label.

## Dimension definitions

- **Communication:** clarity, relevance, respect, and work-related follow-through in communication. Rate observable communication, not accent, fluency, personality, or whether the reviewer likes the person's style.
- **Collaboration:** observable contribution to colleagues or shared work. Do not infer cooperation from popularity, visibility, or social similarity.
- **Compliance awareness:** observable use of relevant procedures, accurate escalation, or documented control practice. This does not replace recorded compliance incidents or establish intent. Apply the same role-relevant expectations across employees.
- **Learning and development:** observable use of coaching, training, or agreed development actions. Do not infer motivation or potential from writing style or access to opportunities.

## Decision rules for tricky feedback

1. **No example, no rating.** “Needs to improve” without a work example is unrated for the affected dimension.
2. **Separate dimensions.** A specific missed handoff may support communication; it does not automatically support collaboration or compliance awareness.
3. **Mixed evidence.** Use 3 when the same item gives specific evidence both for and against the dimension and does not establish a clear overall pattern. Do not average an unrelated positive and negative statement.
4. **Context matters.** Note role-relevant context in the reviewer rationale when available. Do not penalize an employee for workload, assignment, language, accessibility, or resource constraints outside their control.
5. **Avoid protected or personal traits.** Do not score or infer age, gender, ethnicity, disability, religion, family status, health, personality, or other protected/personal attributes. If such content appears, ignore it for scoring and flag the record for review according to the approved data-handling process.
6. **Do not use sentiment as a proxy.** Polite or enthusiastic wording is not proof of strong performance; critical wording is not proof of poor performance.
7. **Do not guess.** If translation, sarcasm, missing context, or ambiguous wording prevents reliable interpretation, leave the dimension unrated and flag it for adjudication.

## Independent review and disagreement

Two reviewers should label the same anonymized items independently before discussing them. They should not see each other's scores during the first pass. Compare ratings by feedback item and dimension. Discuss disagreements using the cited evidence and these anchors; record the final adjudicated value and rationale in the approved review process. Keep each original rating so disagreement is measurable rather than erased.

Before training, inspect disagreement rates and unrated rates by role, department, branch, feedback source, language, and time period where those comparisons are lawful and sufficiently de-identified. Investigate systematic differences in who receives feedback, how specific feedback is, and how reviewers apply the anchors. A model trained on biased or uneven labels can reproduce those patterns even if protected attributes are excluded from its features.

## Minimum record fields

Use the existing CSV header. `evidence_span` should be a short supporting excerpt or an approved reference to one; `annotator_id` should be a pseudonymous reviewer code; `rubric_version` should identify the rubric version used; and `dataset_source` should be `real_anonymized` or `synthetic_demo`. Never invent ratings to fill blank rows. Demo annotations may exercise the pipeline but cannot establish accuracy or fairness.

For the draft labels, the accepted values are integers 1–5 or blank for each dimension, `true`/`false` for `evidence_adequate`, a pseudonymous `annotator_id`, and the current rubric version. The current overall target training workflow still requires separate independently reviewed overall scores and an adjudicated 0–100 score.
