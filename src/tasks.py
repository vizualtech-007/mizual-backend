import asyncio
from celery import Celery
from . import flux_api, s3
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

# Unified memory configuration for 2GB RAM, 2 vCPU Lightsail instances
MAX_WORKERS = int(os.environ.get("MAX_WORKERS", "5"))
CELERY_MEMORY_LIMIT = os.environ.get("CELERY_WORKER_MEMORY_LIMIT", "1GB")
CELERY_CONCURRENCY = int(os.environ.get("CELERY_CONCURRENCY", "1"))

logger.info(f"Initializing Celery with environment: {ENVIRONMENT}, redis_prefix: {redis_prefix}")
logger.info(f"Unified resource configuration - MAX_WORKERS: {MAX_WORKERS}, MEMORY_LIMIT: {CELERY_MEMORY_LIMIT}, CONCURRENCY: {CELERY_CONCURRENCY}")

# For rediss:// URLs, add the required SSL parameter that Celery expects
if broker_url.startswith('rediss://'):
    broker_url = broker_url + ('&' if '?' in broker_url else '?') + 'ssl_cert_reqs=none'

if backend_url.startswith('rediss://'):
    backend_url = backend_url + ('&' if '?' in backend_url else '?') + 'ssl_cert_reqs=none'

# Unified broker configuration for identical Lightsail environments
broker_transport_options = {'polling_interval': 0.1}  # Fast polling for both environments
logger.info("Using unified polling interval: 0.1 seconds")

celery = Celery(
    __name__,
    broker=broker_url,
    backend=backend_url,
    broker_transport_options=broker_transport_options
)

# Configure Celery for 3 concurrent workers with optimized serialization
celery.conf.update(
    worker_concurrency=CELERY_CONCURRENCY,  # Use environment variable
    worker_prefetch_multiplier=1,           # Process one task at a time per worker
    task_acks_late=True,                   # Better error handling
    worker_max_tasks_per_child=100,        # Recycle worker after 100 tasks to prevent memory leaks
    
    # Optimized serialization for better performance
    task_serializer='json',                # JSON is faster than pickle
    result_serializer='json',              # JSON results
    accept_content=['json'],               # Only accept JSON
    result_expires=3600,                   # Results expire after 1 hour
    
    # Performance optimizations
    task_compression='gzip',               # Compress task data
    result_compression='gzip',             # Compress results
    task_ignore_result=False,              # We need results for polling
    
    # Connection optimization
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
)

logger.info(f"Celery configured with concurrency: {CELERY_CONCURRENCY}, prefetch: 1, max_tasks_per_child: 100")

@celery.task(
    name='src.tasks.process_image_edit', 
    soft_time_limit=600, 
    time_limit=660,
    serializer='json',
    compression='gzip',
    acks_late=True
)
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

