from sqlalchemy.orm import Session, selectinload, joinedload
from sqlalchemy import text
from . import models, schemas
import os

# Schema is now set via connect_args in database.py
# No need for explicit schema setting per session

def get_edit(db: Session, edit_id: int):
    return db.query(models.Edit).filter(models.Edit.id == edit_id).first()

def get_edit_by_uuid(db: Session, edit_uuid: str):
    return db.query(models.Edit).filter(models.Edit.uuid == edit_uuid).first()

def create_edit(db: Session, prompt: str, original_image_url: str, enhanced_prompt: str = None, parent_edit_uuid: str = None):
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
    db_edit = get_edit(db, edit_id)
    if db_edit:
        db_edit.status = status
        db.commit()
        db.refresh(db_edit)
    return db_edit

def update_edit_with_result(db: Session, edit_id: int, status: str, edited_image_url: str):
    db_edit = get_edit(db, edit_id)
    if db_edit:
        db_edit.status = status
        db_edit.edited_image_url = edited_image_url
        db.commit()
        db.refresh(db_edit)
    return db_edit

def update_edit_processing_stage(db: Session, edit_id: int, processing_stage: str):
    """Update the processing stage for better progress tracking"""
    db_edit = get_edit(db, edit_id)
    if db_edit:
        db_edit.processing_stage = processing_stage
        db.commit()
        db.refresh(db_edit)
    return db_edit

def update_edit_enhanced_prompt(db: Session, edit_id: int, enhanced_prompt: str):
    """Update the enhanced prompt for an edit"""
    db_edit = get_edit(db, edit_id)
    if db_edit:
        db_edit.enhanced_prompt = enhanced_prompt
        db.commit()
        db.refresh(db_edit)
    return db_edit

# Feedback CRUD Operations
def create_feedback(db: Session, feedback: schemas.FeedbackCreate, user_ip: str = None):
    """Create feedback for an edit"""
    
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
    return db.query(models.EditFeedback).filter(models.EditFeedback.edit_uuid == edit_uuid).first()

def get_feedback_by_id(db: Session, feedback_id: int):
    """Get feedback by ID"""
    return db.query(models.EditFeedback).filter(models.EditFeedback.id == feedback_id).first()

def feedback_exists_for_edit(db: Session, edit_uuid: str) -> bool:
    """Check if feedback already exists for an edit"""
    feedback = db.query(models.EditFeedback).filter(models.EditFeedback.edit_uuid == edit_uuid).first()
    return feedback is not None

# Edit Chain CRUD Operations
def create_edit_chain(db: Session, edit_uuid: str, parent_edit_uuid: str = None):
    """Create an edit chain relationship"""
    
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
    return db.query(models.EditChain).filter(models.EditChain.edit_uuid == edit_uuid).first()

def validate_chain_length(db: Session, parent_edit_uuid: str) -> int:
    """Validate chain length and return current chain length"""
    
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
    """Get the complete chain history for an edit using recursive CTE"""
    
    # Use recursive CTE to find the complete chain efficiently
    cte_query = text("""
        WITH RECURSIVE edit_chain_recursive AS (
            -- Base case: start with the given edit
            SELECT 
                ec.edit_uuid,
                ec.parent_edit_uuid,
                ec.chain_position,
                1 as depth
            FROM edit_chains ec
            WHERE ec.edit_uuid = :edit_uuid
            
            UNION ALL
            
            -- Recursive case: find parent edits
            SELECT 
                ec.edit_uuid,
                ec.parent_edit_uuid,
                ec.chain_position,
                ecr.depth + 1
            FROM edit_chains ec
            INNER JOIN edit_chain_recursive ecr ON ec.edit_uuid = ecr.parent_edit_uuid
            WHERE ecr.depth < 10  -- Prevent infinite recursion
        )
        SELECT DISTINCT edit_uuid, parent_edit_uuid, chain_position
        FROM edit_chain_recursive
        ORDER BY chain_position
    """)
    
    # Execute the CTE query
    chain_result = db.execute(cte_query, {"edit_uuid": edit_uuid}).fetchall()
    
    # If no chain found, check if the edit exists as a standalone edit
    if not chain_result:
        standalone_edit = get_edit_by_uuid(db, edit_uuid)
        if standalone_edit:
            return [{
                'edit': standalone_edit,
                'chain_position': 1,
                'parent_edit_uuid': None
            }]
        return []
    
    # Extract all edit UUIDs from the chain
    chain_uuids = [row.edit_uuid for row in chain_result]
    
    # Single query to get all edits with eager loading
    edits = db.query(models.Edit).filter(
        models.Edit.uuid.in_(chain_uuids)
    ).all()
    
    # Create lookup maps
    edit_map = {edit.uuid: edit for edit in edits}
    chain_info_map = {
        row.edit_uuid: {
            'chain_position': row.chain_position,
            'parent_edit_uuid': row.parent_edit_uuid
        } 
        for row in chain_result
    }
    
    # Build the result ordered by chain position
    chain = []
    for row in sorted(chain_result, key=lambda x: x.chain_position):
        if row.edit_uuid in edit_map:
            chain_info = chain_info_map[row.edit_uuid]
            chain.append({
                'edit': edit_map[row.edit_uuid],
                'chain_position': chain_info['chain_position'],
                'parent_edit_uuid': chain_info['parent_edit_uuid']
            })
    
    return chain

