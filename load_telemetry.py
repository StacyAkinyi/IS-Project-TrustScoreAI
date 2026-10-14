"""Load the generated demonstration KPI history into PostgreSQL."""

import argparse
import csv
from datetime import datetime
from pathlib import Path

import models
from database import SessionLocal

CSV_FILE = Path(__file__).resolve().parent / "data" / "telemetry_demo" / "performance_records.csv"


def load():
    if not CSV_FILE.exists():
        raise FileNotFoundError("Run generate_telemetry.py first.")

    with CSV_FILE.open("r", newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError("Telemetry CSV contains no rows.")

    with SessionLocal() as session:
        if session.query(models.PerformanceRecord.record_id).first():
            raise RuntimeError(
                "Performance records already exist. This loader will not duplicate or replace them."
            )
        employee_ids = {
            item[0] for item in session.query(models.Employee.employee_id).all()
        }
        missing = sorted({int(row["employee_id"]) for row in rows} - employee_ids)
        if missing:
            raise RuntimeError(
                "Some seed employees are missing from PostgreSQL. Load base accounts first."
            )

        records = []
        for row in rows:
            records.append(models.PerformanceRecord(
                employee_id=int(row["employee_id"]),
                recorded_at=datetime.fromisoformat(row["recorded_at"]),
                loan_volumes=int(row["loan_volumes"]),
                transaction_accuracy=float(row["transaction_accuracy"]),
                workplan_completion=float(row["workplan_completion"]),
                error_frequencies=int(row["error_frequencies"]),
                loan_processing_turnaround_hours=float(row["loan_processing_turnaround_hours"]),
                accounts_opened=int(row["accounts_opened"]),
                non_performing_credit_pct=float(row["non_performing_credit_pct"]),
                task_deadline_fulfillment_pct=float(row["task_deadline_fulfillment_pct"]),
                cash_reconciliation_errors=int(row["cash_reconciliation_errors"]),
                customer_satisfaction=float(row["customer_satisfaction"]),
                compliance_incidents=int(row["compliance_incidents"]),
                complaint_resolution_rate_pct=float(row["complaint_resolution_rate_pct"]),
                digital_channel_adoption_pct=float(row["digital_channel_adoption_pct"]),
                feedback_text=row["feedback_text"] or None,
                truthfulness_weight=float(row["truthfulness_weight"]),
                reliability_target=int(row["reliability_target"]),
            ))
        session.add_all(records)
        session.commit()
        print(f"Loaded {len(records)} synthetic performance records for {len({r.employee_id for r in records})} employees.")


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    load()
