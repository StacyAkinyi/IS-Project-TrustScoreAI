from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Database connection URL using your local PostgreSQL credentials
SQLALCHEMY_DATABASE_URL = "postgresql://postgres:Bambino.0@127.0.0.1:5433/trust_score_ai_db"

# Create the SQLAlchemy engine
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# Create a session maker for database interactions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for your ORM models to inherit from
Base = declarative_base()

# Dependency function for FastAPI routes to manage session lifecycle
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()