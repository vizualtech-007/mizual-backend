import asyncio
from celery import Celery
from . import crud, database, flux_api, s3, models
from .flux_api import BFLServiceError
from .task_stages import process_edit_with_stage_retries
from .logger import logger
import os

# Get Redis URLs and modify them to work with Celery SSL requirements
broker_url = os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0")
backend_url = os.environ.get("CELERY_RESULT_BACKEND", "redis://redis:6379/0")

# Add environment prefix for Redis keys
ENVIRONMENT = os.environ.get("ENVIRONMENT", "production")
redis_prefix = f"{ENVIRONMENT}:"

# Environment-aware memory configuration
MAX_WORKERS = int(os.environ.get("MAX_WORKERS", "5" if ENVIRONMENT == "production" else "1"))
CELERY_MEMORY_LIMIT = os.environ.get("CELERY_WORKER_MEMORY_LIMIT", "1GB" if ENVIRONMENT == "production" else "200MB")

logger.info(f"Initializing Celery with environment: {ENVIRONMENT}, redis_prefix: {redis_prefix}")
logger.info(f"Resource configuration - MAX_WORKERS: {MAX_WORKERS}, MEMORY_LIMIT: {CELERY_MEMORY_LIMIT}")

# For rediss:// URLs, add the required SSL parameter that Celery expects
if broker_url.startswith('rediss://'):
    broker_url = broker_url + ('&' if '?' in broker_url else '?') + 'ssl_cert_reqs=none'

if backend_url.startswith('rediss://'):
    backend_url = backend_url + ('&' if '?' in backend_url else '?') + 'ssl_cert_reqs=none'

celery = Celery(
    __name__,
    broker=broker_url,
    backend=backend_url,
    broker_transport_options={'polling_interval': 0.1}
)

@celery.task(name='src.tasks.process_image_edit', soft_time_limit=600, time_limit=660)
def process_image_edit(edit_id: int):
    """
    Process image edit with stage-specific retries.
    Each stage can be retried independently without restarting the entire process.
    """
    logger.info(f"CELERY TASK STARTED: process_image_edit for edit_id={edit_id} (stage-specific retries)")
    
    try:
        # Use the stage-specific retry system
        process_edit_with_stage_retries(edit_id)
        logger.info(f"TASK COMPLETED: Edit {edit_id} processed successfully")
        
    except Exception as e:
        logger.error(f"TASK FAILED: Edit {edit_id} failed with error: {str(e)}")
        logger.error(f"ERROR TYPE: {type(e).__name__}")
        logger.error(f"ERROR DETAILS: {repr(e)}")
        
        # Don't use Celery's retry mechanism - we handle retries internally
        # Just mark as failed and exit
        return

