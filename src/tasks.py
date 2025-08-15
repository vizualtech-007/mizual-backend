import asyncio
from celery import Celery
from . import crud, database, flux_api, s3, models
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

@celery.task(name='tasks.process_image_edit')
def process_image_edit(edit_id: int):
    print(f"🔄 CELERY TASK STARTED: process_image_edit for edit_id={edit_id}")
    
    db = next(database.get_db())
    edit = crud.get_edit(db, edit_id)
    if not edit:
        print(f"❌ TASK ERROR: Edit {edit_id} not found in database")
        return

    print(f"✅ TASK PROCESSING: Edit {edit_id} with UUID {edit.uuid}")
    print(f"📝 Original prompt: '{edit.prompt}'")
    print(f"🤖 Enhanced prompt: '{edit.enhanced_prompt}'")
    
    try:
        # Stage 1: Processing started
        print(f"🔄 UPDATING STATUS: edit_id={edit_id} to processing")
        crud.update_edit_status(db, edit_id, "processing")
        crud.update_edit_processing_stage(db, edit_id, "processing_image")
        print(f"✅ STATUS UPDATED: processing_image stage for edit {edit_id}")

        # Determine which prompt to use (enhanced or original)
        prompt_to_use = edit.enhanced_prompt if edit.enhanced_prompt else edit.prompt
        print(f"🎯 Using prompt for BFL API: '{prompt_to_use[:100]}...'")
        
        # Use the original image URL directly (no localhost replacement needed)
        image_url = edit.original_image_url
        print(f"🖼️  Fetching image from: {image_url}")
        
        import httpx
        print(f"🌐 Making HTTP request to fetch image...")
        response = httpx.get(image_url, timeout=30.0)
        response.raise_for_status()
        image_bytes = response.content
        print(f"✅ Successfully fetched original image, size: {len(image_bytes)} bytes")

        print(f"🤖 Calling BFL API for edit {edit_id}")
        edited_image_bytes = asyncio.run(flux_api.edit_image_with_flux(image_bytes, prompt_to_use))
        print(f"✅ BFL API returned edited image, size: {len(edited_image_bytes)} bytes")

        # Stage 2: Uploading result
        print(f"🔄 UPDATING STAGE: uploading_result for edit {edit_id}")
        crud.update_edit_processing_stage(db, edit_id, "uploading_result")
        print(f"📤 Uploading edited image to S3 for edit {edit_id}")

        edited_file_name = f"edited-{edit.uuid}.png"
        edited_image_url = s3.upload_file_to_s3(edited_image_bytes, edited_file_name)
        print(f"✅ Uploaded edited image to: {edited_image_url}")

        # Stage 3: Completed
        print(f"🔄 UPDATING STATUS: edit_id={edit_id} to completed")
        crud.update_edit_with_result(db, edit_id, "completed", edited_image_url)
        crud.update_edit_processing_stage(db, edit_id, "completed")
        print(f"🎉 TASK COMPLETED: Edit {edit_id} completed successfully")

    except Exception as e:
        print(f"❌ TASK ERROR: Error processing edit {edit_id}: {str(e)}")
        print(f"❌ ERROR TYPE: {type(e).__name__}")
        print(f"❌ ERROR DETAILS: {repr(e)}")
        
        try:
            crud.update_edit_status(db, edit_id, "failed")
            crud.update_edit_processing_stage(db, edit_id, "failed")
            print(f"✅ STATUS UPDATED: Edit {edit_id} marked as failed")
        except Exception as update_error:
            print(f"❌ CRITICAL ERROR: Could not update status for edit {edit_id}: {update_error}")
            
    finally:
        print(f"🔚 TASK FINISHED: Closing database connection for edit {edit_id}")
        db.close()

# Register the same function with the old name for backward compatibility with old tasks in queue
@celery.task(name='src.tasks.process_image_edit')
def process_image_edit_legacy(edit_id: int):
    """Legacy task name for old tasks in queue"""
    print(f"Legacy task called for edit {edit_id}")
    return process_image_edit(edit_id)

