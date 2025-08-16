import asyncio
from celery import Celery
from . import crud, database, flux_api, s3, models
from .flux_api import BFLServiceError
from .task_stages import process_edit_with_stage_retries
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

@celery.task(name='tasks.process_image_edit', bind=True, soft_time_limit=600, time_limit=660)
def process_image_edit(self, edit_id: int):
    """
    Process image edit with stage-specific retries.
    Each stage can be retried independently without restarting the entire process.
    """
    print(f"CELERY TASK STARTED: process_image_edit for edit_id={edit_id} (stage-specific retries)")
    
    try:
        # Use the new stage-specific retry system
        process_edit_with_stage_retries(edit_id)
        print(f"TASK COMPLETED: Edit {edit_id} processed successfully")
        
    except Exception as e:
        print(f"TASK FAILED: Edit {edit_id} failed with error: {str(e)}")
        print(f"ERROR TYPE: {type(e).__name__}")
        print(f"ERROR DETAILS: {repr(e)}")
        
        # Don't use Celery's retry mechanism - we handle retries internally
        # Just mark as failed and exit
        return

# Register the same function with the old name for backward compatibility with old tasks in queue
@celery.task(name='src.tasks.process_image_edit')
def process_image_edit_legacy(edit_id: int):
    """Legacy task name for old tasks in queue"""
    print(f"Legacy task called for edit {edit_id}")
    return process_image_edit(edit_id)

