"""Generate synthetic base accounts and reporting lines for local setup only."""

import csv
import random
from pathlib import Path


SEED = 168327
EXECUTIVE_COUNT = 8
SUPERVISORS_PER_EXECUTIVE = 5
EMPLOYEES_PER_SUPERVISOR = 6
OUTPUT_DIR = Path(__file__).resolve().parent / "data" / "base_seed"

KENYAN_FIRST_NAMES = [
    "Akinyi", "Wanjiku", "Njeri", "Adhiambo", "Nyambura", "Atieno", "Wairimu",
    "Muthoni", "Chebet", "Jelagat", "Wambui", "Zawadi", "Asha", "Mariam",
    "Kamau", "Otieno", "Mwangi", "Mutua", "Omondi", "Barasa", "Kiptoo", "Kibet",
    "Maina", "Ochieng", "Njoroge", "Kariuki", "Munyua", "Abdi", "Hassan", "Linet",
    "Moraa", "Nyakio", "Wekesa", "Cheruiyot", "Kilonzo", "Muli", "Wafula", "Muriuki",
    "Kiplagat", "Saidi", "Mwangangi", "Faith", "Grace", "Brian", "Daniel", "Mary",
    "James", "John", "Peter", "Ruth", "Esther", "David", "Joseph", "Anne", "Mercy",
    "Samuel", "Elizabeth", "Michael", "Joyce", "George", "Catherine", "Paul", "Lucy",
]
LAST_NAMES = [
    "Achieng", "Wanjala", "Njuguna", "Omondi", "Kiptoo", "Muthama", "Wekesa",
    "Nyambura", "Kariuki", "Abdalla", "Kilonzo", "Barasa", "Cheruiyot", "Otieno",
    "Muriuki", "Wanjiru", "Mwangangi", "Kipchumba", "Ouma", "Naliaka", "Mwende",
    "Auma", "Koech", "Karanja", "Githinji", "Musyoka", "Mwakio", "Adan", "Sang",
    "Onyango", "Kimutai", "Munyoki", "Chepkirui", "Waithera", "Mboya", "Moraa",
    "Kiplimo", "Abdi", "Wasike", "Mumo", "Nyongesa", "Kipkemoi", "Smith", "Brown",
    "Taylor", "Wilson", "Martin", "Clark", "Lewis", "Walker", "Hall", "Young", "Allen",
    "King", "Scott", "Green", "Baker", "Hill", "Adams", "Moore", "White", "Harris",
]
LEGACY_FIRST_NAMES = [
    "Akinyi", "Wanjiku", "Njeri", "Adhiambo", "Nyambura", "Atieno", "Wairimu",
    "Muthoni", "Chebet", "Jelagat", "Wambui", "Zawadi", "Asha", "Mariam",
    "Kamau", "Otieno", "Mwangi", "Kipchoge", "Mutua", "Omondi", "Barasa",
    "Kiptoo", "Kibet", "Maina", "Ochieng", "Njoroge", "Kariuki", "Munyua",
    "Abdi", "Hassan", "Linet", "Moraa", "Nyakio", "Wekesa", "Cheruiyot",
    "Kilonzo", "Muli", "Wafula", "Muriuki", "Kiplagat", "Saidi", "Mwangangi",
]
LEGACY_LAST_NAMES = [
    "Achieng", "Wanjala", "Njuguna", "Omondi", "Kiptoo", "Muthama", "Wekesa",
    "Nyambura", "Kariuki", "Abdalla", "Kilonzo", "Barasa", "Cheruiyot", "Otieno",
    "Muriuki", "Wanjiru", "Mwangangi", "Kipchumba", "Ouma", "Naliaka", "Mwende",
    "Auma", "Koech", "Karanja", "Githinji", "Musyoka", "Mwakio", "Adan", "Sang",
    "Onyango", "Kimutai", "Munyoki", "Chepkirui", "Waithera", "Mboya", "Moraa",
    "Kiplimo", "Abdi", "Wasike", "Mumo", "Nyongesa", "Kipkemoi",
]

FIRST_NAMES = list(dict.fromkeys(KENYAN_FIRST_NAMES))
LAST_NAMES = list(dict.fromkeys(LAST_NAMES))
REGIONS = [
    "Nairobi", "Coast", "Western", "Rift Valley", "Central", "Eastern", "Nyanza", "North Eastern",
]
BRANCHES = {
    "Nairobi": ["NBO-CBD", "NBO-Westlands", "NBO-Kilimani", "NBO-Upperhill"],
    "Coast": ["MSA-Island", "MSA-Nyali", "KLF-CBD"],
    "Western": ["KSM-Central", "KAK-CBD", "BGM-Central"],
    "Rift Valley": ["NKU-CBD", "ELD-CBD", "NKR-Central"],
    "Central": ["THK-Industrial", "NYR-CBD", "KRG-Central"],
    "Eastern": ["MAC-CBD", "MER-Central", "EMB-CBD"],
    "Nyanza": ["KSM-Milimani", "HOM-CBD", "MIG-Central"],
    "North Eastern": ["GAR-CBD", "WJR-Central"],
}
DEPARTMENTS = [
    "Retail Banking", "Credit Processing", "Branch Operations", "Compliance",
    "Customer Service", "Corporate Banking", "Digital Banking", "Risk and Audit",
]
JOB_ROLES = [
    "Teller", "Credit Officer", "Customer Service Officer",
    "Relationship Officer", "Operations Analyst",
]


def write_csv(filename: str, rows: list[dict]) -> None:
    path = OUTPUT_DIR / filename
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def generate() -> Path:
    rng = random.Random(SEED)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    employees = []
    executives = []
    supervisors = []
    employee_id = 1
    supervisor_id = 1
    account_count = EXECUTIVE_COUNT * (1 + SUPERVISORS_PER_EXECUTIVE * (1 + EMPLOYEES_PER_SUPERVISOR))
    name_candidates = [f"{first} {last}" for first in FIRST_NAMES for last in LAST_NAMES]
    if len(name_candidates) < account_count:
        raise ValueError("The unique name pool is smaller than the configured account count.")
    name_rng = random.Random(SEED + 1)
    names = iter(name_rng.sample(name_candidates, k=account_count))

    def next_full_name():
        # Preserve the original seeded sequence for branch, department, and role values.
        rng.choice(LEGACY_FIRST_NAMES)
        rng.choice(LEGACY_LAST_NAMES)
        return next(names)

    # The employee table is the identity table for every role. Role-specific
    # tables below only hold the fields shown in the class/ER diagrams.
    for executive_id, region in enumerate(REGIONS, start=1):
        employees.append({
            "employee_id": employee_id,
            "full_name": next_full_name(),
            "email": f"employee{employee_id}@trustscore.test",
            "department": "Executive Management",
            "role": "Executive Manager",
            "user_type": "executive",
            "supervisor_id": "",
        })
        executives.append({
            "executive_id": executive_id,
            "emp_id": employee_id,
            "oversight_region": region,
        })
        employee_id += 1

    for executive in executives:
        region = executive["oversight_region"]
        for _ in range(SUPERVISORS_PER_EXECUTIVE):
            supervisor_employee_id = employee_id
            employees.append({
                "employee_id": supervisor_employee_id,
                "full_name": next_full_name(),
                "email": f"employee{supervisor_employee_id}@trustscore.test",
                "department": rng.choice(DEPARTMENTS),
                "role": "Immediate Supervisor",
                "user_type": "supervisor",
                "supervisor_id": "",
            })
            supervisors.append({
                "supervisor_id": supervisor_id,
                "branch_code": rng.choice(BRANCHES[region]),
                "executive_id": executive["executive_id"],
                "emp_id": supervisor_employee_id,
            })
            employee_id += 1
            supervisor_id += 1

    for supervisor in supervisors:
        for _ in range(EMPLOYEES_PER_SUPERVISOR):
            employees.append({
                "employee_id": employee_id,
                "full_name": next_full_name(),
                "email": f"employee{employee_id}@trustscore.test",
                "department": rng.choice(DEPARTMENTS),
                "role": rng.choice(JOB_ROLES),
                "user_type": "employee",
                "supervisor_id": supervisor["supervisor_id"],
            })
            employee_id += 1

    write_csv("employees.csv", employees)
    write_csv("executive_managers.csv", executives)
    write_csv("immediate_supervisors.csv", supervisors)

    print(
        f"Generated base seed: {len(employees)} synthetic employee accounts, "
        f"{len(supervisors)} supervisor profiles and {len(executives)} executive profiles."
    )
    print("No KPI, feedback, appraisal report, score, or source-mapping rows were generated.")
    print(f"CSV files: {OUTPUT_DIR}")
    return OUTPUT_DIR


if __name__ == "__main__":
    generate()
