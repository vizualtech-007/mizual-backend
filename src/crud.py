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

def create_edit(db: Session, prompt: str, original_image_url: str, enhanced_prompt: str = None, parent_edit_uuid: str = None):
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
    
    # Create chain relationship if this is a follow-up edit
    if parent_edit_uuid:
        create_edit_chain(db, db_edit.uuid, parent_edit_uuid)
    
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

# Edit Chain CRUD Operations
def create_edit_chain(db: Session, edit_uuid: str, parent_edit_uuid: str = None):
    """Create an edit chain relationship"""
    set_schema_for_session(db)
    
    # Calculate chain position
    chain_position = 1  # Default for first edit
    if parent_edit_uuid:
        parent_chain = get_edit_chain_by_edit_uuid(db, parent_edit_uuid)
        if parent_chain:
            chain_position = parent_chain.chain_position + 1
        else:
            chain_position = 2  # Parent is first edit, this is second
    
    db_chain = models.EditChain(
        edit_uuid=edit_uuid,
        parent_edit_uuid=parent_edit_uuid,
        chain_position=chain_position
    )
    db.add(db_chain)
    db.commit()
    db.refresh(db_chain)
    return db_chain

def get_edit_chain_by_edit_uuid(db: Session, edit_uuid: str):
    """Get edit chain record for a specific edit"""
    set_schema_for_session(db)
    return db.query(models.EditChain).filter(models.EditChain.edit_uuid == edit_uuid).first()

def validate_chain_length(db: Session, parent_edit_uuid: str) -> int:
    """Validate chain length and return current chain length"""
    set_schema_for_session(db)
    
    # Get the parent's chain position
    parent_chain = get_edit_chain_by_edit_uuid(db, parent_edit_uuid)
    if parent_chain:
        current_length = parent_chain.chain_position
    else:
        current_length = 1  # Parent is the first edit
    
    # Check if adding one more would exceed limit
    if current_length >= 5:
        return -1  # Chain too long
    
    return current_length

def get_edit_chain_history(db: Session, edit_uuid: str):
    """Get the complete chain history for an edit"""
    set_schema_for_session(db)
    
    # Start with the current edit
    current_edit = get_edit_by_uuid(db, edit_uuid)
    if not current_edit:
        return []
    
    # Get the chain record for this edit
    chain_record = get_edit_chain_by_edit_uuid(db, edit_uuid)
    
    # Build the chain by following parent relationships
    chain = []
    current_uuid = edit_uuid
    
    while current_uuid:
        edit = get_edit_by_uuid(db, current_uuid)
        if edit:
            chain_info = get_edit_chain_by_edit_uuid(db, current_uuid)
            chain.append({
                'edit': edit,
                'chain_position': chain_info.chain_position if chain_info else 1,
                'parent_edit_uuid': chain_info.parent_edit_uuid if chain_info else None
            })
            
            # Move to parent
            current_uuid = chain_info.parent_edit_uuid if chain_info else None
        else:
            break
    
    # Reverse to get chronological order (first edit first)
    return list(reversed(chain))

def get_chain_stats(db: Session):
    """Get analytics about edit chains"""
    set_schema_for_session(db)
    
    # Count total chains
    total_chains = db.query(models.EditChain).count()
    
    # Get average chain length
    if total_chains > 0:
        max_positions = db.query(models.EditChain.chain_position).all()
        avg_length = sum(pos[0] for pos in max_positions) / len(max_positions)
    else:
        avg_length = 0
    
    return {
        'total_chains': total_chains,
        'average_chain_length': round(avg_length, 2)
    }
