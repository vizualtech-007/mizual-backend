"""
Performance tracking system for image editing pipeline.
Tracks timing, memory usage, and resource utilization for each stage and sub-operation.
Enhanced with detailed profiling for optimization analysis.
"""

import time
import os
import psutil
from typing import Dict, Optional, List
from datetime import datetime, timezone
from .logger import logger


class PerformanceTracker:
    def __init__(self, edit_id: int, edit_uuid: str):
        self.edit_id = edit_id
        self.edit_uuid = edit_uuid
        self.start_time = time.time()
        self.stage_times: Dict[str, Dict[str, float]] = {}
        self.current_stage: Optional[str] = None
        self.current_stage_start: Optional[float] = None
        
        # Memory and resource tracking
        self.process = psutil.Process()
        self.system_start_memory = psutil.virtual_memory().percent
        self.process_start_memory = self.process.memory_info().rss / (1024 * 1024)  # MB
        self.peak_memory_usage = self.process_start_memory
        
        # Sub-operation tracking
        self.sub_operations: Dict[str, List[Dict]] = {}
        self._current_sub_op = None
        self._stage_start_memory = self.process_start_memory
        
        # Log the start of tracking with system info
        logger.info(f"PERFORMANCE TRACKER STARTED: edit_id={edit_id}, uuid={edit_uuid}, timestamp={datetime.now(timezone.utc).isoformat()}")
        logger.info(f"SYSTEM BASELINE: system_memory={self.system_start_memory:.1f}%, process_memory={self.process_start_memory:.1f}MB, cpu_count={psutil.cpu_count()}")
    
    def start_stage(self, stage_name: str):
        """Start timing a new stage with memory tracking"""
        # End previous stage if exists
        if self.current_stage and self.current_stage_start:
            self.end_stage(self.current_stage)
        
        # Start new stage
        self.current_stage = stage_name
        self.current_stage_start = time.time()
        
        # Capture memory state at stage start
        current_memory = self.process.memory_info().rss / (1024 * 1024)  # MB
        system_memory = psutil.virtual_memory().percent
        cpu_percent = self.process.cpu_percent()
        
        # Store stage start memory for delta calculation
        self._stage_start_memory = current_memory
        
        elapsed_total = self.current_stage_start - self.start_time
        logger.info(f"STAGE STARTED: edit_id={self.edit_id}, stage={stage_name}, total_elapsed={elapsed_total:.3f}s, memory={current_memory:.1f}MB, system_mem={system_memory:.1f}%, cpu={cpu_percent:.1f}%")
        
        # Initialize sub-operations list for this stage
        self.sub_operations[stage_name] = []
    
    def end_stage(self, stage_name: str):
        """End timing for a stage with memory tracking"""
        if self.current_stage != stage_name:
            logger.warning(f"WARNING: Stage mismatch. Expected {self.current_stage}, got {stage_name}")
            return
        
        if not self.current_stage_start:
            logger.warning(f"WARNING: No start time for stage {stage_name}")
            return
        
        end_time = time.time()
        stage_duration = end_time - self.current_stage_start
        total_elapsed = end_time - self.start_time
        
        # Capture memory state at stage end
        end_memory = self.process.memory_info().rss / (1024 * 1024)  # MB
        system_memory = psutil.virtual_memory().percent
        cpu_percent = self.process.cpu_percent()
        
        # Update peak memory if needed
        if end_memory > self.peak_memory_usage:
            self.peak_memory_usage = end_memory
        
        # Store stage timing with memory info
        self.stage_times[stage_name] = {
            'start_time': self.current_stage_start,
            'end_time': end_time,
            'duration': stage_duration,
            'total_elapsed_at_end': total_elapsed,
            'memory_start_mb': self._stage_start_memory,
            'memory_end_mb': end_memory,
            'memory_delta_mb': end_memory - self._stage_start_memory,
            'system_memory_percent': system_memory,
            'cpu_percent': cpu_percent,
            'sub_operations': self.sub_operations.get(stage_name, [])
        }
        
        logger.info(f"STAGE COMPLETED: edit_id={self.edit_id}, stage={stage_name}, duration={stage_duration:.3f}s, total_elapsed={total_elapsed:.3f}s, memory_delta={self.stage_times[stage_name]['memory_delta_mb']:+.1f}MB, end_memory={end_memory:.1f}MB")
        
        # Clear current stage
        self.current_stage = None
        self.current_stage_start = None
    
    def start_sub_operation(self, operation_name: str, details: str = ""):
        """Start timing a sub-operation within the current stage"""
        if not self.current_stage:
            logger.warning(f"WARNING: No active stage for sub-operation {operation_name}")
            return
        
        current_memory = self.process.memory_info().rss / (1024 * 1024)
        sub_op = {
            'name': operation_name,
            'start_time': time.time(),
            'details': details,
            'memory_start_mb': current_memory
        }
        
        # Store reference for completion
        self._current_sub_op = sub_op
        
        elapsed = time.time() - self.start_time
        logger.info(f"SUB_OP STARTED: edit_id={self.edit_id}, stage={self.current_stage}, operation={operation_name}, total_elapsed={elapsed:.3f}s, memory={current_memory:.1f}MB")
    
    def end_sub_operation(self, operation_name: str = None):
        """End timing for the current sub-operation"""
        if not hasattr(self, '_current_sub_op') or not self._current_sub_op:
            logger.warning(f"WARNING: No active sub-operation to end")
            return
        
        end_time = time.time()
        current_memory = self.process.memory_info().rss / (1024 * 1024)
        
        # Complete the sub-operation
        sub_op = self._current_sub_op
        sub_op['end_time'] = end_time
        sub_op['duration'] = end_time - sub_op['start_time']
        sub_op['memory_end_mb'] = current_memory
        sub_op['memory_delta_mb'] = current_memory - sub_op['memory_start_mb']
        
        # Add to current stage's sub-operations
        if self.current_stage and self.current_stage in self.sub_operations:
            self.sub_operations[self.current_stage].append(sub_op)
        
        elapsed = time.time() - self.start_time
        logger.info(f"SUB_OP COMPLETED: edit_id={self.edit_id}, stage={self.current_stage}, operation={sub_op['name']}, duration={sub_op['duration']:.3f}s, total_elapsed={elapsed:.3f}s, memory_delta={sub_op['memory_delta_mb']:+.1f}MB")
        
        # Clear current sub-operation
        self._current_sub_op = None
    
    def log_milestone(self, milestone: str, additional_info: str = ""):
        """Log a milestone without starting/ending stages"""
        elapsed = time.time() - self.start_time
        current_memory = self.process.memory_info().rss / (1024 * 1024)
        info_str = f", {additional_info}" if additional_info else ""
        logger.info(f"MILESTONE: edit_id={self.edit_id}, milestone={milestone}, total_elapsed={elapsed:.3f}s, memory={current_memory:.1f}MB{info_str}")
    
    def finish_tracking(self, final_status: str):
        """Finish tracking and log comprehensive summary"""
        # End current stage if exists
        if self.current_stage and self.current_stage_start:
            self.end_stage(self.current_stage)
        
        # End any active sub-operation
        if hasattr(self, '_current_sub_op') and self._current_sub_op:
            self.end_sub_operation()
        
        total_time = time.time() - self.start_time
        final_memory = self.process.memory_info().rss / (1024 * 1024)
        final_system_memory = psutil.virtual_memory().percent
        
        logger.info(f"PERFORMANCE SUMMARY START: edit_id={self.edit_id}, uuid={self.edit_uuid}")
        logger.info(f"TOTAL TIME: {total_time:.3f}s, FINAL STATUS: {final_status}")
        logger.info(f"MEMORY SUMMARY: start={self.process_start_memory:.1f}MB, peak={self.peak_memory_usage:.1f}MB, final={final_memory:.1f}MB, delta={final_memory - self.process_start_memory:+.1f}MB")
        
        # Generate detailed table summary
        self._log_detailed_table_summary(total_time)
        
        # Calculate untracked time
        tracked_time = sum(timing['duration'] for timing in self.stage_times.values())
        untracked_time = total_time - tracked_time
        untracked_percentage = (untracked_time / total_time) * 100
        
        logger.info(f"UNTRACKED TIME: {untracked_time:.3f}s ({untracked_percentage:.1f}%)")
        logger.info(f"PERFORMANCE SUMMARY END: edit_id={self.edit_id}")
        
        return {
            'edit_id': self.edit_id,
            'edit_uuid': self.edit_uuid,
            'total_time': total_time,
            'final_status': final_status,
            'stage_times': self.stage_times,
            'untracked_time': untracked_time,
            'memory_summary': {
                'start_mb': self.process_start_memory,
                'peak_mb': self.peak_memory_usage,
                'final_mb': final_memory,
                'delta_mb': final_memory - self.process_start_memory
            },
            'system_memory_final_percent': final_system_memory
        }
    
    def _log_detailed_table_summary(self, total_time: float):
        """Log a detailed table format summary"""
        logger.info("="*120)
        logger.info("DETAILED PERFORMANCE TABLE SUMMARY")
        logger.info("="*120)
        
        # Header
        header = f"{'Stage':<20} {'Duration':<10} {'%':<6} {'Mem Start':<10} {'Mem End':<10} {'Mem Δ':<8} {'CPU %':<6} {'Sub-Ops':<6}"
        logger.info(header)
        logger.info("-"*120)
        
        # Stage rows
        for stage_name, timing in self.stage_times.items():
            duration = timing['duration']
            percentage = (duration / total_time) * 100
            mem_start = timing.get('memory_start_mb', 0)
            mem_end = timing.get('memory_end_mb', 0)
            mem_delta = timing.get('memory_delta_mb', 0)
            cpu_percent = timing.get('cpu_percent', 0)
            sub_ops_count = len(timing.get('sub_operations', []))
            
            row = f"{stage_name:<20} {duration:<10.3f} {percentage:<6.1f} {mem_start:<10.1f} {mem_end:<10.1f} {mem_delta:<+8.1f} {cpu_percent:<6.1f} {sub_ops_count:<6}"
            logger.info(row)
            
            # Sub-operations details
            for sub_op in timing.get('sub_operations', []):
                sub_duration = sub_op.get('duration', 0)
                sub_mem_delta = sub_op.get('memory_delta_mb', 0)
                sub_details = sub_op.get('details', '')
                sub_row = f"  └─ {sub_op['name']:<16} {sub_duration:<10.3f} {'':<6} {'':<10} {'':<10} {sub_mem_delta:<+8.1f} {'':<6} {sub_details}"
                logger.info(sub_row)
        
        logger.info("-"*120)
        
        # Summary row
        total_tracked = sum(timing['duration'] for timing in self.stage_times.values())
        total_mem_delta = self.peak_memory_usage - self.process_start_memory
        summary_row = f"{'TOTAL':<20} {total_tracked:<10.3f} {'':<6} {self.process_start_memory:<10.1f} {self.peak_memory_usage:<10.1f} {total_mem_delta:<+8.1f} {'':<6} {'':<6}"
        logger.info(summary_row)
        logger.info("="*120)


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


# Convenience functions for sub-operation tracking
def start_sub_operation(edit_id: int, operation_name: str, details: str = ""):
    """Start a sub-operation for the given edit"""
    tracker = get_performance_tracker(edit_id)
    if tracker:
        tracker.start_sub_operation(operation_name, details)


def end_sub_operation(edit_id: int, operation_name: str = None):
    """End a sub-operation for the given edit"""
    tracker = get_performance_tracker(edit_id)
    if tracker:
        tracker.end_sub_operation(operation_name)