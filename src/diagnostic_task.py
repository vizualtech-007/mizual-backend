"""
Diagnostic task to identify why Celery tasks aren't executing
"""

from celery import Celery
import os

# Create minimal Celery instance
redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
celery_app = Celery('diagnostic', broker=redis_url, backend=redis_url)

@celery_app.task(name='diagnostic.test_task')
def test_task(test_id: int):
    """Minimal test task to verify Celery execution"""
    print(f"DIAGNOSTIC TASK STARTED: test_id={test_id}")
    print(f"DIAGNOSTIC: Task is executing successfully!")
    return f"Task {test_id} completed"

@celery_app.task(name='diagnostic.test_imports')
def test_imports():
    """Test all imports that might be causing issues"""
    print("DIAGNOSTIC: Testing imports...")
    
    try:
        from . import database
        print("✅ database import OK")
    except Exception as e:
        print(f"❌ database import FAILED: {e}")
    
    try:
        from . import crud
        print("✅ crud import OK")
    except Exception as e:
        print(f"❌ crud import FAILED: {e}")
    
    try:
        from .performance_tracker import get_performance_tracker
        print("✅ performance_tracker import OK")
    except Exception as e:
        print(f"❌ performance_tracker import FAILED: {e}")
    
    try:
        from .task_stages import process_edit_with_stage_retries
        print("✅ task_stages import OK")
    except Exception as e:
        print(f"❌ task_stages import FAILED: {e}")
        print(f"❌ DETAILED ERROR: {repr(e)}")
    
    print("DIAGNOSTIC: Import test completed")
    return "Import test done"