import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:password@localhost:5432/contrarian_db"
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,   # liveness check before each connection use
    pool_recycle=300,     # recycle connections every 5 min (fixes Winsock 10053)
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()