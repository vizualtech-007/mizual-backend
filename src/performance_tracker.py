"""
Performance tracking system for image editing pipeline.
Tracks timing for each stage and overall process duration.
"""

import time
from typing import Dict, Optional
from datetime import datetime, timezone


class PerformanceTracker:
    def __init__(self, edit_id: int, edit_uuid: str):
        self.edit_id = edit_id
        self.edit_uuid = edit_uuid
        self.start_time = time.time()
        self.stage_times: Dict[str, Dict[str, float]] = {}
        self.current_stage: Optional[str] = None
        self.current_stage_start: Optional[float] = None
        
        # Log the start of tracking
        print(f"PERFORMANCE TRACKER STARTED: edit_id={edit_id}, uuid={edit_uuid}, timestamp={datetime.now(timezone.utc).isoformat()}")
    
    def start_stage(self, stage_name: str):
        """Start timing a new stage"""
        # End previous stage if exists
        if self.current_stage and self.current_stage_start:
            self.end_stage(self.current_stage)
        
        # Start new stage
        self.current_stage = stage_name
        self.current_stage_start = time.time()
        
        elapsed_total = self.current_stage_start - self.start_time
        print(f"STAGE STARTED: edit_id={self.edit_id}, stage={stage_name}, total_elapsed={elapsed_total:.3f}s")
    
    def end_stage(self, stage_name: str):
        """End timing for a stage"""
        if self.current_stage != stage_name:
            print(f"WARNING: Stage mismatch. Expected {self.current_stage}, got {stage_name}")
            return
        
        if not self.current_stage_start:
            print(f"WARNING: No start time for stage {stage_name}")
            return
        
        end_time = time.time()
        stage_duration = end_time - self.current_stage_start
        total_elapsed = end_time - self.start_time
        
        # Store stage timing
        self.stage_times[stage_name] = {
            'start_time': self.current_stage_start,
            'end_time': end_time,
            'duration': stage_duration,
            'total_elapsed_at_end': total_elapsed
        }
        
        print(f"STAGE COMPLETED: edit_id={self.edit_id}, stage={stage_name}, duration={stage_duration:.3f}s, total_elapsed={total_elapsed:.3f}s")
        
        # Clear current stage
        self.current_stage = None
        self.current_stage_start = None
    
    def log_milestone(self, milestone: str, additional_info: str = ""):
        """Log a milestone without starting/ending stages"""
        elapsed = time.time() - self.start_time
        info_str = f", {additional_info}" if additional_info else ""
        print(f"MILESTONE: edit_id={self.edit_id}, milestone={milestone}, total_elapsed={elapsed:.3f}s{info_str}")
    
    def finish_tracking(self, final_status: str):
        """Finish tracking and log final summary"""
        # End current stage if exists
        if self.current_stage and self.current_stage_start:
            self.end_stage(self.current_stage)
        
        total_time = time.time() - self.start_time
        
        print(f"PERFORMANCE SUMMARY START: edit_id={self.edit_id}, uuid={self.edit_uuid}")
        print(f"TOTAL TIME: {total_time:.3f}s, FINAL STATUS: {final_status}")
        
        # Log each stage duration
        for stage_name, timing in self.stage_times.items():
            duration = timing['duration']
            percentage = (duration / total_time) * 100
            print(f"STAGE TIMING: {stage_name}={duration:.3f}s ({percentage:.1f}%)")
        
        # Calculate untracked time
        tracked_time = sum(timing['duration'] for timing in self.stage_times.values())
        untracked_time = total_time - tracked_time
        untracked_percentage = (untracked_time / total_time) * 100
        
        print(f"UNTRACKED TIME: {untracked_time:.3f}s ({untracked_percentage:.1f}%)")
        print(f"PERFORMANCE SUMMARY END: edit_id={self.edit_id}")
        
        return {
            'edit_id': self.edit_id,
            'edit_uuid': self.edit_uuid,
            'total_time': total_time,
            'final_status': final_status,
            'stage_times': self.stage_times,
            'untracked_time': untracked_time
        }


# Global tracker storage (in production, consider using Redis or database)
_active_trackers: Dict[int, PerformanceTracker] = {}


def start_performance_tracking(edit_id: int, edit_uuid: str) -> PerformanceTracker:
    """Start performance tracking for an edit"""
    tracker = PerformanceTracker(edit_id, edit_uuid)
    _active_trackers[edit_id] = tracker
    return tracker


def get_performance_tracker(edit_id: int) -> Optional[PerformanceTracker]:
    """Get existing performance tracker"""
    return _active_trackers.get(edit_id)


def finish_performance_tracking(edit_id: int, final_status: str) -> Optional[Dict]:
    """Finish and remove performance tracker"""
    tracker = _active_trackers.pop(edit_id, None)
    if tracker:
        return tracker.finish_tracking(final_status)
    return None