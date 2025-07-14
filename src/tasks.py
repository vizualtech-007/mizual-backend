import asyncio
from celery import Celery
from . import crud, database, flux_api, s3, models
import os

# Get Redis URLs and modify them to work with Celery SSL requirements
broker_url = os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0")
backend_url = os.environ.get("CELERY_RESULT_BACKEND", "redis://redis:6379/0")

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

@celery.task
def process_image_edit(edit_id: int):
    db = next(database.get_db())
    edit = crud.get_edit(db, edit_id)
    if not edit:
        return

    crud.update_edit_status(db, edit_id, "processing")

    try:
        # Replace public hostname with internal Docker network hostname for image fetching.
        internal_image_url = edit.original_image_url.replace("localhost", "minio")
        
        import httpx
        response = httpx.get(internal_image_url)
        response.raise_for_status()
        image_bytes = response.content

        edited_image_bytes = asyncio.run(flux_api.edit_image_with_flux(image_bytes, edit.prompt))

        edited_file_name = f"edited-{edit.uuid}.png"
        edited_image_url = s3.upload_file_to_s3(edited_image_bytes, edited_file_name)

        crud.update_edit_with_result(db, edit_id, "completed", edited_image_url)

    except Exception as e:
        crud.update_edit_status(db, edit_id, "failed")
        # Log error for debugging. Use structured logging in production.
        print(f"Error processing edit {edit_id}: {e}")
    finally:
        db.close()

