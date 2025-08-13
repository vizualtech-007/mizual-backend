from sqlalchemy.orm import Session
from sqlalchemy import text
from . import models, schemas
import os

def set_schema_for_session(db: Session):
    """Set the correct schema for the current session based on environment"""
    environment = os.environ.get("ENVIRONMENT", "production")
    schema_name = "preview" if environment == "preview" else "public"
    db.execute(text(f"SET search_path TO {schema_name}, public"))

def get_edit(db: Session, edit_id: int):
    set_schema_for_session(db)
    return db.query(models.Edit).filter(models.Edit.id == edit_id).first()

def get_edit_by_uuid(db: Session, edit_uuid: str):
    set_schema_for_session(db)
    return db.query(models.Edit).filter(models.Edit.uuid == edit_uuid).first()

def create_edit(db: Session, prompt: str, original_image_url: str, enhanced_prompt: str = None):
    set_schema_for_session(db)
    db_edit = models.Edit(
        prompt=prompt,
        enhanced_prompt=enhanced_prompt,
        original_image_url=original_image_url,
        status="pending"
    )
    db.add(db_edit)
    db.commit()
    db.refresh(db_edit)
    return db_edit

def update_edit_status(db: Session, edit_id: int, status: str):
    set_schema_for_session(db)
    db_edit = get_edit(db, edit_id)
    if db_edit:
        db_edit.status = status
        db.commit()
        db.refresh(db_edit)
    return db_edit

def update_edit_with_result(db: Session, edit_id: int, status: str, edited_image_url: str):
    set_schema_for_session(db)
    db_edit = get_edit(db, edit_id)
    if db_edit:
        db_edit.status = status
        db_edit.edited_image_url = edited_image_url
        db.commit()
        db.refresh(db_edit)
    return db_edit

def update_edit_processing_stage(db: Session, edit_id: int, processing_stage: str):
    """Update the processing stage for better progress tracking"""
    set_schema_for_session(db)
    db_edit = get_edit(db, edit_id)
    if db_edit:
        db_edit.processing_stage = processing_stage
        db.commit()
        db.refresh(db_edit)
    return db_edit

# Feedback CRUD Operations
def create_feedback(db: Session, feedback: schemas.FeedbackCreate, user_ip: str = None):
    """Create feedback for an edit"""
    set_schema_for_session(db)
    
    # Check if edit exists
    edit = get_edit_by_uuid(db, feedback.edit_uuid)
    if not edit:
        return None
    
    # Check if feedback already exists for this edit
    existing_feedback = get_feedback_by_edit_uuid(db, feedback.edit_uuid)
    if existing_feedback:
        return None  # Feedback already exists
    
    db_feedback = models.EditFeedback(
        edit_uuid=feedback.edit_uuid,
        rating=feedback.rating,
        feedback_text=feedback.feedback_text,
        user_ip=user_ip
    )
    db.add(db_feedback)
    db.commit()
    db.refresh(db_feedback)
    return db_feedback

def get_feedback_by_edit_uuid(db: Session, edit_uuid: str):
    """Get feedback for a specific edit"""
    set_schema_for_session(db)
    return db.query(models.EditFeedback).filter(models.EditFeedback.edit_uuid == edit_uuid).first()

def get_feedback_by_id(db: Session, feedback_id: int):
    """Get feedback by ID"""
    set_schema_for_session(db)
    return db.query(models.EditFeedback).filter(models.EditFeedback.id == feedback_id).first()

def feedback_exists_for_edit(db: Session, edit_uuid: str) -> bool:
    """Check if feedback already exists for an edit"""
    set_schema_for_session(db)
    feedback = db.query(models.EditFeedback).filter(models.EditFeedback.edit_uuid == edit_uuid).first()
    return feedback is not None
