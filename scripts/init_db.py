import sys
import os

# Add the project root to the python path so it can find the 'app' module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.base import Base
from app.db.session import engine
from app.db.models import InvestigationReport

def init_db():
    print("Connecting to database and creating tables...")
    # This is the correct way to call create_all
    Base.metadata.create_all(bind=engine)
    print("✅ Database initialized successfully.")

if __name__ == "__main__":
    init_db()