"""Generate varied synthetic feedback examples for local pipeline demonstrations only."""

import csv
import random
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EMPLOYEES_FILE = ROOT / "data" / "base_seed" / "employees.csv"
SUPERVISORS_FILE = ROOT / "data" / "base_seed" / "immediate_supervisors.csv"
OUTPUT_DIR = ROOT / "data" / "feedback_demo"
OUTPUT_FILE = OUTPUT_DIR / "feedback_records.csv"
SEED = 20261017

COMMENT_BANK = {
    "communication": {
        "positive": [
            "Shared clear handovers for {work_item}, including the owner and next action.",
            "Explained the status of {work_item} promptly, so the team could plan the follow-up.",
            "Recorded concise updates on {work_item} and responded to colleagues' clarification requests.",
            "Flagged a change affecting {work_item} early and gave the relevant team a clear update.",
        ],
        "negative": [
            "Updates on {work_item} arrived after the agreed handover, leaving the next action unclear.",
            "Two messages about {work_item} omitted key details and needed follow-up questions.",
            "The status of {work_item} was not shared with the next owner before the deadline.",
            "A change to {work_item} was not communicated to the team until they asked for an update.",
        ],
        "neutral": [
            "A handover note for {work_item} was recorded; the available notes do not show whether the next owner received it.",
            "The log lists updates about {work_item}, but does not describe their clarity or timing.",
            "There is not enough documented detail about communication on {work_item} to rate this area.",
            "The record confirms a status update for {work_item}, without evidence about its effect on follow-up.",
        ],
    },
    "collaboration": {
        "positive": [
            "Coordinated with a colleague to complete {work_item} before the shared deadline.",
            "Helped a teammate resolve a documented blocker in {work_item} and updated the shared tracker.",
            "Shared the workload for {work_item} and confirmed which actions each team member would handle.",
            "Passed a useful process note to the team while working on {work_item}.",
        ],
        "negative": [
            "The handoff for {work_item} was not completed with the next owner, delaying the shared task.",
            "A requested team update about {work_item} was missed, so colleagues had to repeat the follow-up.",
            "The shared tracker for {work_item} was not updated after the agreed team discussion.",
            "A colleague had to request the status of {work_item} more than once before work could continue.",
        ],
        "neutral": [
            "The record shows {work_item} was assigned to the team but does not identify individual contributions.",
            "A team discussion about {work_item} is noted; no follow-up actions or outcomes were recorded.",
            "There is not enough specific evidence in the notes to rate collaboration on {work_item}.",
            "The shared tracker contains an entry for {work_item}, with no detail about how the work was coordinated.",
        ],
    },
    "compliance_awareness": {
        "positive": [
            "Used the required checklist for {work_item} and documented the verification before closure.",
            "Raised a process exception on {work_item} through the documented escalation channel.",
            "Completed the required control step for {work_item} and recorded the supporting reference.",
            "Checked the applicable procedure before completing {work_item} and noted the verification.",
        ],
        "negative": [
            "The required verification step for {work_item} was missing from the record and had to be completed later.",
            "A procedure exception in {work_item} was not escalated through the expected channel at first.",
            "The checklist for {work_item} was incomplete when the case was submitted for review.",
            "The record for {work_item} does not show the required control check before closure.",
        ],
        "neutral": [
            "The available notes do not show whether the control step for {work_item} was required or completed.",
            "No compliance observation about {work_item} was recorded for this period.",
            "There is not enough evidence in this entry to rate compliance awareness for {work_item}.",
            "The record mentions {work_item} but does not include the relevant procedure or control outcome.",
        ],
    },
    "learning_development": {
        "positive": [
            "Applied the coaching point on {work_item} in a later case and recorded the updated process step.",
            "Completed the agreed practice on {work_item} and used the feedback in subsequent work.",
            "Asked for feedback on {work_item}, then documented the change made in the next review.",
            "Used a learning note about {work_item} to correct a later handover and shared the result.",
        ],
        "negative": [
            "The agreed follow-up practice for {work_item} was not completed by the review date.",
            "The same documented gap in {work_item} appeared again after coaching; no follow-up was recorded.",
            "The learning action for {work_item} remained open, with no progress note in this period.",
            "A requested update after coaching on {work_item} was not available at the review date.",
        ],
        "neutral": [
            "The notes mention coaching on {work_item}, but do not record a follow-up or outcome.",
            "No learning action related to {work_item} was recorded during this period.",
            "There is not enough evidence to assess how feedback on {work_item} was applied.",
            "The record notes a training session about {work_item} but no later work example.",
        ],
    },
}
WORK_ITEMS = [
    "a customer follow-up", "a loan file review", "a daily cash reconciliation",
    "a transaction correction", "a complaint resolution", "a branch handover",
    "a workplan task", "a KYC review", "a service request", "a month-end control check",
    "a digital banking support case", "a credit documentation request",
]
TONE_POLARITY = {"positive": (0.25, 0.9), "negative": (-0.9, -0.25), "neutral": (-0.12, 0.12)}
FIELDS = ["employee_id", "supervisor_id", "author_employee_id", "created_at", "narrative_text",
          "sentiment_polarity_value", "data_source", "tone_label", "dimension_tag"]


def _read(path):
    with path.open("r", newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def generate():
    if not EMPLOYEES_FILE.exists() or not SUPERVISORS_FILE.exists():
        raise FileNotFoundError("Run generate_data.py first to create the base employee seed.")
    employees = [row for row in _read(EMPLOYEES_FILE) if row["user_type"] == "employee"]
    supervisors = _read(SUPERVISORS_FILE)
    supervisor_by_id = {int(row["supervisor_id"]): row for row in supervisors}
    teams = {}
    for employee in employees:
        teams.setdefault(int(employee["supervisor_id"]), []).append(int(employee["employee_id"]))
    rng = random.Random(SEED)
    now = datetime.now(timezone.utc)
    month_indexes = [now.year * 12 + now.month - 1 - offset for offset in (10, 8, 6, 4, 2, 0)]
    dates = [datetime(index // 12, index % 12 + 1, 8, 12, tzinfo=timezone.utc) for index in month_indexes]
    rows = []
    dimensions = list(COMMENT_BANK)
    for employee in employees:
        employee_id = int(employee["employee_id"])
        supervisor_id = int(employee["supervisor_id"])
        supervisor = supervisor_by_id[supervisor_id]
        supervisor_employee_id = int(supervisor["emp_id"])
        tones = ["positive", "negative", "neutral"] * 2
        rng.shuffle(tones)
        chosen_dimensions = [rng.choice(dimensions) for _ in range(len(dates))]
        for index, (created_at, tone, dimension) in enumerate(zip(dates, tones, chosen_dimensions)):
            template = rng.choice(COMMENT_BANK[dimension][tone])
            work_item = rng.choice(WORK_ITEMS)
            comment = template.format(work_item=work_item)
            team = teams.get(supervisor_id, [])
            peer_ids = [candidate for candidate in team if candidate != employee_id]
            author_id = supervisor_employee_id if index % 3 == 0 or not peer_ids else rng.choice(peer_ids)
            low, high = TONE_POLARITY[tone]
            rows.append({
                "employee_id": employee_id,
                "supervisor_id": supervisor_id,
                "author_employee_id": author_id,
                "created_at": dates[index].isoformat(),
                "narrative_text": comment,
                "sentiment_polarity_value": round(rng.uniform(low, high), 2),
                "data_source": "synthetic_demo",
                "tone_label": tone,
                "dimension_tag": dimension,
            })
    rng.shuffle(rows)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    counts = {tone: sum(row["tone_label"] == tone for row in rows) for tone in TONE_POLARITY}
    print(f"Generated {len(rows)} synthetic feedback rows for {len(employees)} base employees.")
    print(f"Polarity mix: {counts}; every row is tagged synthetic_demo.")
    print(f"CSV file: {OUTPUT_FILE}")
    print("These examples are for pipeline demonstrations, not evidence of real-world model accuracy or fairness.")
    return OUTPUT_FILE


if __name__ == "__main__":
    generate()
