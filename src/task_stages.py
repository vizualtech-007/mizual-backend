"""
Stage-specific retry logic for image processing tasks.
Each stage can be retried independently without restarting the entire process.
"""

import asyncio
import httpx
from . import crud, database, flux_api, s3
from .flux_api import BFLServiceError
from .performance_tracker import get_performance_tracker, finish_performance_tracking
import os
from .performance_tracker import PerformanceTracker
from datetime import timezone

# Import LLM provider
try:
    from .llm import get_provider
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False


class StageProcessor:
    def __init__(self, edit_id: int, db):
        self.edit_id = edit_id
        self.db = db
        self.edit = None
        self.cached_image_bytes = None  # Cache for image bytes to avoid multiple S3 downloads
        
    def get_edit(self):
        """Get edit details from database"""
        if not self.edit:
            self.edit = crud.get_edit(self.db, self.edit_id)
        return self.edit
    
    def update_stage(self, stage: str):
        """Update processing stage in database"""
        crud.update_edit_processing_stage(self.db, self.edit_id, stage)
        print(f"STAGE UPDATED: {stage} for edit {self.edit_id}")
    
    def stage_enhance_prompt(self):
        """Stage: Enhance prompt with LLM - Optimized to skip redundant stage update"""
        print(f"STAGE: Enhancing prompt for edit {self.edit_id} (API already set stage)")
        # Verify current stage before starting
        edit = self.get_edit()
        print(f"CELERY: Current stage when starting prompt enhancement: '{edit.processing_stage}'")
        
        edit = self.get_edit()
        original_prompt = edit.prompt
        enhanced_prompt = None
        
        if LLM_AVAILABLE and os.environ.get("ENABLE_PROMPT_ENHANCEMENT", "true").lower() in ["true", "1", "yes"]:
            try:
                print("Attempting prompt enhancement with LLM")
                llm_provider = get_provider()
                if llm_provider:
                    # Fetch image for prompt enhancement - Optimized
                    print(f"Fetching image for prompt enhancement from: {edit.original_image_url}")
                    import httpx
                    timeout = httpx.Timeout(10.0, connect=3.0)  # Even faster timeouts
                    with httpx.Client(timeout=timeout) as client:
                        response = client.get(edit.original_image_url)
                        response.raise_for_status()
                        image_bytes = response.content
                    
                    enhanced_prompt = llm_provider.enhance_prompt(original_prompt, image_bytes)
                    print("Gemini enhancement completed")
                    print(f"Original prompt: '{original_prompt}'")
                    print(f"Enhanced prompt: '{enhanced_prompt}'")
                    
                    # Update database with enhanced prompt
                    crud.update_edit_enhanced_prompt(self.db, self.edit_id, enhanced_prompt)
                    print(f"Enhanced prompt saved to database for edit {self.edit_id}")
                    
                    # Store image_bytes for reuse to avoid second S3 download
                    self.cached_image_bytes = image_bytes
                    print(f"Cached image bytes for reuse (size: {len(image_bytes)} bytes)")
                    
            except Exception as e:
                print(f"LLM enhancement failed: {e}")
                print("Falling back to original prompt")
                enhanced_prompt = None
        
        if enhanced_prompt:
            print(f"Using enhanced prompt for BFL")
            return enhanced_prompt
        else:
            print(f"Using original prompt for BFL")
            return original_prompt
    
    def stage_fetch_image(self):
        """Stage: Fetch original image from S3 - Optimized with caching"""
        print(f"STAGE: Fetching original image for edit {self.edit_id}")
        self.update_stage("fetching_original_image")
        
        # Check if we already have cached image bytes from prompt enhancement
        if hasattr(self, 'cached_image_bytes') and self.cached_image_bytes:
            print(f"Using cached image bytes (size: {len(self.cached_image_bytes)} bytes) - SKIPPING S3 DOWNLOAD")
            return self.cached_image_bytes
        
        # If not cached, download from S3
        edit = self.get_edit()
        image_url = edit.original_image_url
        print(f"Fetching image from: {image_url}")
        
        # Optimized HTTP request with faster timeout
        timeout = httpx.Timeout(10.0, connect=3.0)  # Even faster timeouts
        with httpx.Client(timeout=timeout) as client:
            response = client.get(image_url)
            response.raise_for_status()
            image_bytes = response.content
            
        print(f"Successfully fetched original image, size: {len(image_bytes)} bytes")
        return image_bytes
    
    def stage_process_with_ai(self, image_bytes: bytes, prompt: str):
        """Stage: Process image with BFL AI - NO RETRIES"""
        print(f"STAGE: Processing with AI for edit {self.edit_id}")
        self.update_stage("connecting_to_ai_service")
        
        print(f"Calling BFL API for edit {self.edit_id}")
        self.update_stage("processing_with_ai")
        
        try:
            edited_image_bytes = asyncio.run(flux_api.edit_image_with_flux(image_bytes, prompt))
            print(f"BFL API returned edited image, size: {len(edited_image_bytes)} bytes")
            return edited_image_bytes
        except Exception as e:
            print(f"BFL API ERROR: {str(e)} - NO RETRIES")
            raise e
    
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


def retry_stage_with_backoff(stage_func, stage_name: str, max_retries: int = 3, base_delay: int = 10, allow_retries: bool = True):
    """
    Optimized retry with faster base delays and exponential backoff.
    Only retries the failed stage, not the entire process.
    Some stages (like AI processing) don't retry on failure.
    """
    if not allow_retries:
        # No retries allowed - fail immediately on any error
        try:
            print(f"STAGE ATTEMPT: {stage_name} (no retries allowed)")
            return stage_func()
        except Exception as e:
            print(f"STAGE FAILED: {stage_name} - {str(e)} (no retries)")
            raise e
    
    # Optimized retry logic with faster delays
    for attempt in range(max_retries):
        try:
            print(f"STAGE ATTEMPT: {stage_name} (attempt {attempt + 1}/{max_retries})")
            return stage_func()
        except BFLServiceError as e:
            if not getattr(e, 'is_temporary', False) or attempt == max_retries - 1:
                print(f"STAGE FAILED: {stage_name} - {str(e)}")
                raise e
            
            # Faster exponential backoff: 10s, 20s, 40s instead of 30s, 60s, 120s
            delay = base_delay * (2 ** attempt)
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
    tracker = None
    try:
        # Initialize
        db = database.get_db_with_retry(max_retries=3)
        processor = StageProcessor(edit_id, db)
        edit = processor.get_edit()
        
        if not edit:
            print(f"TASK ERROR: Edit {edit_id} not found in database")
            return

        tracker = PerformanceTracker(edit.id, edit.uuid)
        # Set start time to when the request was created for end-to-end measurement
        tracker.start_time = edit.created_at.replace(tzinfo=timezone.utc).timestamp()
        
        print(f"TASK PROCESSING: Edit {edit_id} with UUID {edit.uuid}")
        print(f"Original prompt: '{edit.prompt}'")
        print(f"Enhanced prompt: '{edit.enhanced_prompt}'")
        
        # Initialize processing - Update status immediately
        tracker.start_stage("initialization")
        crud.update_edit_status(db, edit_id, "processing")
        tracker.end_stage("initialization")
        
        # Stage 0: Enhance prompt (moved from API for instant response)
        tracker.start_stage("prompt_enhancement")
        prompt_to_use = processor.stage_enhance_prompt()
        tracker.end_stage("prompt_enhancement")
        
        # Continue with processing stages
        processor.update_stage("initializing_processing")
        processor.update_stage("preparing_image_data")
        
        print(f"Using prompt for BFL API: '{prompt_to_use}'")
        
        # Stage 1: Fetch image (with retries)
        tracker.start_stage("fetch_image")
        image_bytes = retry_stage_with_backoff(
            lambda: processor.stage_fetch_image(),
            "fetch_image",
            max_retries=2,  # Reduced retries for faster failure
            base_delay=5    # Faster initial delay
        )
        tracker.end_stage("fetch_image")
        
        # Stage 2: Process with AI (NO RETRIES - fail immediately on BFL/Gemini errors)
        tracker.start_stage("ai_processing")
        edited_image_bytes = retry_stage_with_backoff(
            lambda: processor.stage_process_with_ai(image_bytes, prompt_to_use),
            "process_with_ai",
            max_retries=1,
            base_delay=0,
            allow_retries=False
        )
        tracker.end_stage("ai_processing")
        
        # Stage 3: Upload result (with retries)
        tracker.start_stage("upload_result")
        edited_image_url = retry_stage_with_backoff(
            lambda: processor.stage_upload_result(edited_image_bytes),
            "upload_result",
            max_retries=2,  # Reduced retries for faster failure
            base_delay=5    # Faster initial delay
        )
        tracker.end_stage("upload_result")
        
        # Stage 4: Complete
        tracker.start_stage("finalization")
        processor.stage_complete(edited_image_url)
        tracker.end_stage("finalization")

        tracker.finish_tracking("completed")
        
    except Exception as e:
        print(f"TASK FAILED: Edit {edit_id} failed: {str(e)}")
        if db:
            try:
                crud.update_edit_status(db, edit_id, "failed")
                crud.update_edit_processing_stage(db, edit_id, "failed")
                print(f"STATUS UPDATED: Edit {edit_id} marked as failed")
            except Exception as update_error:
                print(f"CRITICAL ERROR: Could not update status for edit {edit_id}: {update_error}")
        
        if tracker:
            tracker.finish_tracking(f"failed_{type(e).__name__}")

        raise e
    
    finally:
        if db:
            db.close()