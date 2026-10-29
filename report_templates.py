"""Deterministic, offline narrative templates for TrustScoreAI period reports."""

from __future__ import annotations

from typing import Any


DIMENSION_LABELS = {
    "communication": "Communication",
    "collaboration": "Collaboration",
    "compliance_awareness": "Compliance awareness",
    "learning_development": "Learning and development",
}

GROUP_LABELS = {
    "operational_quality": "Operational quality",
    "delivery_timeliness": "Delivery and timeliness",
    "customer_outcomes": "Customer outcomes",
    "risk_controls": "Risk and controls",
}

SAFE_CUTOFF = 200 / 3
WARNING_CUTOFF = 100 / 3


def report_period_label(period_type: str, period_code: str) -> str:
    """Return a readable label while retaining the stable database period code."""
    if period_type == "quarterly":
        return f"Quarter {period_code.rsplit('Q', 1)[-1]} of {period_code[:4]} ({period_code})"
    if period_type == "semiannual":
        return f"Half {period_code.rsplit('H', 1)[-1]} of {period_code[:4]} ({period_code})"
    return f"Annual review for {period_code}"


def _score_state(score: Any) -> str:
    if not isinstance(score, (int, float)):
        return "No data"
    if score < WARNING_CUTOFF:
        return "Danger"
    if score < SAFE_CUTOFF:
        return "Warning"
    return "Safe"


def _quote_excerpt(text: Any, limit: int = 220) -> str | None:
    if not isinstance(text, str):
        return None
    value = " ".join(text.split())
    if not value:
        return None
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


def _dimension_summary(label: str, item: dict, examples: list[dict]) -> tuple[str, list[dict]]:
    positive = int(item.get("positive_count") or 0)
    negative = int(item.get("negative_count") or 0)
    mixed_neutral = int(item.get("mixed_or_neutral_count") or 0)
    total = int(item.get("classification_count") or 0)
    score = item.get("score_0_100")

    if positive + negative:
        score_text = f"{score:.1f}% positive among the numerically scored classifications" if score is not None else "a numeric percentage is unavailable"
        summary = (
            f"The model assigned {positive} positive and {negative} negative {label.lower()} classification(s) "
            f"({score_text}). {mixed_neutral} mixed or neutral item(s) are shown as context and are not scored."
        )
    elif mixed_neutral:
        summary = (
            f"No positive or negative {label.lower()} classifications are available for a numeric rate. "
            f"There are {mixed_neutral} mixed or neutral item(s), which remain contextual and unscored."
        )
    elif total:
        summary = f"{total} {label.lower()} classification(s) are present, but none has a scorable positive or negative direction."
    else:
        summary = f"No supervisor-classified {label.lower()} evidence is available for this period."

    selected = []
    for direction, title in (("positive", "Example classified positive"), ("negative", "Example classified negative")):
        match = next((row for row in examples if row.get("direction") == direction and _quote_excerpt(row.get("statement"))), None)
        if match:
            selected.append({"direction": direction, "label": title, "text": _quote_excerpt(match.get("statement"))})
    return summary, selected


def build_local_report(
    *,
    period_type: str,
    period_code: str,
    telemetry_groups: dict,
    feedback_groups: dict,
    supervisor_evidence: dict,
    coverage: dict,
) -> tuple[dict, dict]:
    """Build report narrative and feedback payload without network or model calls.

    This function uses only supplied KPI group results and saved supervisor-answer
    classifier outputs. It does not calculate a Trust Score or reinterpret labels.
    """
    period_label = report_period_label(period_type, period_code)
    available_groups = []
    states = {"Safe": 0, "Warning": 0, "Danger": 0, "No data": 0}
    all_groups = [
        (GROUP_LABELS.get(key, key.replace("_", " ").title()), value)
        for key, value in telemetry_groups.items()
    ]
    all_groups.extend(
        (DIMENSION_LABELS.get(key, key.replace("_", " ").title()), value)
        for key, value in feedback_groups.items()
    )
    for label, group in all_groups:
        state = group.get("state") or _score_state(group.get("score_0_100"))
        states[state if state in states else "No data"] += 1
        if group.get("score_0_100") is not None:
            available_groups.append(label)

    record_count = int(coverage.get("telemetry_records") or 0)
    months = int(coverage.get("telemetry_months") or 0)
    form_count = int(coverage.get("supervisor_forms") or 0)
    answer_count = int(coverage.get("supervisor_answers") or 0)
    assigned_count = int(coverage.get("classified_answer_category_assignments") or 0)
    distinct_answer_count = int(coverage.get("distinct_classified_answers") or 0)

    if available_groups:
        state_summary = (
            f"Of the eight KPI and feedback groups, {states['Safe']} are in the Safe band, "
            f"{states['Warning']} in Warning, {states['Danger']} in Danger, and {states['No data']} have no numeric data."
        )
    else:
        state_summary = "None of the eight KPI and feedback groups has a numeric value for this period."

    summary = (
        f"{period_label}: {record_count} monthly KPI record(s) cover {months} month(s), and "
        f"{form_count} supervisor appraisal form(s) contain {answer_count} answered item(s). "
        f"The classifier produced {assigned_count} answer-category assignment(s) across "
        f"{distinct_answer_count} distinct supervisor answer(s). {state_summary} "
        "This narrative is assembled from saved values using local templates; it does not calculate or change the Trust Score."
    )

    normalized_dimensions = {}
    feedback_summaries = {}
    for key, label in DIMENSION_LABELS.items():
        group = feedback_groups.get(key, {})
        evidence = supervisor_evidence.get(key, {})
        evidence_summary, examples = _dimension_summary(label, group, evidence.get("evidence", []))
        normalized_dimensions[key] = {
            "score_0_100": group.get("score_0_100"),
            "state": group.get("state", "No data"),
            "positive_count": int(group.get("positive_count") or 0),
            "negative_count": int(group.get("negative_count") or 0),
            "mixed_or_neutral_count": int(group.get("mixed_or_neutral_count") or 0),
            "classification_count": int(group.get("classification_count") or 0),
            "evidence_summary": evidence_summary,
            "examples": examples,
            "rating_source": "supervisor_answer_classifier",
        }
        feedback_summaries[key] = evidence_summary

    strengths = []
    development_priorities = []
    for key, group in telemetry_groups.items():
        label = GROUP_LABELS.get(key, group.get("label", key.replace("_", " ").title()))
        score = group.get("score_0_100")
        state = group.get("state", _score_state(score))
        if score is None:
            continue
        if state == "Safe":
            strengths.append(f"{label} is in the Safe band ({score:.1f}/100) for this period.")
        elif state in ("Warning", "Danger"):
            development_priorities.append(f"Review {label} ({state.lower()}, {score:.1f}/100) with the underlying monthly metrics.")

    for key, group in feedback_groups.items():
        label = DIMENSION_LABELS.get(key, group.get("label", key.replace("_", " ").title()))
        score = group.get("score_0_100")
        state = group.get("state", _score_state(score))
        positive = int(group.get("positive_count") or 0)
        negative = int(group.get("negative_count") or 0)
        if score is None:
            continue
        if state == "Safe" and positive:
            strengths.append(f"{label} has more positive than negative classified evidence ({positive} positive, {negative} negative; {score:.1f}%).")
        elif state in ("Warning", "Danger") and negative:
            development_priorities.append(f"Discuss {label} evidence with the employee ({positive} positive, {negative} negative classifications; {score:.1f}% positive).")

    if not strengths:
        strengths.append("There is not enough numeric evidence in this period to identify a group-level strength.")
    if not development_priorities:
        development_priorities.append("No KPI or feedback group fell in the Warning or Danger band based on the available numeric evidence.")

    caveats = [
        "This report uses fixed local text templates; no OpenAI API or other paid text-generation service is called.",
        "Feedback summaries use the saved classifier's positive, negative, mixed and neutral labels for supervisor answers only. The classifier can make mistakes; examples retain their predicted labels and are not independently verified.",
        "Mixed and neutral feedback is contextual and excluded from numeric feedback percentages. Employee follow-up answers are excluded from classification, feedback scoring and this report.",
        "Safe, Warning and Danger bands are demonstration thresholds, not approved bank policy. Review underlying evidence and role-specific expectations before taking action.",
        "Missing data means insufficient evidence, not poor performance. This report is descriptive decision support and does not recommend hiring, promotion, discipline or termination.",
    ]
    missing_groups = [label for label, group in all_groups if group.get("score_0_100") is None]
    if missing_groups:
        caveats.append("No numeric evidence was available for: " + ", ".join(missing_groups) + ".")

    narrative = {
        "generation_method": "local_templates_v1",
        "period_label": period_label,
        "summary": summary,
        "feedback_summaries": feedback_summaries,
        "feedback_dimensions": normalized_dimensions,
        "strengths": strengths[:6],
        "development_priorities": development_priorities[:6],
        "caveats": caveats[:8],
    }
    return narrative, normalized_dimensions
