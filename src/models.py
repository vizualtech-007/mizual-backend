from sqlalchemy import Column, Integer, String, DateTime, Text
from .database import Base
import datetime
import uuid

class Edit(Base):
    __tablename__ = "edits"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String, unique=True, index=True, default=lambda: str(uuid.uuid4()))
    prompt = Column(String, index=True)
    enhanced_prompt = Column(String, nullable=True)  # Store LLM-enhanced prompt
    original_image_url = Column(String)
    edited_image_url = Column(String, nullable=True)
    status = Column(String, default="pending")
    processing_stage = Column(String, default="pending")  # New field from migration
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class EditFeedback(Base):
    __tablename__ = "edit_feedback"

    id = Column(Integer, primary_key=True, index=True)
    edit_uuid = Column(String, nullable=False, unique=True)  # One feedback per edit
    rating = Column(Integer, nullable=False)  # 1-5 stars
    feedback_text = Column(Text, nullable=True)  # Optional text feedback
    user_ip = Column(String, nullable=True)  # For analytics
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
