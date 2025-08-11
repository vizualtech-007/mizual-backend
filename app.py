from fastapi import FastAPI, File, UploadFile, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from src import models, schemas, database, crud, s3, tasks
from src.database import engine
import uuid
import base64

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for now (can be restricted later)
    allow_credentials=False,  # Set to False when using allow_origins=["*"]
    allow_methods=["*"],
    allow_headers=["*"],
)

class EditImageRequest(BaseModel):
    prompt: str
    image: str

@app.on_event("startup")
def startup_event():
    s3.create_bucket_if_not_exists()
    # Skip database migrations for now - tables are already properly set up
    print("Startup complete - database migrations skipped")

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

