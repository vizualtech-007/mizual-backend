from pydantic import BaseModel, Field
import datetime
from typing import Optional
import uuid

class EditBase(BaseModel):
    prompt: str

class EditCreate(EditBase):
    pass

class Edit(EditBase):
    uuid: uuid.UUID
    original_image_url: str
    edited_image_url: Optional[str] = None
    status: str
    created_at: datetime.datetime

    class Config:
        from_attributes = True

class EditCreateResponse(BaseModel):
    edit_id: uuid.UUID
    polling_url: str
