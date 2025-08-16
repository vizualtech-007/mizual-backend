from fastapi import FastAPI, File, UploadFile, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from src import models, schemas, database, crud, s3, tasks
from src.database import engine
from src.performance_tracker import start_performance_tracking
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
    parent_edit_uuid: Optional[str] = None  # For follow-up editing

@app.on_event("startup")
def startup_event():
    s3.create_bucket_if_not_exists()
    # Skip database migrations for now - tables are already properly set up
    print("Startup complete - database migrations skipped")

@app.get("/health")
@app.head("/health")
def health_check():
    """Health check endpoint for monitoring and load balancers"""
    return {"status": "ok", "message": "Service is running"}

@app.get("/health/celery")
@limiter.limit("10/minute")
async def celery_health_check(request: Request):
    """Health check endpoint for Celery worker connectivity"""
    try:
        from src.tasks import celery
        
        # Check if workers are available
        inspect = celery.control.inspect()
        active_workers = inspect.active()
        
        if active_workers:
            worker_count = len(active_workers)
            worker_names = list(active_workers.keys())
            
            # Get worker stats
            stats = inspect.stats()
            
            return {
                "status": "healthy",
                "message": "Celery workers are connected and active",
                "worker_count": worker_count,
                "workers": worker_names,
                "redis_connection": "ok",
                "stats": stats
            }
        else:
            return {
                "status": "unhealthy",
                "message": "No active Celery workers found",
                "worker_count": 0,
                "workers": [],
                "redis_connection": "unknown"
            }
            
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to check Celery health: {str(e)}",
            "error_type": type(e).__name__,
            "worker_count": 0,
            "workers": [],
            "redis_connection": "failed"
        }

@app.get("/debug/db-schema")
@limiter.limit("5/minute")
async def debug_database_schema(request: Request):
    """Debug endpoint to check database schema and table structure"""
    try:
        db = next(database.get_db())
        
        # Check current schema path
        schema_result = db.execute(text("SHOW search_path")).fetchone()
        current_schema = schema_result[0] if schema_result else "unknown"
        
        # Check if edits table exists and get its columns
        table_check = db.execute(text("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'edits' 
            AND table_schema = ANY(current_schemas(false))
            ORDER BY ordinal_position
        """)).fetchall()
        
        # Check environment variable
        environment = os.environ.get("ENVIRONMENT", "unknown")
        
        return {
            "environment": environment,
            "current_schema_path": current_schema,
            "edits_table_columns": [
                {
                    "column_name": row[0],
                    "data_type": row[1], 
                    "is_nullable": row[2],
                    "column_default": row[3]
                } for row in table_check
            ],
            "has_processing_stage": any(row[0] == 'processing_stage' for row in table_check)
        }
    except Exception as e:
        return {"error": f"Database schema check failed: {str(e)}"}
    finally:
        if 'db' in locals():
            db.close()

@app.post("/edit-image/", response_model=schemas.EditCreateResponse)
@limiter.limit(f"{RATE_LIMIT_DAILY_IMAGES}/day")  # Configurable daily limit per IP
@limiter.limit(f"1/{RATE_LIMIT_BURST_SECONDS}seconds")  # Configurable burst protection per IP
async def edit_image_endpoint(request: Request, edit_request: EditImageRequest, db: Session = Depends(database.get_db)):
    # Validate follow-up editing if parent_edit_uuid is provided
    if edit_request.parent_edit_uuid:
        # Check if parent edit exists
        parent_edit = crud.get_edit_by_uuid(db, edit_request.parent_edit_uuid)
        if not parent_edit:
            raise HTTPException(status_code=404, detail="Parent edit not found")
        
        # Check if parent edit is completed
        if parent_edit.status != "completed":
            raise HTTPException(status_code=400, detail=f"Parent edit is {parent_edit.status}, cannot continue from incomplete edit")
        
        # Validate chain length
        chain_length = crud.validate_chain_length(db, edit_request.parent_edit_uuid)
        if chain_length == -1:
            raise HTTPException(status_code=400, detail="Maximum chain length of 5 edits reached")
        
        print(f"Starting follow-up edit (chain position {chain_length + 1}) with prompt: '{edit_request.prompt}'")
        print(f"Parent edit: {edit_request.parent_edit_uuid}")
    else:
        print(f"Starting new edit with prompt: '{edit_request.prompt}'")

    try:
        # Decode the base64 image
        header, encoded_image = edit_request.image.split(",", 1)
        image_bytes = base64.b64decode(encoded_image)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image format: {e}")
    
    original_file_name = f"original-{uuid.uuid4()}.png"
    
    # Start performance tracking immediately when request is received
    tracker = start_performance_tracking(0, "temp")  # Will update with real edit_id later
    tracker.start_stage("image_upload_s3")

    try:
        # Optimized S3 upload with better performance
        original_image_url = s3.upload_file_to_s3(image_bytes, original_file_name)
        print(f"Uploaded original image to: {original_image_url}")
        
        # Track S3 upload completion - Skip prompt enhancement for instant API response
        tracker.end_stage("image_upload_s3")
        tracker.start_stage("database_operations")
    except Exception as e:
        print(f"Failed to upload original image to S3: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to upload original image to S3: {e}")

    # Skip prompt enhancement in API - moved to Celery task for instant response
    original_prompt = edit_request.prompt
    print("Prompt enhancement moved to Celery task for faster API response")

    # Create database record with original prompt only (enhanced_prompt will be added by Celery)
    edit = crud.create_edit(
        db=db,
        prompt=original_prompt,
        enhanced_prompt=None,  # Will be set by Celery task
        original_image_url=original_image_url,
        parent_edit_uuid=edit_request.parent_edit_uuid
    )
    
    # Update tracker with real edit_id and uuid
    tracker.edit_id = edit.id
    tracker.edit_uuid = edit.uuid

    # Update status immediately to show progress to user
    crud.update_edit_status(db, edit.id, "processing")
    crud.update_edit_processing_stage(db, edit.id, "pending")  # Start with pending, Celery will update to enhancing_prompt
    
    # Track database operations completion and task queuing
    tracker.end_stage("database_operations")
    tracker.log_milestone("task_queued", f"celery_task_queued")
    
    # Process the image edit asynchronously with the final prompt
    tasks.process_image_edit.delay(edit.id)
    
    print(f"Edit request queued for processing with UUID: {edit.uuid}")

    polling_url = str(request.url_for('get_edit_status', edit_uuid=edit.uuid))

    return {"edit_id": edit.uuid, "polling_url": polling_url}

@app.get("/edit/{edit_uuid}", response_model=schemas.EditStatusResponse)
@limiter.limit(f"{RATE_LIMIT_STATUS_CHECKS_PER_MINUTE}/minute")  # Configurable status check limit
def get_edit_status(request: Request, edit_uuid: str, db: Session = Depends(database.get_db)):
    from src.status_messages import get_status_message
    
    db_edit = crud.get_edit_by_uuid(db, edit_uuid=edit_uuid)
    if db_edit is None:
        raise HTTPException(status_code=404, detail="Edit not found")
    
    # Get user-friendly progress information
    progress_info = get_status_message(db_edit.status, db_edit.processing_stage)
    
    return {
        "uuid": db_edit.uuid,
        "status": db_edit.status,
        "processing_stage": db_edit.processing_stage,
        "message": progress_info["message"],
        "progress_percent": progress_info["progress_percent"],
        "is_complete": progress_info["is_complete"],
        "is_error": progress_info["is_error"],
        "edited_image_url": db_edit.edited_image_url,
        "created_at": db_edit.created_at
    }

@app.post("/feedback/", response_model=schemas.FeedbackResponse)
@limiter.limit("5/minute")  # Limit feedback submissions to prevent spam
async def submit_feedback(request: Request, feedback: schemas.FeedbackCreate, db: Session = Depends(database.get_db)):
    """Submit feedback for an edit result"""
    
    # Get user IP for analytics
    user_ip = get_remote_address(request)
    
    # Validate that the edit exists
    edit = crud.get_edit_by_uuid(db, feedback.edit_uuid)
    if not edit:
        raise HTTPException(status_code=404, detail="Edit not found")
    
    # Check if edit is completed (can only give feedback on completed edits)
    if edit.status != "completed":
        raise HTTPException(status_code=400, detail="Can only provide feedback for completed edits")
    
    # Check if feedback already exists for this edit
    if crud.feedback_exists_for_edit(db, feedback.edit_uuid):
        raise HTTPException(status_code=409, detail="Feedback already submitted for this edit")
    
    # Create the feedback
    db_feedback = crud.create_feedback(db=db, feedback=feedback, user_ip=user_ip)
    
    if not db_feedback:
        raise HTTPException(status_code=500, detail="Failed to create feedback")
    
    rating_text = "thumbs up" if feedback.rating == 1 else "thumbs down"
    print(f"Feedback submitted for edit {feedback.edit_uuid}: {rating_text} ({feedback.rating})")
    if feedback.feedback_text:
        print(f"Feedback text: {feedback.feedback_text[:100]}...")  # Log first 100 chars
    
    return {
        "success": True,
        "message": "Thank you for your feedback!",
        "feedback_id": db_feedback.id
    }

@app.get("/feedback/{edit_uuid}", response_model=schemas.Feedback)
@limiter.limit("10/minute")  # Allow checking feedback status
async def get_feedback_for_edit(request: Request, edit_uuid: str, db: Session = Depends(database.get_db)):
    """Get feedback for a specific edit (optional endpoint for checking if feedback exists)"""
    
    # Validate that the edit exists
    edit = crud.get_edit_by_uuid(db, edit_uuid)
    if not edit:
        raise HTTPException(status_code=404, detail="Edit not found")
    
    # Get feedback for this edit
    feedback = crud.get_feedback_by_edit_uuid(db, edit_uuid)
    if not feedback:
        raise HTTPException(status_code=404, detail="No feedback found for this edit")
    
    return feedback

@app.get("/chain/{edit_uuid}")
@limiter.limit("10/minute")  # Allow checking chain history
async def get_edit_chain_history(request: Request, edit_uuid: str, db: Session = Depends(database.get_db)):
    """Get the complete chain history for an edit"""
    
    # Validate that the edit exists
    edit = crud.get_edit_by_uuid(db, edit_uuid)
    if not edit:
        raise HTTPException(status_code=404, detail="Edit not found")
    
    # Get chain history
    chain_history = crud.get_edit_chain_history(db, edit_uuid)
    
    return {
        "edit_uuid": edit_uuid,
        "chain_length": len(chain_history),
        "chain_history": chain_history
    }


