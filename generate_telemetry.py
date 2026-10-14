"""Create reproducible demonstration KPI history for synthetic employee accounts."""

import csv
import random
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EMPLOYEES_FILE = ROOT / "data" / "base_seed" / "employees.csv"
OUTPUT_DIR = ROOT / "data" / "telemetry_demo"
OUTPUT_FILE = OUTPUT_DIR / "performance_records.csv"
SEED = 20261014
MONTHS = 12
FIELDS = [
    "employee_id", "recorded_at", "loan_volumes", "transaction_accuracy",
    "workplan_completion", "error_frequencies", "loan_processing_turnaround_hours",
    "accounts_opened", "non_performing_credit_pct", "task_deadline_fulfillment_pct",
    "cash_reconciliation_errors", "customer_satisfaction", "compliance_incidents",
    "complaint_resolution_rate_pct", "digital_channel_adoption_pct",
    "feedback_text", "truthfulness_weight", "reliability_target",
]


def clamp(value, low, high):
    return max(low, min(high, value))


def generate():
    if not EMPLOYEES_FILE.exists():
        raise FileNotFoundError("Run generate_data.py first to create base employee accounts.")

    with EMPLOYEES_FILE.open("r", newline="", encoding="utf-8") as stream:
        employees = [
            row for row in csv.DictReader(stream)
            if row["user_type"] == "employee"
        ]
    if not employees:
        raise ValueError("No employee accounts found in the base seed.")

    rng = random.Random(SEED)
    profiles = {
        int(employee["employee_id"]): rng.choices(
            [0.84, 0.64, 0.43], weights=[0.30, 0.45, 0.25], k=1
        )[0]
        for employee in employees
    }

    now = datetime.now(timezone.utc)
    month_starts = []
    for offset in range(MONTHS - 1, -1, -1):
        index = now.year * 12 + now.month - 1 - offset
        month_starts.append(datetime(index // 12, index % 12 + 1, 1, tzinfo=timezone.utc))

    rows = []
    for employee in employees:
        employee_id = int(employee["employee_id"])
        baseline = profiles[employee_id]
        for month_index, recorded_at in enumerate(month_starts):
            progress = (month_index - (MONTHS - 1) / 2) * 0.008
            quality = clamp(baseline + progress + rng.gauss(0, 0.09), 0.15, 0.98)
            row = {
                "employee_id": employee_id,
                "recorded_at": recorded_at.isoformat(),
                "loan_volumes": round(clamp(28 + quality * 115 + rng.gauss(0, 28), 0, 220)),
                "transaction_accuracy": round(clamp(82 + quality * 18 + rng.gauss(0, 2.5), 70, 100), 2),
                "workplan_completion": round(clamp(42 + quality * 68 + rng.gauss(0, 9), 30, 120), 2),
                "error_frequencies": round(clamp((1 - quality) * 12 + rng.gauss(0, 2), 0, 15)),
                "loan_processing_turnaround_hours": round(clamp(10 + (1 - quality) * 58 + rng.gauss(0, 9), 3, 96), 2),
                "accounts_opened": round(clamp(quality * 30 + rng.gauss(0, 7), 0, 50)),
                "non_performing_credit_pct": round(clamp((1 - quality) * 11 + rng.gauss(0, 2), 0, 18), 2),
                "task_deadline_fulfillment_pct": round(clamp(47 + quality * 52 + rng.gauss(0, 8), 35, 100), 2),
                "cash_reconciliation_errors": round(clamp((1 - quality) * 7 + rng.gauss(0, 1.5), 0, 10)),
                "customer_satisfaction": round(clamp(1.8 + quality * 3.1 + rng.gauss(0, 0.4), 1, 5), 2),
                "compliance_incidents": 0 if rng.random() > (0.02 + (1 - quality) * 0.25) else rng.choices([1, 2, 3], [0.65, 0.27, 0.08])[0],
                "complaint_resolution_rate_pct": round(clamp(52 + quality * 46 + rng.gauss(0, 9), 30, 100), 2),
                "digital_channel_adoption_pct": round(clamp(18 + quality * 72 + rng.gauss(0, 12), 5, 100), 2),
                "feedback_text": "",
                "truthfulness_weight": round(rng.uniform(0.65, 1.0), 2),
                "reliability_target": 1 if rng.random() < 0.9 else 0,
            }
            rows.append(row)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Generated {len(rows)} monthly telemetry rows for {len(employees)} synthetic employees.")
    print(f"CSV file: {OUTPUT_FILE}")
    print("All KPI values are synthetic demonstrations, not calibrated employment standards.")


if __name__ == "__main__":
    generate()
