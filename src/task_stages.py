"""
Stage-specific retry logic for image processing tasks.
Each stage can be retried independently without restarting the entire process.
"""

import asyncio
import httpx
from . import crud, database, flux_api, s3
from .flux_api import BFLServiceError


class StageProcessor:
    def __init__(self, edit_id: int, db):
        self.edit_id = edit_id
        self.db = db
        self.edit = None
        
    def get_edit(self):
        """Get edit details from database"""
        if not self.edit:
            self.edit = crud.get_edit(self.db, self.edit_id)
        return self.edit
    
    def update_stage(self, stage: str):
        """Update processing stage in database"""
        crud.update_edit_processing_stage(self.db, self.edit_id, stage)
        print(f"STAGE UPDATED: {stage} for edit {self.edit_id}")
    
    def stage_fetch_image(self):
        """Stage: Fetch original image from S3"""
        print(f"STAGE: Fetching original image for edit {self.edit_id}")
        self.update_stage("fetching_original_image")
        
        edit = self.get_edit()
        image_url = edit.original_image_url
        print(f"Fetching image from: {image_url}")
        
        response = httpx.get(image_url, timeout=30.0)
        response.raise_for_status()
        image_bytes = response.content
        print(f"Successfully fetched original image, size: {len(image_bytes)} bytes")
        
        return image_bytes
    
    def stage_process_with_ai(self, image_bytes: bytes, prompt: str):
        """Stage: Process image with BFL AI"""
        print(f"STAGE: Processing with AI for edit {self.edit_id}")
        self.update_stage("connecting_to_ai_service")
        
        print(f"Calling BFL API for edit {self.edit_id}")
        self.update_stage("processing_with_ai")
        
        edited_image_bytes = asyncio.run(flux_api.edit_image_with_flux(image_bytes, prompt))
        print(f"BFL API returned edited image, size: {len(edited_image_bytes)} bytes")
        
        return edited_image_bytes
    
    def stage_upload_result(self, edited_image_bytes: bytes):
        """Stage: Upload result to S3"""
        print(f"STAGE: Uploading result for edit {self.edit_id}")
        self.update_stage("preparing_result")
        
        edit = self.get_edit()
        edited_file_name = f"edited-{edit.uuid}.png"
        
        self.update_stage("uploading_result")
        edited_image_url = s3.upload_file_to_s3(edited_image_bytes, edited_file_name)
        print(f"Uploaded edited image to: {edited_image_url}")
        
        return edited_image_url
    
    def stage_complete(self, edited_image_url: str):
        """Stage: Mark as completed"""
        print(f"STAGE: Completing edit {self.edit_id}")
        crud.update_edit_with_result(self.db, self.edit_id, "completed", edited_image_url)
        crud.update_edit_processing_stage(self.db, self.edit_id, "completed")
        print(f"TASK COMPLETED: Edit {self.edit_id} completed successfully")


def retry_stage_with_backoff(stage_func, stage_name: str, max_retries: int = 3, base_delay: int = 30):
    """
    Retry a specific stage with exponential backoff.
    Only retries the failed stage, not the entire process.
    """
    for attempt in range(max_retries):
        try:
            print(f"STAGE ATTEMPT: {stage_name} (attempt {attempt + 1}/{max_retries})")
            return stage_func()
        except BFLServiceError as e:
            if not getattr(e, 'is_temporary', False) or attempt == max_retries - 1:
                print(f"STAGE FAILED: {stage_name} - {str(e)}")
                raise e
            
            delay = base_delay * (2 ** attempt)  # Exponential backoff
            print(f"STAGE RETRY: {stage_name} failed, retrying in {delay}s (attempt {attempt + 1}/{max_retries})")
            import time
            time.sleep(delay)
        except Exception as e:
            print(f"STAGE FAILED: {stage_name} - Unexpected error: {str(e)}")
            raise e
    
    raise Exception(f"Stage {stage_name} failed after {max_retries} attempts")


def process_edit_with_stage_retries(edit_id: int):
    """
    Process edit with stage-specific retries.
    Each stage can be retried independently.
    """
    db = None
    try:
        # Initialize
        db = database.get_db_with_retry(max_retries=3)
        processor = StageProcessor(edit_id, db)
        edit = processor.get_edit()
        
        if not edit:
            print(f"TASK ERROR: Edit {edit_id} not found in database")
            return
        
        print(f"TASK PROCESSING: Edit {edit_id} with UUID {edit.uuid}")
        print(f"Original prompt: '{edit.prompt}'")
        print(f"Enhanced prompt: '{edit.enhanced_prompt}'")
        
        # Initialize processing
        crud.update_edit_status(db, edit_id, "processing")
        processor.update_stage("initializing_processing")
        processor.update_stage("preparing_image_data")
        
        # Determine prompt to use
        prompt_to_use = edit.enhanced_prompt if edit.enhanced_prompt else edit.prompt
        print(f"Using prompt for BFL API: '{prompt_to_use[:100]}...'")
        
        # Stage 1: Fetch image (with retries)
        image_bytes = retry_stage_with_backoff(
            lambda: processor.stage_fetch_image(),
            "fetch_image",
            max_retries=3,
            base_delay=10
        )
        
        # Stage 2: Process with AI (with retries)
        edited_image_bytes = retry_stage_with_backoff(
            lambda: processor.stage_process_with_ai(image_bytes, prompt_to_use),
            "process_with_ai",
            max_retries=3,
            base_delay=60
        )
        
        # Stage 3: Upload result (with retries)
        edited_image_url = retry_stage_with_backoff(
            lambda: processor.stage_upload_result(edited_image_bytes),
            "upload_result",
            max_retries=3,
            base_delay=10
        )
        
        # Stage 4: Complete
        processor.stage_complete(edited_image_url)
        
    except Exception as e:
        print(f"TASK FAILED: Edit {edit_id} failed: {str(e)}")
        if db:
            try:
                crud.update_edit_status(db, edit_id, "failed")
                crud.update_edit_processing_stage(db, edit_id, "failed")
                print(f"STATUS UPDATED: Edit {edit_id} marked as failed")
            except Exception as update_error:
                print(f"CRITICAL ERROR: Could not update status for edit {edit_id}: {update_error}")
        raise e
    
    finally:
        if db:
            db.close()