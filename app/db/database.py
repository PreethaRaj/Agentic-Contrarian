from app.db.session import engine
from app.db.base import Base  # Ensure your models (like Investigation) are imported here

def init_db():
    """
    Initializes the database by creating all tables defined in the Base metadata.
    """
    try:
        # We call create_all on the metadata object, passing the engine
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables initialized successfully.")
    except Exception as e:
        print(f"❌ Failed to initialize database: {e}")
        raise e