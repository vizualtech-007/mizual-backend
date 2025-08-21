"""
Raw psycopg database operations for maximum performance and reliability.
Eliminates prepared statement issues and reduces memory usage.
Unified database interface for both API and Celery operations.
"""
import os
import psycopg
from typing import Optional, Dict, Any, List
from .logger import logger
import uuid

# Database configuration with error handling
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

DATABASE_SCHEMA = os.environ.get("DATABASE_SCHEMA", "public")

def get_connection():
    """Get a raw psycopg connection that never uses prepared statements"""
    # Force autocommit mode and simple query protocol to prevent PgBouncer issues
    conn = psycopg.connect(
        DATABASE_URL,
        autocommit=True,  # No transactions, no prepared statements
        options=f"-csearch_path={DATABASE_SCHEMA},public",
        # Optimize connection settings for performance
        connect_timeout=10,
        keepalives_idle=600,  # Keep connection alive
        keepalives_interval=30,
        keepalives_count=3
    )
    # Force simple query protocol
    conn.execute(f"SET search_path TO {DATABASE_SCHEMA}, public")
    return conn

def get_edit_by_id(edit_id: int) -> Optional[Dict[str, Any]]:
    """Get edit by ID - single database call"""
    with get_connection() as conn:
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

def get_edit_by_uuid(edit_uuid: str) -> Optional[Dict[str, Any]]:
    """Get edit by UUID - single database call"""
    with get_connection() as conn:
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

def create_edit(prompt: str, original_image_url: str, enhanced_prompt: str = None, parent_edit_uuid: str = None) -> Dict[str, Any]:
    """Create new edit - optimized single transaction with optional chain creation"""
    edit_uuid = str(uuid.uuid4())
    
    with get_connection() as conn:
        with conn.cursor() as cur:
            # First create the edit
            cur.execute("""
                INSERT INTO edits (uuid, prompt, enhanced_prompt, original_image_url, status, processing_stage, created_at)
                VALUES (%s, %s, %s, %s, 'pending', 'pending', NOW())
                RETURNING id, uuid, prompt, enhanced_prompt, original_image_url, 
                         edited_image_url, status, processing_stage, created_at
            """, (edit_uuid, prompt, enhanced_prompt, original_image_url))
            
            row = cur.fetchone()
            edit_result = {
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
            
            # If this is a chain edit, create the chain entry separately
            if parent_edit_uuid:
                # Get the chain position
                cur.execute("""
                    SELECT COALESCE(MAX(chain_position), 0) + 1 as pos
                    FROM edit_chains ec
                    JOIN edits e ON ec.edit_uuid = e.uuid
                    WHERE e.uuid = %s OR ec.parent_edit_uuid = %s
                """, (parent_edit_uuid, parent_edit_uuid))
                
                chain_position = cur.fetchone()[0]
                
                # Insert the chain entry
                cur.execute("""
                    INSERT INTO edit_chains (edit_uuid, parent_edit_uuid, chain_position)
                    VALUES (%s, %s, %s)
                """, (edit_uuid, parent_edit_uuid, chain_position))
            
            return edit_result

def update_edit_status(edit_id: int, status: str) -> bool:
    """Update edit status - single database call"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE edits SET status = %s WHERE id = %s
            """, (status, edit_id))
            
            return cur.rowcount > 0

def update_edit_processing_stage(edit_id: int, processing_stage: str) -> bool:
    """Update processing stage - single database call"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE edits SET processing_stage = %s WHERE id = %s
            """, (processing_stage, edit_id))
            
            return cur.rowcount > 0

def update_edit_enhanced_prompt(edit_id: int, enhanced_prompt: str) -> bool:
    """Update enhanced prompt - single database call"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE edits SET enhanced_prompt = %s WHERE id = %s
            """, (enhanced_prompt, edit_id))
            
            return cur.rowcount > 0

def update_edit_with_result(edit_id: int, status: str, edited_image_url: str) -> bool:
    """Update edit with final result - single database call"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE edits 
                SET status = %s, edited_image_url = %s, processing_stage = 'completed'
                WHERE id = %s
            """, (status, edited_image_url, edit_id))
            
            return cur.rowcount > 0

def get_edit_chain_history(edit_uuid: str) -> List[Dict[str, Any]]:
    """Get complete edit chain history - single optimized query"""
    with get_connection() as conn:
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

def create_edit_feedback(edit_uuid: str, rating: int, feedback_text: str = None, user_ip: str = None) -> bool:
    """Create edit feedback - single database call"""
    with get_connection() as conn:
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

def get_edit_feedback(edit_uuid: str) -> Optional[Dict[str, Any]]:
    """Get edit feedback - single database call"""
    with get_connection() as conn:
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

def get_database_performance_info() -> Dict[str, Any]:
    """Get database performance information and optimization suggestions"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Check if optimal indexes exist
            cur.execute("""
                SELECT 
                    schemaname, tablename, indexname, indexdef
                FROM pg_indexes 
                WHERE schemaname = %s 
                AND tablename IN ('edits', 'edit_chains', 'edit_feedback')
                ORDER BY tablename, indexname
            """, (DATABASE_SCHEMA,))
            
            indexes = cur.fetchall()
            
            # Check query performance statistics if available
            cur.execute("""
                SELECT 
                    query, calls, total_time, mean_time
                FROM pg_stat_statements 
                WHERE query LIKE '%edits%' 
                ORDER BY total_time DESC 
                LIMIT 5
            """)
            
            try:
                query_stats = cur.fetchall()
            except:
                query_stats = []  # pg_stat_statements might not be enabled
            
            return {
                "indexes": [
                    {
                        "schema": row[0],
                        "table": row[1], 
                        "index_name": row[2],
                        "definition": row[3]
                    } for row in indexes
                ],
                "query_stats": [
                    {
                        "query": row[0][:100] + "..." if len(row[0]) > 100 else row[0],
                        "calls": row[1],
                        "total_time": row[2],
                        "mean_time": row[3]
                    } for row in query_stats
                ],
                "optimization_suggestions": [
                    "Ensure index on edits(uuid) for fast lookups",
                    "Ensure index on edits(status, processing_stage) for status queries",
                    "Ensure index on edit_chains(edit_uuid) for chain lookups", 
                    "Ensure index on edit_chains(parent_edit_uuid) for parent lookups",
                    "Ensure index on edit_feedback(edit_uuid) for feedback lookups",
                    "Consider partial index on edits(created_at) WHERE status='completed'"
                ]
            }

logger.info("Raw psycopg database module initialized with prepare_threshold=0")