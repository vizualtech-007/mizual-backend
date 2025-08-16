import asyncio
from celery import Celery
from . import crud, database, flux_api, s3, models
from .flux_api import BFLServiceError
import os

# Get Redis URLs and modify them to work with Celery SSL requirements
broker_url = os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0")
backend_url = os.environ.get("CELERY_RESULT_BACKEND", "redis://redis:6379/0")

# Add environment prefix for Redis keys
ENVIRONMENT = os.environ.get("ENVIRONMENT", "production")
redis_prefix = f"{ENVIRONMENT}:"
print(f"Initializing Celery with environment: {ENVIRONMENT}, redis_prefix: {redis_prefix}")

# For rediss:// URLs, add the required SSL parameter that Celery expects
if broker_url.startswith('rediss://'):
    broker_url = broker_url + ('&' if '?' in broker_url else '?') + 'ssl_cert_reqs=none'

if backend_url.startswith('rediss://'):
    backend_url = backend_url + ('&' if '?' in backend_url else '?') + 'ssl_cert_reqs=none'

celery = Celery(
    __name__,
    broker=broker_url,
    backend=backend_url
)

@celery.task(name='tasks.process_image_edit', bind=True, autoretry_for=(BFLServiceError,), retry_kwargs={'max_retries': 2, 'countdown': 60}, soft_time_limit=300, time_limit=330)
def process_image_edit(self, edit_id: int):
    retry_count = self.request.retries
    print(f"CELERY TASK STARTED: process_image_edit for edit_id={edit_id} (attempt {retry_count + 1}/3)")
    
    # Use improved database connection with retry logic
    db = None
    try:
        db = database.get_db_with_retry(max_retries=3)
    except Exception as e:
        print(f"CRITICAL ERROR: Could not establish database connection for edit {edit_id}: {e}")
        return
    
    try:
        edit = crud.get_edit(db, edit_id)
        if not edit:
            print(f"TASK ERROR: Edit {edit_id} not found in database")
            return

        print(f"TASK PROCESSING: Edit {edit_id} with UUID {edit.uuid}")
        print(f"Original prompt: '{edit.prompt}'")
        print(f"Enhanced prompt: '{edit.enhanced_prompt}'")
    except Exception as e:
        print(f"DATABASE ERROR: Could not fetch edit {edit_id}: {e}")
        if db:
            db.close()
        return
    
    try:
        # Stage 1: Processing started
        print(f"UPDATING STATUS: edit_id={edit_id} to processing")
        crud.update_edit_status(db, edit_id, "processing")
        crud.update_edit_processing_stage(db, edit_id, "initializing_processing")
        print(f"STAGE UPDATED: initializing_processing for edit {edit_id}")
        
        # Stage: Preparing image data
        crud.update_edit_processing_stage(db, edit_id, "preparing_image_data")
        print(f"STAGE UPDATED: preparing_image_data for edit {edit_id}")

        # Determine which prompt to use (enhanced or original)
        prompt_to_use = edit.enhanced_prompt if edit.enhanced_prompt else edit.prompt
        print(f"Using prompt for BFL API: '{prompt_to_use[:100]}...'")
        
        # Stage: Fetching original image
        crud.update_edit_processing_stage(db, edit_id, "fetching_original_image")
        print(f"STAGE UPDATED: fetching_original_image for edit {edit_id}")
        
        # Use the original image URL directly (no localhost replacement needed)
        image_url = edit.original_image_url
        print(f"Fetching image from: {image_url}")
        
        import httpx
        print(f"Making HTTP request to fetch image...")
        response = httpx.get(image_url, timeout=30.0)
        response.raise_for_status()
        image_bytes = response.content
        print(f"Successfully fetched original image, size: {len(image_bytes)} bytes")
        
        # Stage: Connecting to AI service
        crud.update_edit_processing_stage(db, edit_id, "connecting_to_ai_service")
        print(f"STAGE UPDATED: connecting_to_ai_service for edit {edit_id}")

        print(f"Calling BFL API for edit {edit_id}")
        
        # Stage: Processing with AI
        crud.update_edit_processing_stage(db, edit_id, "processing_with_ai")
        print(f"STAGE UPDATED: processing_with_ai for edit {edit_id}")
        
        edited_image_bytes = asyncio.run(flux_api.edit_image_with_flux(image_bytes, prompt_to_use))
        print(f"BFL API returned edited image, size: {len(edited_image_bytes)} bytes")
        
        # Stage: Preparing result
        crud.update_edit_processing_stage(db, edit_id, "preparing_result")
        print(f"STAGE UPDATED: preparing_result for edit {edit_id}")

        # Stage 2: Uploading result
        print(f"UPDATING STAGE: uploading_result for edit {edit_id}")
        crud.update_edit_processing_stage(db, edit_id, "uploading_result")
        print(f"Uploading edited image to S3 for edit {edit_id}")

        edited_file_name = f"edited-{edit.uuid}.png"
        edited_image_url = s3.upload_file_to_s3(edited_image_bytes, edited_file_name)
        print(f"Uploaded edited image to: {edited_image_url}")

        # Stage 3: Completed
        print(f"UPDATING STATUS: edit_id={edit_id} to completed")
        crud.update_edit_with_result(db, edit_id, "completed", edited_image_url)
        crud.update_edit_processing_stage(db, edit_id, "completed")
        print(f"TASK COMPLETED: Edit {edit_id} completed successfully")

    except BFLServiceError as e:
        retry_count = self.request.retries
        max_retries = self.retry_kwargs.get('max_retries', 2)
        
        print(f"BFL SERVICE ERROR: {str(e)}")
        print(f"ERROR TYPE: BFLServiceError")
        print(f"STATUS CODE: {getattr(e, 'status_code', 'N/A')}")
        print(f"IS TEMPORARY: {getattr(e, 'is_temporary', False)}")
        print(f"RETRY INFO: Attempt {retry_count + 1}/{max_retries + 1}")
        
        # Check if we should retry based on error type
        should_retry = getattr(e, 'is_temporary', False) and retry_count < max_retries
        
        if not should_retry or retry_count >= max_retries:
            print(f"NOT RETRYING: Marking edit {edit_id} as failed")
            try:
                # Reconnect to database if needed
                if not db or db.is_active is False:
                    if db:
                        db.close()
                    db = database.get_db_with_retry(max_retries=3)
                
                crud.update_edit_status(db, edit_id, "failed")
                crud.update_edit_processing_stage(db, edit_id, "failed")
                print(f"STATUS UPDATED: Edit {edit_id} marked as failed due to BFL service error")
            except Exception as update_error:
                print(f"CRITICAL ERROR: Could not update status for edit {edit_id}: {update_error}")
            return  # Don't retry, mark as failed
        else:
            print(f"RETRYING: Will retry edit {edit_id} in 60 seconds (attempt {retry_count + 2}/{max_retries + 1})")
            # Re-raise to trigger Celery's retry mechanism
            raise
            
    except Exception as e:
        retry_count = self.request.retries
        max_retries = self.retry_kwargs.get('max_retries', 2)
        
        print(f"UNEXPECTED ERROR: Error processing edit {edit_id}: {str(e)}")
        print(f"ERROR TYPE: {type(e).__name__}")
        print(f"ERROR DETAILS: {repr(e)}")
        print(f"RETRY INFO: Attempt {retry_count + 1}/{max_retries + 1}")
        
        # For unexpected errors, always mark as failed (don't retry)
        print(f"UNEXPECTED ERROR: Marking edit {edit_id} as failed")
        try:
            # Reconnect to database if needed
            if not db or db.is_active is False:
                if db:
                    db.close()
                db = database.get_db_with_retry(max_retries=3)
            
            crud.update_edit_status(db, edit_id, "failed")
            crud.update_edit_processing_stage(db, edit_id, "failed")
            print(f"STATUS UPDATED: Edit {edit_id} marked as failed due to unexpected error")
        except Exception as update_error:
            print(f"CRITICAL ERROR: Could not update status for edit {edit_id}: {update_error}")
        return  # Don't retry unexpected errors
            
    finally:
        print(f"TASK FINISHED: Closing database connection for edit {edit_id}")
        db.close()

# Register the same function with the old name for backward compatibility with old tasks in queue
@celery.task(name='src.tasks.process_image_edit')
def process_image_edit_legacy(edit_id: int):
    """Legacy task name for old tasks in queue"""
    print(f"Legacy task called for edit {edit_id}")
    return process_image_edit(edit_id)

