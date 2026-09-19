from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext

# ---------------------------------------------------------
# Config
# ---------------------------------------------------------
# NOTE: In a real production system, SECRET_KEY must come from an
# environment variable, never hardcoded in source. For this student
# project, a hardcoded value is fine for now.
SECRET_KEY = "trustscoreai-dev-secret-change-this-later"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Turn a plain-text password into a secure hash for storage."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check a plain-text password against a stored hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict) -> str:
    """Build a signed JWT containing the given claims (e.g. user_id, role)."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str):
    """Verify and decode a JWT. Returns the payload dict, or None if invalid/expired."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


get_password_hash = hash_password