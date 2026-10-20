"""Append synthetic feedback examples to PostgreSQL without resetting existing data."""

import argparse
import csv
from datetime import datetime
from pathlib import Path

import models
from database import SessionLocal

CSV_FILE = Path(__file__).resolve().parent / "data" / "feedback_demo" / "feedback_records.csv"


def load():
    if not CSV_FILE.exists():
        raise FileNotFoundError("Run generate_feedback_demo.py first.")
    with CSV_FILE.open("r", newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError("Synthetic feedback CSV contains no rows.")
    if any(row.get("data_source") != "synthetic_demo" for row in rows):
        raise ValueError("This loader accepts only rows explicitly tagged synthetic_demo.")

    with SessionLocal() as session:
        if session.query(models.UnstructuredFeedback.feedback_id).filter_by(data_source="synthetic_demo").first():
            raise RuntimeError("Synthetic feedback already exists. Loader will not duplicate it.")
        employee_ids = {row[0] for row in session.query(models.Employee.employee_id).all()}
        supervisor_ids = {row[0] for row in session.query(models.ImmediateSupervisor.supervisor_id).all()}
        missing_employee_ids = {int(row["employee_id"]) for row in rows} - employee_ids
        missing_author_ids = {int(row["author_employee_id"]) for row in rows} - employee_ids
        missing_supervisor_ids = {int(row["supervisor_id"]) for row in rows} - supervisor_ids
        if missing_employee_ids or missing_author_ids or missing_supervisor_ids:
            raise RuntimeError("Feedback CSV has account references missing from PostgreSQL; no rows were loaded.")
        feedback_rows = [models.UnstructuredFeedback(
            employee_id=int(row["employee_id"]),
            supervisor_id=int(row["supervisor_id"]),
            author_employee_id=int(row["author_employee_id"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            narrative_text=row["narrative_text"],
            sentiment_polarity_value=float(row["sentiment_polarity_value"]),
            data_source="synthetic_demo",
        ) for row in rows]
        session.add_all(feedback_rows)
        session.commit()
    tones = {}
    for row in rows:
        tones[row["tone_label"]] = tones.get(row["tone_label"], 0) + 1
    print(f"Loaded {len(rows)} synthetic feedback rows; existing records were preserved.")
    print(f"Polarity mix in the generated file: {tones}")


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    load()
