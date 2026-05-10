from sqlalchemy import Column, String, JSON, DateTime
from sqlalchemy.dialects.postgresql import UUID
import uuid
import datetime
from app.db.base import Base

class InvestigationReport(Base):
    __tablename__ = "investigations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query = Column(String, nullable=False)
    state_snapshot = Column(JSON) 
    created_at = Column(DateTime, default=datetime.datetime.utcnow)