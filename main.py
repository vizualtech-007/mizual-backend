from fastapi import FastAPI, File, UploadFile, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
import models, schemas, database, crud, s3, tasks
from database import engine
import uuid
import base64

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class EditImageRequest(BaseModel):
    prompt: str
    image: str

@app.on_event("startup")
def startup_event():
    s3.create_bucket_if_not_exists()
    with engine.connect() as connection:
        # Ensure required columns exist and backfill UUIDs for existing records.
        connection.execute(text("ALTER TABLE edits ADD COLUMN IF NOT EXISTS original_image_url VARCHAR"))
        connection.execute(text("ALTER TABLE edits ADD COLUMN IF NOT EXISTS edited_image_url VARCHAR"))
        connection.execute(text("ALTER TABLE edits ADD COLUMN IF NOT EXISTS uuid VARCHAR"))
        connection.commit()

        edits_without_uuid = connection.execute(text("SELECT id FROM edits WHERE uuid IS NULL"))
        for row in edits_without_uuid:
            edit_id = row[0]
            new_uuid = str(uuid.uuid4())
            connection.execute(text(f"UPDATE edits SET uuid = '{new_uuid}' WHERE id = {edit_id}"))
        connection.commit()

@app.post("/edit-image/", response_model=schemas.EditCreateResponse)
async def edit_image_endpoint(request: Request, edit_request: EditImageRequest, db: Session = Depends(database.get_db)):
    try:
        # Decode the base64 image
        header, encoded_image = edit_request.image.split(",", 1)
        image_bytes = base64.b64decode(encoded_image)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image format: {e}")

    original_file_name = f"original-{uuid.uuid4()}.png"

    try:
        original_image_url = s3.upload_file_to_s3(image_bytes, original_file_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload original image to S3: {e}")

    edit = crud.create_edit(
        db=db,
        prompt=edit_request.prompt,
        original_image_url=original_image_url
    )

    tasks.process_image_edit.delay(edit.id)

    polling_url = str(request.url_for('get_edit_status', edit_uuid=edit.uuid))

    return {"edit_id": edit.uuid, "polling_url": polling_url}

@app.get("/edit/{edit_uuid}", response_model=schemas.Edit)
def get_edit_status(edit_uuid: str, db: Session = Depends(database.get_db)):
    db_edit = crud.get_edit_by_uuid(db, edit_uuid=edit_uuid)
    if db_edit is None:
        raise HTTPException(status_code=404, detail="Edit not found")
    return db_edit
