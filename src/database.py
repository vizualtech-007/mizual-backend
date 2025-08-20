from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
import os

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://user:password@localhost/db")

# Convert postgresql:// to postgresql+psycopg:// to use psycopg driver instead of psycopg2
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
ENVIRONMENT = os.environ.get("ENVIRONMENT", "production")

# Add schema to connection based on environment
schema_name = "preview" if ENVIRONMENT == "preview" else "public"
connect_args = {
    "sslmode": "require",
    "options": f"-csearch_path={schema_name},public"
}

# Optimized connection pool configuration for performance
engine = create_engine(
    DATABASE_URL, 
    connect_args=connect_args,
    poolclass=QueuePool,
    pool_size=10,        # Increased pool size
    max_overflow=20,     # Increased overflow
    pool_pre_ping=True,  # Validates connections before use
    pool_recycle=1800,   # Faster recycle (30 minutes)
    pool_timeout=10,     # Faster timeout
    echo=False,
    # Disable prepared statement caching to fix PgBouncer compatibility
    execution_options={"prepared_statement_cache_size": 0}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Schema is now set via connect_args in create_engine
# No need for explicit schema setting per session

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_db_with_retry(max_retries=3):
    """Get database connection with retry logic for tasks"""
    for attempt in range(max_retries):
        db = None
        try:
            db = SessionLocal()
            # Test the connection with proper SQLAlchemy text() wrapper
            db.execute(text("SELECT 1"))
            return db
        except Exception as e:
            if db:
                db.close()
            if attempt == max_retries - 1:
                raise e
            from src.logger import logger
            logger.warning(f"DATABASE CONNECTION RETRY: Attempt {attempt + 1}/{max_retries} failed: {e}")
            import time
            time.sleep(2 ** attempt)  # Exponential backoff
