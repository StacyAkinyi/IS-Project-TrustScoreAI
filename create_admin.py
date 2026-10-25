"""Create the first administrator account interactively.

Run the PostgreSQL migration in migrations/add_admin_user_type.sql first.
Passwords are prompted securely and only the password hash is stored.
"""

from getpass import getpass

from sqlalchemy import func

import auth
import models
from database import SessionLocal


def password_policy_error(password: str) -> str | None:
    if len(password) < 12:
        return "Password must be at least 12 characters long."
    if len(password.encode("utf-8")) > 72:
        return "Password must be no more than 72 bytes."
    if not any(character.islower() for character in password):
        return "Password must include a lowercase letter."
    if not any(character.isupper() for character in password):
        return "Password must include an uppercase letter."
    if not any(character.isdigit() for character in password):
        return "Password must include a number."
    if not any(not character.isalnum() for character in password):
        return "Password must include a symbol."
    return None


def main() -> None:
    full_name = input("Administrator full name: ").strip()
    email = input("Administrator email: ").strip().lower()
    if len(full_name) < 2 or "@" not in email:
        raise SystemExit("Enter a valid name and email address.")

    password = getpass("Create administrator password (12-72 characters): ")
    confirmation = getpass("Confirm password: ")
    policy_error = password_policy_error(password)
    if policy_error:
        raise SystemExit(policy_error)
    if password != confirmation:
        raise SystemExit("Passwords did not match.")

    db = SessionLocal()
    try:
        existing = db.query(models.Employee).filter(
            func.lower(models.Employee.email) == email
        ).first()
        if existing:
            raise SystemExit("An account already uses that email; no account was changed.")

        administrator = models.Employee(
            full_name=full_name,
            email=email,
            password_hashed=auth.hash_password(password),
            department="Administration",
            role="System Administrator",
            user_type="admin",
            supervisor_id=None,
        )
        db.add(administrator)
        db.commit()
        print(f"Administrator account created for {email} (employee ID {administrator.employee_id}).")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
