"""Automatically multi-label supervisor appraisal evidence and calculate grouped Trust Scores."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

import models


CATEGORIES = (
    "collaboration",
    "communication",
    "compliance_awareness",
    "learning_development",
)

KPI_GROUPS = {
    "operational_quality": ("transaction_accuracy", "error_frequencies"),
    "delivery_timeliness": (
        "workplan_completion",
        "task_deadline_fulfillment_pct",
        "loan_processing_turnaround_hours",
    ),
    "customer_outcomes": ("customer_satisfaction", "complaint_resolution_rate_pct"),
    "risk_controls": (
        "non_performing_credit_pct",
        "cash_reconciliation_errors",
        "compliance_incidents",
    ),
}

KPI_LABELS = {
    "transaction_accuracy": "Transaction accuracy",
    "error_frequencies": "Processing errors",
    "workplan_completion": "Workplan completion",
    "task_deadline_fulfillment_pct": "Tasks completed on time",
    "loan_processing_turnaround_hours": "Loan processing time",
    "customer_satisfaction": "Customer satisfaction",
    "complaint_resolution_rate_pct": "Complaint resolution",
    "non_performing_credit_pct": "Non-performing credit",
    "cash_reconciliation_errors": "Cash reconciliation errors",
    "compliance_incidents": "Compliance incidents",
}

# The supplied limits reflect the user's agreed demo rules. Non-performing credit
# uses the existing 18% demo ceiling until a bank-approved target is supplied.
LOWER_IS_BETTER_LIMITS = {
    "error_frequencies": 10.0,
    "loan_processing_turnaround_hours": 168.0,
    "non_performing_credit_pct": 18.0,
    "compliance_incidents": 2.0,
}


def _clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(maximum, value))


def _state(score: float | None) -> str:
    if score is None:
        return "No data"
    if score < 100 / 3:
        return "Danger"
    if score < 200 / 3:
        return "Warning"
    return "Safe"


def _metric_score(key: str, mean_value: float, period_values: list[float]) -> tuple[float, bool]:
    """Return a 0-100 quality score and a zero-tolerance cash-error flag."""
    if key == "cash_reconciliation_errors":
        breached = any(value > 0 for value in period_values)
        return (0.0 if breached else 100.0), breached
    if key == "customer_satisfaction":
        return _clamp((mean_value - 1.0) * 25.0), False
    if key in LOWER_IS_BETTER_LIMITS:
        limit = LOWER_IS_BETTER_LIMITS[key]
        return _clamp(100.0 * (1.0 - mean_value / limit)), False
    # Percentage and completion measures use 100% as their target; over-delivery
    # is capped so it cannot offset a weak competency elsewhere.
    return _clamp(mean_value), False


def build_kpi_groups(records: list[models.PerformanceRecord]) -> tuple[dict, bool]:
    groups: dict = {}
    cash_alert = False
    for group_key, metric_keys in KPI_GROUPS.items():
        metrics = []
        metric_scores = []
        for key in metric_keys:
            values = [float(getattr(row, key)) for row in records if getattr(row, key, None) is not None]
            if not values:
                metrics.append({
                    "key": key, "label": KPI_LABELS[key], "mean": None,
                    "score_0_100": None, "state": "No data", "sample_count": 0,
                })
                continue
            mean_value = sum(values) / len(values)
            score, breached = _metric_score(key, mean_value, values)
            cash_alert = cash_alert or breached
            metric_scores.append(score)
            metrics.append({
                "key": key,
                "label": KPI_LABELS[key],
                "mean": round(mean_value, 2),
                "score_0_100": round(score, 1),
                "state": _state(score),
                "sample_count": len(values),
                "zero_tolerance_breach": breached if key == "cash_reconciliation_errors" else False,
            })
        group_score = round(sum(metric_scores) / len(metric_scores), 1) if metric_scores else None
        groups[group_key] = {
            "label": group_key.replace("_", " ").title(),
            "score_0_100": group_score,
            "state": _state(group_score),
            "metrics": metrics,
        }
    return groups, cash_alert


def _extract_form_items(
    employee_id: int,
    supervisor_appraisals: list[models.SupervisorAppraisal],
) -> list[dict]:
    """Extract supervisor answers only; question categories are not classifier labels."""
    items: list[dict] = []
    for appraisal in supervisor_appraisals:
        answers = appraisal.answers_snapshot if isinstance(appraisal.answers_snapshot, list) else []
        for index, answer in enumerate(answers):
            if not isinstance(answer, dict):
                continue
            text = answer.get("answer")
            if isinstance(text, str) and text.strip():
                items.append({
                    "employee_id": employee_id,
                    "source_type": "supervisor_appraisal",
                    "supervisor_appraisal_id": appraisal.appraisal_id,
                    "feedback_id": None,
                    "item_key": str(answer.get("id") or answer.get("question_id") or f"answer_{index + 1}"),
                    "statement_text": text.strip(),
                })
    return items


def _predict_competencies(model, thresholds: dict[str, float], statement: str) -> list[tuple[str, float]]:
    """Return every competency whose independently trained probability meets its cutoff."""
    probabilities = model.predict_proba([" ".join(statement.lower().split())])[0]
    if len(probabilities) != len(CATEGORIES):
        raise ValueError(
            f"Competency model returned {len(probabilities)} columns; expected {len(CATEGORIES)}."
        )
    predicted = []
    for category, probability in zip(CATEGORIES, probabilities):
        cutoff = float(thresholds.get(category, 0.5))
        if float(probability) >= cutoff:
            predicted.append((category, float(probability)))
    return predicted


def _classify_direction(model, category: str, statement: str) -> tuple[str, float, dict]:
    model_input = f"{category.lower()} [SEP] {' '.join(statement.lower().split())}"
    classifier = model.named_steps["classifier"]
    labels = [str(label) for label in classifier.classes_]
    probabilities = model.predict_proba([model_input])[0]
    probability_map = {label: round(float(probability), 6) for label, probability in zip(labels, probabilities)}
    direction = str(model.predict([model_input])[0]).lower()
    if direction not in {"negative", "positive", "mixed", "neutral"}:
        raise ValueError(f"Unsupported appraisal direction label: {direction}")
    return direction, probability_map.get(direction, 0.0), probability_map


def _upsert_classification(
    db: Session,
    item: dict,
    category: str,
    category_probability: float,
    direction_model,
    model_version: str,
):
    query = db.query(models.FeedbackClassification).filter_by(
        supervisor_appraisal_id=item["supervisor_appraisal_id"],
        item_key=item["item_key"],
        category=category,
    )
    existing = query.first()
    direction, confidence, direction_probabilities = _classify_direction(
        direction_model, category, item["statement_text"]
    )
    probability_payload = {
        "competency_probability": round(category_probability, 6),
        "direction_probabilities": direction_probabilities,
    }
    if existing:
        existing.employee_id = item["employee_id"]
        existing.statement_text = item["statement_text"]
        existing.predicted_direction = direction
        existing.confidence = confidence
        existing.probabilities = probability_payload
        existing.review_status = "auto_classified"
        existing.confirmed_direction = None
        existing.reviewed_by_employee_id = None
        existing.reviewed_at = None
        existing.model_version = model_version
        existing.is_current = True
        return existing
    row = models.FeedbackClassification(
        **{key: item[key] for key in (
            "employee_id", "source_type", "supervisor_appraisal_id", "feedback_id",
            "item_key", "statement_text",
        )},
        category=category,
        predicted_direction=direction,
        confidence=confidence,
        probabilities=probability_payload,
        review_status="auto_classified",
        is_current=True,
        model_version=model_version,
    )
    db.add(row)
    db.flush()
    return row


def get_period_classifications(
    db: Session,
    employee_id: int,
    start: datetime,
    end: datetime,
) -> tuple[list[models.FeedbackClassification], list[models.SupervisorAppraisal], list[models.UnstructuredFeedback]]:
    appraisals = db.query(models.SupervisorAppraisal).filter(
        models.SupervisorAppraisal.employee_id == employee_id,
        models.SupervisorAppraisal.created_at >= start,
        models.SupervisorAppraisal.created_at < end,
    ).all()
    feedback_rows: list[models.UnstructuredFeedback] = []
    appraisal_ids = [row.appraisal_id for row in appraisals]
    classifications = db.query(models.FeedbackClassification).filter(
        models.FeedbackClassification.employee_id == employee_id,
        models.FeedbackClassification.source_type == "supervisor_appraisal",
        models.FeedbackClassification.is_current.is_(True),
        models.FeedbackClassification.supervisor_appraisal_id.in_(appraisal_ids) if appraisal_ids else False,
    ).order_by(
        models.FeedbackClassification.category,
        models.FeedbackClassification.supervisor_appraisal_id,
        models.FeedbackClassification.item_key,
    ).all()
    return classifications, appraisals, feedback_rows


def build_feedback_groups(rows: Iterable[models.FeedbackClassification]) -> tuple[dict, int]:
    """Score only automatic direction predictions on supervisor appraisal answers."""
    rows = [row for row in rows if row.review_status == "auto_classified"]
    groups = {}
    for category in CATEGORIES:
        category_rows = [row for row in rows if row.category == category]
        positive = [row for row in category_rows if row.predicted_direction == "positive"]
        negative = [row for row in category_rows if row.predicted_direction == "negative"]
        mixed_neutral = [row for row in category_rows if row.predicted_direction in ("mixed", "neutral")]
        scored_count = len(positive) + len(negative)
        category_score = round(100.0 * len(positive) / scored_count, 1) if scored_count else None
        groups[category] = {
            "label": category.replace("_", " ").title(),
            "score_0_100": category_score,
            "state": _state(category_score),
            "classification_count": len(category_rows),
            "positive_count": len(positive),
            "negative_count": len(negative),
            "mixed_or_neutral_count": len(mixed_neutral),
            "score_rule": "Automatic direction predictions on supervisor answers: positive=100, negative=0; mixed/neutral are not numerically scored.",
        }
    return groups, 0


def score_status(kpi_groups: dict, feedback_groups: dict, pending_count: int = 0) -> tuple[float | None, str]:
    group_scores = [
        item.get("score_0_100")
        for item in [*kpi_groups.values(), *feedback_groups.values()]
    ]
    if all(score is not None for score in group_scores) and len(group_scores) == 8:
        return round(sum(float(score) for score in group_scores) / 8, 1), "ready"
    return None, "incomplete"


def serialize_classification(row: models.FeedbackClassification) -> dict:
    return {
        "classification_id": row.classification_id,
        "employee_id": row.employee_id,
        "source_type": row.source_type,
        "supervisor_appraisal_id": row.supervisor_appraisal_id,
        "feedback_id": row.feedback_id,
        "item_key": row.item_key,
        "category": row.category,
        "statement_text": row.statement_text,
        "predicted_direction": row.predicted_direction,
        "confidence": round(float(row.confidence), 4),
        "probabilities": row.probabilities,
        "review_status": row.review_status,
        "confirmed_direction": row.confirmed_direction,
        "model_version": row.model_version,
        "reviewed_at": row.reviewed_at,
    }


def serialize_run(run: models.TrustScoreRun, classifications: list[models.FeedbackClassification]) -> dict:
    return {
        "run_id": run.run_id,
        "employee_id": run.employee_id,
        "period_type": run.period_type,
        "period_code": run.period_code,
        "period_start": run.period_start,
        "period_end": run.period_end,
        "kpi_groups": run.kpi_groups,
        "feedback_groups": run.feedback_groups,
        "trust_score": run.trust_score,
        "score_status": run.score_status,
        "data_coverage": run.data_coverage,
        "generated_at": run.generated_at,
        "classifications": [serialize_classification(row) for row in classifications],
    }


def recalculate_run(db: Session, run: models.TrustScoreRun) -> list[models.FeedbackClassification]:
    rows, appraisals, _ = get_period_classifications(
        db, run.employee_id, run.period_start, run.period_end
    )
    feedback_groups, _ = build_feedback_groups(rows)
    trust_score, status = score_status(run.kpi_groups, feedback_groups)
    run.feedback_groups = feedback_groups
    run.trust_score = trust_score
    run.score_status = status
    coverage = dict(run.data_coverage or {})
    coverage.update({
        "supervisor_form_count": len(appraisals),
        "employee_followup_count": 0,
        "employee_followups_scored": False,
        "classified_answer_category_count": len(rows),
        "pending_review_count": 0,
        "scored_group_count": sum(
            item.get("score_0_100") is not None
            for item in [*run.kpi_groups.values(), *feedback_groups.values()]
        ),
    })
    run.data_coverage = coverage
    run.generated_at = datetime.now(run.period_start.tzinfo)
    return rows


def generate_run(
    db: Session,
    employee_id: int,
    generated_by_employee_id: int,
    period_type: str,
    period_code: str,
    start: datetime,
    end: datetime,
    competency_model,
    competency_thresholds: dict[str, float],
    direction_model,
    model_version: str,
) -> tuple[models.TrustScoreRun, list[models.FeedbackClassification]]:
    if competency_model is None:
        raise RuntimeError("The multi-label competency model is unavailable.")
    if direction_model is None:
        raise RuntimeError("The appraisal direction model is unavailable.")
    employee = db.query(models.Employee).filter_by(employee_id=employee_id, is_active=True).first()
    if employee is None:
        raise LookupError("Employee not found")
    records = db.query(models.PerformanceRecord).filter(
        models.PerformanceRecord.employee_id == employee_id,
        models.PerformanceRecord.recorded_at >= start,
        models.PerformanceRecord.recorded_at < end,
    ).order_by(models.PerformanceRecord.recorded_at.asc()).all()
    appraisals = db.query(models.SupervisorAppraisal).filter(
        models.SupervisorAppraisal.employee_id == employee_id,
        models.SupervisorAppraisal.created_at >= start,
        models.SupervisorAppraisal.created_at < end,
    ).all()
    items = _extract_form_items(employee_id, appraisals)
    appraisal_ids = [row.appraisal_id for row in appraisals]
    if appraisal_ids:
        # Retain previous rows for audit, but only the current model's categories
        # can feed this period's score.
        db.query(models.FeedbackClassification).filter(
            models.FeedbackClassification.supervisor_appraisal_id.in_(appraisal_ids)
        ).update({
            models.FeedbackClassification.is_current: False,
            models.FeedbackClassification.review_status: "superseded",
        }, synchronize_session=False)
    assigned_category_count = 0
    unassigned_answer_count = 0
    for item in items:
        selected_categories = _predict_competencies(
            competency_model, competency_thresholds, item["statement_text"]
        )
        if not selected_categories:
            unassigned_answer_count += 1
        for category, probability in selected_categories:
            _upsert_classification(
                db, item, category, probability, direction_model, model_version
            )
            assigned_category_count += 1
    db.flush()

    classifications, appraisals, _ = get_period_classifications(
        db, employee_id, start, end
    )
    kpi_groups, cash_alert = build_kpi_groups(records)
    feedback_groups, _ = build_feedback_groups(classifications)
    trust_score, status = score_status(kpi_groups, feedback_groups)
    coverage = {
        "performance_record_count": len(records),
        "supervisor_form_count": len(appraisals),
        "employee_followups_scored": False,
        "supervisor_answer_count": len(items),
        "unassigned_supervisor_answer_count": unassigned_answer_count,
        "classified_answer_category_count": assigned_category_count,
        "pending_review_count": 0,
        "scored_group_count": sum(
            item.get("score_0_100") is not None
            for item in [*kpi_groups.values(), *feedback_groups.values()]
        ),
        "cash_reconciliation_zero_tolerance_alert": cash_alert,
    }

    run = db.query(models.TrustScoreRun).filter_by(
        employee_id=employee_id, period_type=period_type, period_code=period_code
    ).first()
    if run is None:
        run = models.TrustScoreRun(
            employee_id=employee_id,
            generated_by_employee_id=generated_by_employee_id,
            period_type=period_type,
            period_code=period_code,
            period_start=start,
            period_end=end,
            kpi_groups=kpi_groups,
            feedback_groups=feedback_groups,
            data_coverage=coverage,
            trust_score=trust_score,
            score_status=status,
        )
        db.add(run)
    else:
        run.generated_by_employee_id = generated_by_employee_id
        run.period_start = start
        run.period_end = end
        run.kpi_groups = kpi_groups
        run.feedback_groups = feedback_groups
        run.data_coverage = coverage
        run.trust_score = trust_score
        run.score_status = status
        run.generated_at = datetime.now(start.tzinfo)
    db.flush()
    return run, classifications

