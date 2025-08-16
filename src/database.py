from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
import os

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://user:password@localhost/db")
ENVIRONMENT = os.environ.get("ENVIRONMENT", "production")

# Add schema to connection based on environment
schema_name = "preview" if ENVIRONMENT == "preview" else "public"
connect_args = {
    "sslmode": "require",
    "options": f"-csearch_path={schema_name},public"
}

# Improved connection pool configuration for better reliability
engine = create_engine(
    DATABASE_URL, 
    connect_args=connect_args,
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,  # Validates connections before use
    pool_recycle=3600,   # Recycle connections every hour
    echo=False
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def set_schema_for_session(db):
    """Explicitly set the schema path for a database session"""
    schema_name = "preview" if ENVIRONMENT == "preview" else "public"
    db.execute(text(f"SET search_path TO {schema_name}, public"))
    db.commit()

def get_db():
    db = SessionLocal()
    try:
        set_schema_for_session(db)
        yield db
    finally:
        db.close()

def get_db_with_retry(max_retries=3):
    """Get database connection with retry logic for tasks"""
    for attempt in range(max_retries):
        db = None
        try:
            db = SessionLocal()
            # Set schema path explicitly
            set_schema_for_session(db)
            # Test the connection with proper SQLAlchemy text() wrapper
            db.execute(text("SELECT 1"))
            return db
        except Exception as e:
            if db:
                db.close()
            if attempt == max_retries - 1:
                raise e
            print(f"DATABASE CONNECTION RETRY: Attempt {attempt + 1}/{max_retries} failed: {e}")
            import time
            time.sleep(2 ** attempt)  # Exponential backoff
