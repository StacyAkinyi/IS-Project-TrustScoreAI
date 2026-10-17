"""Load only synthetic employee identities and reporting structure into PostgreSQL."""

import argparse
import csv
import os
from pathlib import Path

from passlib.context import CryptContext
from sqlalchemy import text

import models
from database import Base, SessionLocal, engine


DATA_DIR = Path(__file__).resolve().parent / "data" / "base_seed"
PASSWORD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")
DEMO_PASSWORD = os.getenv("SEED_DEMO_PASSWORD", "TrustScoreDemo2026!")
BASE_MODELS = [models.Employee, models.ExecutiveManager, models.ImmediateSupervisor]
POSTGRES_SEQUENCES = {
    "employees": "employee_id",
    "executive_managers": "executive_id",
    "immediate_supervisors": "sup_id",
}


def read_csv(filename: str) -> list[dict[str, str]]:
    path = DATA_DIR / filename
    if not path.is_file():
        raise FileNotFoundError(f"Missing {path}. Run generate_data.py first.")
    with path.open("r", newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def as_int(value: str | None, *, optional: bool = False) -> int | None:
    if value is None or value.strip() == "":
        if optional:
            return None
        raise ValueError("Expected an integer value, found an empty field.")
    return int(value)


def load_base_data(reset: bool = False) -> None:
    employees = read_csv("employees.csv")
    executives = read_csv("executive_managers.csv")
    supervisors = read_csv("immediate_supervisors.csv")

    if reset:
        print("Resetting all TrustScoreAI tables as requested...")
        trustscoreai_tables = (
            "appraisal_source_mappings",
            "password_reset_tokens",
            "appraisal_reports",
            "performance_records",
            "unstructured_feedback",
            "immediate_supervisors",
            "executive_managers",
            "employees",
        )
        with engine.begin() as connection:
            for table_name in trustscoreai_tables:
                connection.execute(text(f'DROP TABLE IF EXISTS "{table_name}" CASCADE'))
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as session:
        if not reset and any(session.query(model).first() for model in BASE_MODELS):
            raise RuntimeError(
                "Base account tables already contain rows. Back up the database and use "
                "--reset only if you intend to replace all TrustScoreAI data."
            )
        session.rollback()

        with session.begin():
            employees_by_id = {}
            employee_supervisors = {}
            for row in employees:
                employee = models.Employee(
                    employee_id=as_int(row["employee_id"]),
                    full_name=row["full_name"],
                    email=row["email"].strip().lower(),
                    password_hashed=PASSWORD_CONTEXT.hash(DEMO_PASSWORD),
                    department=row["department"],
                    role=row["role"],
                    user_type=row["user_type"],
                    supervisor_id=None,
                )
                employees_by_id[employee.employee_id] = employee
                employee_supervisors[employee.employee_id] = as_int(
                    row["supervisor_id"], optional=True
                )
                session.add(employee)
            session.flush()

            session.add_all([
                models.ExecutiveManager(
                    executive_id=as_int(row["executive_id"]),
                    emp_id=as_int(row["emp_id"]),
                    oversight_region=row["oversight_region"],
                )
                for row in executives
            ])
            session.flush()

            session.add_all([
                models.ImmediateSupervisor(
                    supervisor_id=as_int(row["supervisor_id"]),
                    branch_code=row["branch_code"],
                    executive_id=as_int(row["executive_id"]),
                    emp_id=as_int(row["emp_id"]),
                )
                for row in supervisors
            ])
            session.flush()

            # Set employee-to-supervisor links after both sides of the circular
            # relationship exist. Executive and supervisor accounts have no
            # immediate supervisor in this seed hierarchy.
            for employee_id, supervisor_id in employee_supervisors.items():
                employees_by_id[employee_id].supervisor_id = supervisor_id
            session.flush()

    # Explicit IDs are used for stable seed files; advance only the three
    # account/profile sequences so later application inserts won't collide.
    with engine.begin() as connection:
        for table_name, id_column in POSTGRES_SEQUENCES.items():
            connection.execute(text(
                f"SELECT setval(pg_get_serial_sequence('{table_name}', '{id_column}'), "
                f"COALESCE(MAX({id_column}), 1), COUNT(*) > 0) FROM {table_name}"
            ))

    print(
        f"Loaded {len(employees)} synthetic base accounts: "
        f"{len(supervisors)} supervisors and {len(executives)} executives."
    )
    print("Performance, feedback, report, and source-mapping tables were left untouched.")
    print(f"Shared local-demo password: {DEMO_PASSWORD}")



def refresh_demo_names() -> None:
    """Refresh names for synthetic demo accounts without resetting any tables."""
    employees = read_csv("employees.csv")
    names = [row["full_name"].strip() for row in employees]
    if len(names) != len(set(names)):
        raise RuntimeError("The generated employee seed contains duplicate full names.")
    if any(not row["email"].lower().endswith("@trustscore.test") for row in employees):
        raise RuntimeError("Name refresh is limited to @trustscore.test demo accounts.")

    with SessionLocal() as session:
        existing = {
            employee.email: employee
            for employee in session.query(models.Employee).filter(
                models.Employee.email.like("%@trustscore.test")
            ).all()
        }
        requested_emails = {row["email"].strip().lower() for row in employees}
        if set(existing) != requested_emails:
            raise RuntimeError(
                "The database demo account set does not match data/base_seed. "
                "No names were changed."
            )
        for row in employees:
            existing[row["email"].strip().lower()].full_name = row["full_name"].strip()
        session.commit()
    print(f"Updated names for {len(employees)} synthetic demo accounts; IDs and related records were preserved.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop and recreate all TrustScoreAI tables before loading base accounts.",
    )
    parser.add_argument(
        "--refresh-demo-names",
        action="store_true",
        help="Update only existing @trustscore.test names; preserve all rows and relationships.",
    )
    args = parser.parse_args()
    if args.refresh_demo_names:
        if args.reset:
            parser.error("--reset and --refresh-demo-names cannot be used together")
        refresh_demo_names()
    else:
        load_base_data(reset=args.reset)


if __name__ == "__main__":
    main()
