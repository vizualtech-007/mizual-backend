"""
Optimized CRUD operations for better performance.
Includes batch operations and async-compatible functions.
"""

from sqlalchemy.orm import Session
from sqlalchemy import text
from . import models
from typing import Optional


def update_edit_enhanced_prompt(db: Session, edit_id: int, enhanced_prompt: str):
    """Optimized update for enhanced prompt"""
    try:
        # Use direct SQL for faster update
        db.execute(
            text("UPDATE edits SET enhanced_prompt = :enhanced_prompt WHERE id = :edit_id"),
            {"enhanced_prompt": enhanced_prompt, "edit_id": edit_id}
        )
        db.commit()
    except Exception as e:
        db.rollback()
        raise e


def batch_update_edit_status_and_stage(db: Session, edit_id: int, status: str, stage: str):
    """Batch update status and stage in single query"""
    try:
        db.execute(
            text("UPDATE edits SET status = :status, processing_stage = :stage WHERE id = :edit_id"),
            {"status": status, "stage": stage, "edit_id": edit_id}
        )
        db.commit()
    except Exception as e:
        db.rollback()
        raise e


def optimized_get_edit(db: Session, edit_id: int) -> Optional[models.Edit]:
    """Optimized edit retrieval with minimal data"""
    try:
        # Only select needed columns for better performance
        result = db.execute(
            text("""
                SELECT id, uuid, prompt, enhanced_prompt, original_image_url, 
                       edited_image_url, status, processing_stage, created_at
                FROM edits 
                WHERE id = :edit_id
            """),
            {"edit_id": edit_id}
        ).fetchone()
        
        if result:
            edit = models.Edit()
            edit.id = result[0]
            edit.uuid = result[1]
            edit.prompt = result[2]
            edit.enhanced_prompt = result[3]
            edit.original_image_url = result[4]
            edit.edited_image_url = result[5]
            edit.status = result[6]
            edit.processing_stage = result[7]
            edit.created_at = result[8]
            return edit
        return None
    except Exception as e:
        print(f"Error in optimized_get_edit: {e}")
        # Fallback to regular method
        return db.query(models.Edit).filter(models.Edit.id == edit_id).first()