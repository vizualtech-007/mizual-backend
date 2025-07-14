from sqlalchemy.orm import Session
import models, schemas

def get_edit(db: Session, edit_id: int):
    return db.query(models.Edit).filter(models.Edit.id == edit_id).first()

def get_edit_by_uuid(db: Session, edit_uuid: str):
    return db.query(models.Edit).filter(models.Edit.uuid == edit_uuid).first()

def create_edit(db: Session, prompt: str, original_image_url: str):
    db_edit = models.Edit(
        prompt=prompt,
        original_image_url=original_image_url,
        status="pending"
    )
    db.add(db_edit)
    db.commit()
    db.refresh(db_edit)
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
