"""
Async operations for improved performance.
Non-blocking operations for S3, database, and external APIs.
"""

import asyncio
import httpx
from typing import Optional, Callable, Any
import time


async def async_s3_upload(upload_func: Callable, *args, **kwargs) -> str:
    """Async wrapper for S3 upload operations"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, upload_func, *args, **kwargs)


async def async_database_operation(db_func: Callable, *args, **kwargs) -> Any:
    """Async wrapper for database operations"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, db_func, *args, **kwargs)


async def async_http_request(url: str, method: str = "GET", **kwargs) -> httpx.Response:
    """Async HTTP request with optimized settings"""
    timeout = httpx.Timeout(10.0, connect=5.0)  # Faster timeouts
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        if method.upper() == "GET":
            return await client.get(url, **kwargs)
        elif method.upper() == "POST":
            return await client.post(url, **kwargs)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")


class PerformanceOptimizer:
    """Performance optimization utilities"""
    
    @staticmethod
    async def parallel_operations(*operations):
        """Execute multiple async operations in parallel"""
        return await asyncio.gather(*operations, return_exceptions=True)
    
    @staticmethod
    def time_operation(operation_name: str):
        """Decorator to time operations"""
        def decorator(func):
            async def wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = await func(*args, **kwargs)
                    duration = time.time() - start_time
                    print(f"PERFORMANCE: {operation_name} completed in {duration:.3f}s")
                    return result
                except Exception as e:
                    duration = time.time() - start_time
                    print(f"PERFORMANCE: {operation_name} failed in {duration:.3f}s - {str(e)}")
                    raise
            return wrapper
        return decorator


# Optimized retry logic with exponential backoff
async def async_retry_operation(
    operation: Callable,
    max_retries: int = 3,
    base_delay: float = 0.1,
    max_delay: float = 2.0,
    operation_name: str = "operation"
) -> Any:
    """Async retry with exponential backoff"""
    
    for attempt in range(max_retries):
        try:
            return await operation()
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"ASYNC RETRY: {operation_name} failed after {max_retries} attempts")
                raise e
            
            delay = min(base_delay * (2 ** attempt), max_delay)
            print(f"ASYNC RETRY: {operation_name} attempt {attempt + 1} failed, retrying in {delay:.3f}s")
            await asyncio.sleep(delay)
    
    raise Exception(f"Async retry failed for {operation_name}")