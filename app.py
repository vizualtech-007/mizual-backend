from fastapi import FastAPI, File, UploadFile, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from src import models, schemas, database, crud, s3, tasks
from src.database import engine
import uuid
import base64
import os

# Import LLM provider factory
try:
    from src.llm import get_provider
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
import os

models.Base.metadata.create_all(bind=engine)

# Rate limiting configuration from environment variables
RATE_LIMIT_DAILY_IMAGES = os.environ.get("RATE_LIMIT_DAILY_IMAGES", "3")
RATE_LIMIT_BURST_SECONDS = os.environ.get("RATE_LIMIT_BURST_SECONDS", "10")
RATE_LIMIT_STATUS_CHECKS_PER_MINUTE = os.environ.get("RATE_LIMIT_STATUS_CHECKS_PER_MINUTE", "30")

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)
app = FastAPI()

# Add rate limiter to app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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
@limiter.limit(f"{RATE_LIMIT_DAILY_IMAGES}/day")  # Configurable daily limit per IP
@limiter.limit(f"1/{RATE_LIMIT_BURST_SECONDS}seconds")  # Configurable burst protection per IP
async def edit_image_endpoint(request: Request, edit_request: EditImageRequest, db: Session = Depends(database.get_db)):
    try:
        # Decode the base64 image
        header, encoded_image = edit_request.image.split(",", 1)
        image_bytes = base64.b64decode(encoded_image)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image format: {e}")

    print(f"Starting image edit process with prompt: '{edit_request.prompt}'")
    
    original_file_name = f"original-{uuid.uuid4()}.png"

    try:
        original_image_url = s3.upload_file_to_s3(image_bytes, original_file_name)
        print(f"Uploaded original image to: {original_image_url}")
    except Exception as e:
        print(f"Failed to upload original image to S3: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to upload original image to S3: {e}")

    # Try to enhance the prompt with LLM if available
    enhanced_prompt = None
    original_prompt = edit_request.prompt
    
    if LLM_AVAILABLE and os.environ.get("ENABLE_PROMPT_ENHANCEMENT", "true").lower() in ["true", "1", "yes"]:
        try:
            print("Attempting prompt enhancement with LLM")
            llm_provider = get_provider()
            if llm_provider:
                enhanced_prompt = llm_provider.enhance_prompt(original_prompt, image_bytes)
        except Exception as e:
            print(f"Error enhancing prompt: {str(e)}")
            enhanced_prompt = None
    
    # Use enhanced prompt if available, otherwise use original
    final_prompt = enhanced_prompt if enhanced_prompt else original_prompt
    if enhanced_prompt:
        print(f"Using enhanced prompt for BFL")
    else:
        print(f"Using original prompt for BFL")

    # Create database record with both original and enhanced prompts
    edit = crud.create_edit(
        db=db,
        prompt=original_prompt,
        enhanced_prompt=enhanced_prompt,
        original_image_url=original_image_url
    )

    # Process the image edit asynchronously with the final prompt
    tasks.process_image_edit.delay(edit.id)
    
    print(f"Edit request queued for processing with UUID: {edit.uuid}")

    polling_url = str(request.url_for('get_edit_status', edit_uuid=edit.uuid))

    return {"edit_id": edit.uuid, "polling_url": polling_url}

@app.get("/edit/{edit_uuid}", response_model=schemas.Edit)
@limiter.limit(f"{RATE_LIMIT_STATUS_CHECKS_PER_MINUTE}/minute")  # Configurable status check limit
def get_edit_status(request: Request, edit_uuid: str, db: Session = Depends(database.get_db)):
    db_edit = crud.get_edit_by_uuid(db, edit_uuid=edit_uuid)
    if db_edit is None:
        raise HTTPException(status_code=404, detail="Edit not found")
    return db_edit

