from sqlalchemy import Column, Integer, String, DateTime, text
from database import Base
import datetime
import uuid

class Edit(Base):
    __tablename__ = "edits"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String, unique=True, index=True, default=lambda: str(uuid.uuid4()))
    prompt = Column(String, index=True)
    original_image_url = Column(String)
    edited_image_url = Column(String, nullable=True)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
