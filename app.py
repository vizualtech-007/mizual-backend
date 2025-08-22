from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from src import schemas, s3, tasks, db_raw, cache

import uuid
import base64
import os
from src.logger import logger

# Rate limiting configuration from environment variables
RATE_LIMIT_DAILY_IMAGES = os.environ.get("RATE_LIMIT_DAILY_IMAGES", "3")
RATE_LIMIT_BURST_SECONDS = os.environ.get("RATE_LIMIT_BURST_SECONDS", "10")
RATE_LIMIT_STATUS_CHECKS_PER_MINUTE = os.environ.get("RATE_LIMIT_STATUS_CHECKS_PER_MINUTE", "30")

# Chain editing configuration
MAX_CHAIN_LENGTH = int(os.environ.get("MAX_CHAIN_LENGTH", "5"))

# Image type validation configuration
UNSUPPORTED_IMAGE_TYPES = os.environ.get("UNSUPPORTED_IMAGE_TYPES", "heic,avif,gif").lower().split(",")
UNSUPPORTED_IMAGE_TYPES = [img_type.strip() for img_type in UNSUPPORTED_IMAGE_TYPES if img_type.strip()]

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)
app = FastAPI()

# Add rate limiter to app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Environment-aware CORS configuration
ENVIRONMENT = os.environ.get("ENVIRONMENT", "production")

if ENVIRONMENT == "preview":
    # Dev/Preview environment - allow all origins for development
    # This is safe for preview environment as it's not production
    allowed_origins = ["*"]
else:
    # Production environment - restrict to production URLs only
    allowed_origins = [
        "https://mizual.ai",
        "https://www.mizual.ai",
        "https://mizual-frontend-git-main-*.vercel.app"  # Allow main branch Vercel deployments
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False if ENVIRONMENT == "preview" else True,  # Can't use credentials with allow_origins=["*"]
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

class EditImageRequest(BaseModel):
    prompt: str
    image: str
    parent_edit_uuid: Optional[str] = None  # For follow-up editing

def detect_image_type(image_bytes: bytes) -> str:
    """Detect image type from image bytes using magic bytes"""
    if not image_bytes:
        return 'unknown'
    
    # Check magic bytes for common formats
    if image_bytes.startswith(b'\xff\xd8\xff'):
        return 'jpeg'
    elif image_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'png'
    elif image_bytes.startswith(b'GIF87a') or image_bytes.startswith(b'GIF89a'):
        return 'gif'
    elif image_bytes.startswith(b'RIFF') and len(image_bytes) > 12 and b'WEBP' in image_bytes[:12]:
        return 'webp'
    elif len(image_bytes) > 32 and (b'avif' in image_bytes[:32].lower() or b'ftypavif' in image_bytes[:32]):
        return 'avif'
    elif len(image_bytes) > 32 and (b'heic' in image_bytes[:32].lower() or b'ftypheic' in image_bytes[:32]):
        return 'heic'
    # Check for BMP
    elif image_bytes.startswith(b'BM'):
        return 'bmp'
    # Check for TIFF
    elif image_bytes.startswith(b'II*\x00') or image_bytes.startswith(b'MM\x00*'):
        return 'tiff'
    else:
        return 'unknown'

def validate_image_type(image_bytes: bytes) -> tuple[bool, str]:
    """Validate if image type is supported"""
    detected_type = detect_image_type(image_bytes)
    
    if detected_type == 'unknown':
        return False, "Unable to detect image format. Please upload a valid image file."
    
    if detected_type in UNSUPPORTED_IMAGE_TYPES:
        supported_types = [t for t in ['jpeg', 'jpg', 'png', 'webp'] if t not in UNSUPPORTED_IMAGE_TYPES]
        return False, f"Image format '{detected_type.upper()}' is not supported. Please use one of: {', '.join(supported_types).upper()}"
    
    return True, detected_type

@app.on_event("startup")
def startup_event():
    s3.create_bucket_if_not_exists()
    # Skip database migrations for now - tables are already properly set up
    logger.info("Startup complete - database migrations skipped")

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
        with db_raw.get_connection() as conn:
            with conn.cursor() as cur:
                # Check current schema path
                cur.execute("SHOW search_path")
                schema_result = cur.fetchone()
                current_schema = schema_result[0] if schema_result else "unknown"
                
                # Check if edits table exists and get its columns
                cur.execute("""
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns 
                    WHERE table_name = 'edits' 
                    AND table_schema = ANY(current_schemas(false))
                    ORDER BY ordinal_position
                """)
                table_check = cur.fetchall()
                
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

@app.get("/debug/cache-stats")
@limiter.limit("5/minute")
async def debug_cache_stats(request: Request):
    """Debug endpoint to check cache statistics"""
    return cache.get_cache_stats()

@app.get("/debug/db-performance")
@limiter.limit("3/minute")
async def debug_database_performance(request: Request):
    """Debug endpoint to check database performance and optimization suggestions"""
    try:
        return db_raw.get_database_performance_info()
    except Exception as e:
        return {"error": f"Database performance check failed: {str(e)}"}

@app.post("/edit-image/", response_model=schemas.EditCreateResponse)
@limiter.limit(f"{RATE_LIMIT_DAILY_IMAGES}/day")  # Configurable daily limit per IP
@limiter.limit(f"1/{RATE_LIMIT_BURST_SECONDS}seconds")  # Configurable burst protection per IP
async def edit_image_endpoint(request: Request, edit_request: EditImageRequest):
    # Validate follow-up editing if parent_edit_uuid is provided
    if edit_request.parent_edit_uuid:
        # Check if parent edit exists
        parent_edit = db_raw.get_edit_by_uuid(edit_request.parent_edit_uuid)
        if not parent_edit:
            raise HTTPException(status_code=404, detail="Parent edit not found")
        
        # Check if parent edit is completed
        if parent_edit['status'] != "completed":
            raise HTTPException(status_code=400, detail=f"Parent edit is {parent_edit['status']}, cannot continue from incomplete edit")
        
        # Validate chain length
        # Check chain length (configurable max edits)
        chain_history = db_raw.get_edit_chain_history(edit_request.parent_edit_uuid)
        if len(chain_history) >= MAX_CHAIN_LENGTH:
            raise HTTPException(status_code=400, detail=f"Maximum chain length of {MAX_CHAIN_LENGTH} edits reached")
        
        logger.info(f"Starting follow-up edit (chain position {len(chain_history) + 1}) with prompt: '{edit_request.prompt}'")
        logger.info(f"Parent edit: {edit_request.parent_edit_uuid}")
    else:
        logger.info(f"Starting new edit with prompt: '{edit_request.prompt}'")

    try:
        # Decode the base64 image
        header, encoded_image = edit_request.image.split(",", 1)
        image_bytes = base64.b64decode(encoded_image)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image format: {e}")
    
    # Validate image type
    is_valid, validation_message = validate_image_type(image_bytes)
    if not is_valid:
        logger.warning(f"Image upload rejected: {validation_message}")
        raise HTTPException(status_code=400, detail=validation_message)
    
    logger.info(f"Image type validated: {validation_message}")
    
    original_file_name = f"original-{uuid.uuid4()}.png"
    
    try:
        # Optimized S3 upload with better performance
        original_image_url = s3.upload_file_to_s3(image_bytes, original_file_name)
        logger.info(f"Uploaded original image to: {original_image_url}")
        
    except Exception as e:
        logger.error(f"Failed to upload original image to S3: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to upload original image to S3: {e}")

    # Skip prompt enhancement in API - moved to Celery task for instant response
    original_prompt = edit_request.prompt
    logger.info("Prompt enhancement moved to Celery task for faster API response")

    # Create database record with original prompt only (enhanced_prompt will be added by Celery)
    edit = db_raw.create_edit(
        prompt=original_prompt,
        enhanced_prompt=None,  # Will be set by Celery task
        original_image_url=original_image_url,
        parent_edit_uuid=edit_request.parent_edit_uuid
    )
    
    # Update status immediately to show progress to user - INSTANT FEEDBACK
    db_raw.update_edit_status(edit['id'], "processing")
    logger.info(f"API: Setting processing stage to 'enhancing_prompt' for edit {edit['id']}")
    db_raw.update_edit_processing_stage(edit['id'], "enhancing_prompt")  # Show enhancing_prompt immediately
    logger.info(f"API: Stage updated successfully for edit {edit['id']}")
    
    # Verify the update worked
    updated_edit = db_raw.get_edit_by_id(edit['id'])
    logger.info(f"API: Verified stage is now '{updated_edit['processing_stage']}' for edit {edit['id']}")
    
    # Process the image edit asynchronously with the final prompt
    tasks.celery.send_task('src.tasks.process_image_edit', args=[edit['id']])
    
    logger.info(f"Edit request queued for processing with UUID: {edit['uuid']}")

    polling_url = str(request.url_for('get_edit_status', edit_uuid=edit['uuid']))

    return {"edit_id": edit['uuid'], "polling_url": polling_url}

@app.get("/edit/{edit_uuid}", response_model=schemas.EditStatusResponse)
@limiter.limit(f"{RATE_LIMIT_STATUS_CHECKS_PER_MINUTE}/minute")  # Configurable status check limit
def get_edit_status(request: Request, edit_uuid: str):
    from src.status_messages import get_status_message
    
    # Try to get from cache first (status checks are frequent)
    cached_status = cache.get_cached_edit_status(edit_uuid)
    if cached_status:
        return cached_status
    
    db_edit = db_raw.get_edit_by_uuid(edit_uuid)
    if db_edit is None:
        raise HTTPException(status_code=404, detail="Edit not found")
    
    # Get user-friendly progress information
    progress_info = get_status_message(db_edit['status'], db_edit['processing_stage'])
    
    response_data = {
        "uuid": db_edit['uuid'],
        "status": db_edit['status'],
        "processing_stage": db_edit['processing_stage'],
        "message": progress_info["message"],
        "progress_percent": progress_info["progress_percent"],
        "is_complete": progress_info["is_complete"],
        "is_error": progress_info["is_error"],
        "edited_image_url": db_edit['edited_image_url'],
        "prompt": db_edit['prompt'],
        "created_at": db_edit['created_at']
    }
    
    # Cache the response (short TTL since status changes frequently)
    cache.cache_edit_status(edit_uuid, response_data)
    
    return response_data

@app.post("/feedback/", response_model=schemas.FeedbackResponse)
@limiter.limit("5/minute")  # Limit feedback submissions to prevent spam
async def submit_feedback(request: Request, feedback: schemas.FeedbackCreate):
    """Submit feedback for an edit result"""
    
    # Get user IP for analytics
    user_ip = get_remote_address(request)
    
    # Validate that the edit exists
    edit = db_raw.get_edit_by_uuid(feedback.edit_uuid)
    if not edit:
        raise HTTPException(status_code=404, detail="Edit not found")
    
    # Check if edit is completed (can only give feedback on completed edits)
    if edit['status'] != "completed":
        raise HTTPException(status_code=400, detail="Can only provide feedback for completed edits")
    
    # Check if feedback already exists for this edit
    existing_feedback = db_raw.get_edit_feedback(feedback.edit_uuid)
    if existing_feedback:
        raise HTTPException(status_code=409, detail="Feedback already submitted for this edit")
    
    # Create the feedback
    success = db_raw.create_edit_feedback(
        edit_uuid=feedback.edit_uuid,
        rating=feedback.rating,
        feedback_text=feedback.feedback_text,
        user_ip=user_ip
    )
    if not success:
        raise HTTPException(status_code=500, detail="Failed to create feedback")
    
    
    rating_text = "thumbs up" if feedback.rating == 1 else "thumbs down"
    logger.info(f"Feedback submitted for edit {feedback.edit_uuid}: {rating_text} ({feedback.rating})")
    if feedback.feedback_text:
        logger.info(f"Feedback text: {feedback.feedback_text[:100]}...")  # Log first 100 chars
    
    return {
        "success": True,
        "message": "Thank you for your feedback!",
        "feedback_id": feedback.edit_uuid  # Use edit_uuid as identifier since we don't have auto-increment ID
    }

@app.get("/feedback/{edit_uuid}", response_model=schemas.Feedback)
@limiter.limit("10/minute")  # Allow checking feedback status
async def get_feedback_for_edit(request: Request, edit_uuid: str):
    """Get feedback for a specific edit (optional endpoint for checking if feedback exists)"""
    
    # Try to get from cache first (feedback rarely changes)
    cached_feedback = cache.get_cached_edit_feedback(edit_uuid)
    if cached_feedback:
        return cached_feedback
    
    # Validate that the edit exists
    edit = db_raw.get_edit_by_uuid(edit_uuid)
    if not edit:
        raise HTTPException(status_code=404, detail="Edit not found")
    
    # Get feedback for this edit
    feedback = db_raw.get_edit_feedback(edit_uuid)
    if not feedback:
        raise HTTPException(status_code=404, detail="No feedback found for this edit")
    
    # Cache the feedback (longer TTL since feedback doesn't change)
    cache.cache_edit_feedback(edit_uuid, feedback)
    
    return feedback

@app.get("/chain/{edit_uuid}")
@limiter.limit("10/minute")  # Allow checking chain history
async def get_edit_chain_history(request: Request, edit_uuid: str):
    """Get the complete chain history for an edit"""
    
    # Try to get from cache first
    cached_chain = cache.get_cached_chain_history(edit_uuid)
    if cached_chain:
        return {
            "edit_uuid": edit_uuid,
            "chain_length": len(cached_chain),
            "chain_history": cached_chain
        }
    
    # Validate that the edit exists
    edit = db_raw.get_edit_by_uuid(edit_uuid)
    if not edit:
        raise HTTPException(status_code=404, detail="Edit not found")
    
    # Get chain history
    chain_history = db_raw.get_edit_chain_history(edit_uuid)
    
    # Cache the chain history
    cache.cache_chain_history(edit_uuid, chain_history)
    
    return {
        "edit_uuid": edit_uuid,
        "chain_length": len(chain_history),
        "chain_history": chain_history
    }
