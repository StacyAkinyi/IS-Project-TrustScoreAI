from database import engine, Base
# Explicitly import all model classes so SQLAlchemy registers them to Base.metadata
from models import (
    ExecutiveManager,
    ImmediateSupervisor,
    Employee,
    PerformanceRecord,
    UnstructuredFeedback,
    AppraisalReport,
    AppraisalSourceMapping
)

def setup_database():
    print("Connecting to PostgreSQL database...")
    
    # Create all registered tables in PostgreSQL
    Base.metadata.create_all(bind=engine)
    
    print("Success! All TrustScoreAI tables have been created.")

if __name__ == "__main__":
    setup_database()