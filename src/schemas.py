from pydantic import BaseModel, Field, validator
import datetime
from typing import Optional
import uuid

class EditBase(BaseModel):
    prompt: str

class EditCreate(EditBase):
    pass

class Edit(EditBase):
    uuid: uuid.UUID
    enhanced_prompt: Optional[str] = None  # LLM-enhanced prompt
    original_image_url: str
    edited_image_url: Optional[str] = None
    status: str
    processing_stage: Optional[str] = "pending"  # New field
    created_at: datetime.datetime

    class Config:
        from_attributes = True

class EditStatusResponse(BaseModel):
    """Enhanced status response with progress information"""
    uuid: uuid.UUID
    status: str
    processing_stage: Optional[str] = None
    message: str
    progress_percent: int
    is_complete: bool
    is_error: bool
    edited_image_url: Optional[str] = None
    created_at: datetime.datetime

class EditCreateResponse(BaseModel):
    edit_id: uuid.UUID
    polling_url: str

# Feedback Schemas
class FeedbackBase(BaseModel):
    edit_uuid: str
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 to 5 stars")
    feedback_text: Optional[str] = Field(None, max_length=1000, description="Optional feedback text")

class FeedbackCreate(FeedbackBase):
    @validator('rating')
    def validate_rating(cls, v):
        if v < 1 or v > 5:
            raise ValueError('Rating must be between 1 and 5')
        return v

class Feedback(FeedbackBase):
    id: int
    user_ip: Optional[str] = None
    created_at: datetime.datetime

    class Config:
        from_attributes = True

class FeedbackResponse(BaseModel):
    success: bool
    message: str
    feedback_id: Optional[int] = None
