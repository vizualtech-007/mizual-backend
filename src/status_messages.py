"""
User-friendly status messages for progress indicator
"""

def get_status_message(status: str, processing_stage: str = None) -> dict:
    """
    Convert technical status/stage to user-friendly messages
    Returns dict with message and progress info
    """
    
    # Handle failed status first
    if status == "failed":
        return {
            "message": "Edit failed. Please try again.",
            "stage": "failed",
            "progress_percent": 0,
            "is_complete": True,
            "is_error": True
        }
    
    # Handle completed status
    if status == "completed":
        return {
            "message": "Edit completed successfully!",
            "stage": "completed", 
            "progress_percent": 100,
            "is_complete": True,
            "is_error": False
        }
    
    # Handle processing stages
    stage_messages = {
        "pending": {
            "message": "Your edit is queued...",
            "stage": "pending",
            "progress_percent": 10,
            "is_complete": False,
            "is_error": False
        },
        "enhancing_prompt": {
            "message": "Enhancing your prompt with AI...",
            "stage": "enhancing_prompt",
            "progress_percent": 25,
            "is_complete": False,
            "is_error": False
        },
        "processing_image": {
            "message": "Processing your edit...",
            "stage": "processing_image", 
            "progress_percent": 60,
            "is_complete": False,
            "is_error": False
        },
        "uploading_result": {
            "message": "Finalizing your edit...",
            "stage": "uploading_result",
            "progress_percent": 90,
            "is_complete": False,
            "is_error": False
        }
    }
    
    # Use processing_stage if available, otherwise fall back to status
    stage_key = processing_stage or status
    
    # Return stage-specific message or default
    return stage_messages.get(stage_key, {
        "message": "Processing your edit...",
        "stage": stage_key or "processing",
        "progress_percent": 50,
        "is_complete": False,
        "is_error": False
    })

def get_estimated_time_remaining(processing_stage: str) -> str:
    """
    Get estimated time remaining based on current stage
    """
    time_estimates = {
        "pending": "2-3 minutes",
        "enhancing_prompt": "1-2 minutes", 
        "processing_image": "30-60 seconds",
        "uploading_result": "10-20 seconds",
        "completed": "0 seconds",
        "failed": "N/A"
    }
    
    return time_estimates.get(processing_stage, "1-2 minutes")