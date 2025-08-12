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
    db = next(database.get_db())
    edit = crud.get_edit(db, edit_id)
    if not edit:
        print(f"Edit {edit_id} not found")
        return

    print(f"Processing edit {edit_id} with UUID {edit.uuid}")
    crud.update_edit_status(db, edit_id, "processing")

    try:
        # Determine which prompt to use (enhanced or original)
        prompt_to_use = edit.enhanced_prompt if edit.enhanced_prompt else edit.prompt
        print(f"Using prompt for processing: '{prompt_to_use}'")
        
        # Replace public hostname with internal Docker network hostname for image fetching
        internal_image_url = edit.original_image_url.replace("localhost", "minio")
        print(f"Fetching image from: {internal_image_url}")
        
        import httpx
        response = httpx.get(internal_image_url)
        response.raise_for_status()
        image_bytes = response.content
        print(f"Successfully fetched original image, size: {len(image_bytes)} bytes")

        print(f"Calling BFL API for edit {edit_id}")
        edited_image_bytes = asyncio.run(flux_api.edit_image_with_flux(image_bytes, prompt_to_use))
        print(f"BFL API returned edited image, size: {len(edited_image_bytes)} bytes")

        edited_file_name = f"edited-{edit.uuid}.png"
        edited_image_url = s3.upload_file_to_s3(edited_image_bytes, edited_file_name)
        print(f"Uploaded edited image to: {edited_image_url}")

        crud.update_edit_with_result(db, edit_id, "completed", edited_image_url)
        print(f"Edit {edit_id} completed successfully")

    except Exception as e:
        print(f"Error processing edit {edit_id}: {str(e)}")
        crud.update_edit_status(db, edit_id, "failed")
    finally:
        db.close()

# Register the same function with the old name for backward compatibility with old tasks in queue
@celery.task(name='src.tasks.process_image_edit')
def process_image_edit_legacy(edit_id: int):
    """Legacy task name for old tasks in queue"""
    print(f"Legacy task called for edit {edit_id}")
    return process_image_edit(edit_id)

