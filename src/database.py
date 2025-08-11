from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://user:password@localhost/db")
ENVIRONMENT = os.environ.get("ENVIRONMENT", "production")

# Add schema to connection based on environment
schema_name = "preview" if ENVIRONMENT == "preview" else "public"
print(f"🔧 Database Environment: {ENVIRONMENT}")
print(f"🔧 Using schema: {schema_name}")

connect_args = {
    "sslmode": "require",
    "options": f"-csearch_path={schema_name},public"
}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
