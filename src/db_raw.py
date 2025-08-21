"""
Raw psycopg database operations with connection pooling for maximum performance and reliability.
Eliminates prepared statement issues and reduces memory usage.
Unified database interface for both API and Celery operations.
"""
import os
import psycopg
from psycopg.pool import ConnectionPool
from typing import Optional, Dict, Any, List
from .logger import logger
import uuid
import threading

# Database configuration with error handling
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

DATABASE_SCHEMA = os.environ.get("DATABASE_SCHEMA", "public")

# Global connection pool - thread-safe
_connection_pool: Optional[ConnectionPool] = None
_pool_lock = threading.Lock()

def get_connection_pool():
    """Get or create the global connection pool (thread-safe)"""
    global _connection_pool
    
    if _connection_pool is None:
        with _pool_lock:
            if _connection_pool is None:  # Double-check locking
                logger.info(f"Initializing database connection pool for schema: {DATABASE_SCHEMA}")
                _connection_pool = ConnectionPool(
                    DATABASE_URL,
                    min_size=3,      # Minimum connections
                    max_size=8,      # Maximum connections (good for 3 concurrent workers)
                    timeout=10,      # Connection timeout
                    max_idle=300,    # Close idle connections after 5 minutes
                    kwargs={
                        "autocommit": True,
                        "options": f"-csearch_path={DATABASE_SCHEMA},public"
                    }
                )
                logger.info("Database connection pool initialized successfully")
    
    return _connection_pool

def get_connection():
    """Get a connection from the pool with proper schema setup"""
    pool = get_connection_pool()
    conn = pool.getconn()
    
    # Ensure proper schema is set (pool kwargs should handle this, but double-check)
    try:
        conn.execute(f"SET search_path TO {DATABASE_SCHEMA}, public")
    except Exception as e:
        logger.warning(f"Failed to set search_path: {e}")
    
    return conn

def return_connection(conn):
    """Return connection to pool"""
    pool = get_connection_pool()
    pool.putconn(conn)

def get_edit_by_id(edit_id: int) -> Optional[Dict[str, Any]]:
    """Get edit by ID - single database call using connection pool"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, uuid, prompt, enhanced_prompt, original_image_url, 
                       edited_image_url, status, processing_stage, created_at
                FROM edits WHERE id = %s
            """, (edit_id,))
            
            row = cur.fetchone()
            if not row:
                return None
                
            return {
                'id': row[0],
                'uuid': row[1], 
                'prompt': row[2],
                'enhanced_prompt': row[3],
                'original_image_url': row[4],
                'edited_image_url': row[5],
                'status': row[6],
                'processing_stage': row[7],
                'created_at': row[8]
            }
    finally:
        return_connection(conn)

def get_edit_by_uuid(edit_uuid: str) -> Optional[Dict[str, Any]]:
    """Get edit by UUID - single database call using connection pool"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, uuid, prompt, enhanced_prompt, original_image_url, 
                       edited_image_url, status, processing_stage, created_at
                FROM edits WHERE uuid = %s
            """, (edit_uuid,))
            
            row = cur.fetchone()
            if not row:
                return None
                
            return {
                'id': row[0],
                'uuid': row[1],
                'prompt': row[2], 
                'enhanced_prompt': row[3],
                'original_image_url': row[4],
                'edited_image_url': row[5],
                'status': row[6],
                'processing_stage': row[7],
                'created_at': row[8]
            }
    finally:
        return_connection(conn)

def create_edit(prompt: str, original_image_url: str, enhanced_prompt: str = None, parent_edit_uuid: str = None) -> Dict[str, Any]:
    """Create new edit - single database call with optional chain creation"""
    edit_uuid = str(uuid.uuid4())
    
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Insert edit with created_at
            cur.execute("""
                INSERT INTO edits (uuid, prompt, enhanced_prompt, original_image_url, status, processing_stage, created_at)
                VALUES (%s, %s, %s, %s, 'pending', 'pending', NOW())
                RETURNING id, uuid, prompt, enhanced_prompt, original_image_url, 
                         edited_image_url, status, processing_stage, created_at
            """, (edit_uuid, prompt, enhanced_prompt, original_image_url))
            
            row = cur.fetchone()
            edit_data = {
                'id': row[0],
                'uuid': row[1],
                'prompt': row[2],
                'enhanced_prompt': row[3], 
                'original_image_url': row[4],
                'edited_image_url': row[5],
                'status': row[6],
                'processing_stage': row[7],
                'created_at': row[8]
            }
            
            # Create chain relationship if parent exists
            if parent_edit_uuid:
                # Get parent chain position
                cur.execute("""
                    SELECT COALESCE(MAX(chain_position), 0) + 1
                    FROM edit_chains ec
                    JOIN edits e ON ec.edit_uuid = e.uuid
                    WHERE e.uuid = %s OR ec.parent_edit_uuid = %s
                """, (parent_edit_uuid, parent_edit_uuid))
                
                chain_position = cur.fetchone()[0]
                
                # Insert chain relationship
                cur.execute("""
                    INSERT INTO edit_chains (edit_uuid, parent_edit_uuid, chain_position)
                    VALUES (%s, %s, %s)
                """, (edit_uuid, parent_edit_uuid, chain_position))
            
            return edit_data
    finally:
        return_connection(conn)

def update_edit_status(edit_id: int, status: str) -> bool:
    """Update edit status - single database call"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE edits SET status = %s WHERE id = %s
            """, (status, edit_id))
            
            return cur.rowcount > 0
    finally:
        return_connection(conn)

def update_edit_processing_stage(edit_id: int, processing_stage: str) -> bool:
    """Update processing stage - single database call"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE edits SET processing_stage = %s WHERE id = %s
            """, (processing_stage, edit_id))
            
            return cur.rowcount > 0
    finally:
        return_connection(conn)

def update_edit_enhanced_prompt(edit_id: int, enhanced_prompt: str) -> bool:
    """Update enhanced prompt - single database call"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE edits SET enhanced_prompt = %s WHERE id = %s
            """, (enhanced_prompt, edit_id))
            
            return cur.rowcount > 0
    finally:
        return_connection(conn)

def update_edit_with_result(edit_id: int, status: str, edited_image_url: str) -> bool:
    """Update edit with final result - single database call"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE edits 
                SET status = %s, edited_image_url = %s, processing_stage = 'completed'
                WHERE id = %s
            """, (status, edited_image_url, edit_id))
            
            return cur.rowcount > 0
    finally:
        return_connection(conn)

def get_edit_chain_history(edit_uuid: str) -> List[Dict[str, Any]]:
    """Get complete edit chain history - single optimized query"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                WITH RECURSIVE edit_chain AS (
                    -- Base case: find the root of the chain
                    SELECT e.id, e.uuid, e.prompt, e.enhanced_prompt, e.original_image_url,
                           e.edited_image_url, e.status, e.processing_stage, e.created_at,
                           COALESCE(ec.chain_position, 1) as chain_position,
                           1 as level
                    FROM edits e
                    LEFT JOIN edit_chains ec ON e.uuid = ec.edit_uuid
                    WHERE e.uuid = %s
                    
                    UNION ALL
                    
                    -- Recursive case: find children
                    SELECT e.id, e.uuid, e.prompt, e.enhanced_prompt, e.original_image_url,
                           e.edited_image_url, e.status, e.processing_stage, e.created_at,
                           ec.chain_position,
                           parent.level + 1
                    FROM edits e
                    JOIN edit_chains ec ON e.uuid = ec.edit_uuid
                    JOIN edit_chain parent ON ec.parent_edit_uuid = parent.uuid
                    WHERE parent.level < 10  -- Prevent infinite recursion
                )
                SELECT id, uuid, prompt, enhanced_prompt, original_image_url,
                       edited_image_url, status, processing_stage, created_at, chain_position
                FROM edit_chain
                ORDER BY chain_position
            """, (edit_uuid,))
            
            rows = cur.fetchall()
            return [
                {
                    'id': row[0],
                    'uuid': row[1],
                    'prompt': row[2],
                    'enhanced_prompt': row[3],
                    'original_image_url': row[4],
                    'edited_image_url': row[5],
                    'status': row[6],
                    'processing_stage': row[7],
                    'created_at': row[8],
                    'chain_position': row[9]
                }
                for row in rows
            ]
    finally:
        return_connection(conn)

def create_edit_feedback(edit_uuid: str, rating: int, feedback_text: str = None, user_ip: str = None) -> bool:
    """Create edit feedback - single database call"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            try:
                cur.execute("""
                    INSERT INTO edit_feedback (edit_uuid, rating, feedback_text, user_ip)
                    VALUES (%s, %s, %s, %s)
                """, (edit_uuid, rating, feedback_text, user_ip))
                
                return True
            except psycopg.IntegrityError:
                # Feedback already exists for this edit
                return False
    finally:
        return_connection(conn)

def get_edit_feedback(edit_uuid: str) -> Optional[Dict[str, Any]]:
    """Get edit feedback - single database call"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT edit_uuid, rating, feedback_text, user_ip, created_at
                FROM edit_feedback WHERE edit_uuid = %s
            """, (edit_uuid,))
            
            row = cur.fetchone()
            if not row:
                return None
                
            return {
                'edit_uuid': row[0],
                'rating': row[1],
                'feedback_text': row[2],
                'user_ip': row[3],
                'created_at': row[4]
            }
    finally:
        return_connection(conn)

logger.info("Raw psycopg database module initialized with prepare_threshold=0")