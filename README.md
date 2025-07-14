# Mizual Backend - Reorganized Structure

## 📁 New Package Structure

```
mizual-backend/
├── app.py                  # Main FastAPI application (entry point)
├── src/                    # Python package directory
│   ├── __init__.py        # Package marker
│   ├── models.py          # SQLAlchemy database models
│   ├── schemas.py         # Pydantic request/response schemas
│   ├── database.py        # Database configuration
│   ├── crud.py            # Database CRUD operations
│   ├── tasks.py           # Celery background tasks
│   ├── flux_api.py        # Flux AI API integration
│   └── s3.py              # MinIO/S3 storage operations
├── start-combined.sh      # Startup script for Render
├── render.yaml            # Render deployment configuration
├── requirements.txt       # Python dependencies
├── Dockerfile             # Container definition
└── .env.example           # Environment variables template
```

## 🔧 Import Structure

### Main Application (`app.py`)
```python
from src import models, schemas, database, crud, s3, tasks
from src.database import engine
```

### Package Modules (`src/*.py`)
```python
# Relative imports within the package
from . import models, schemas
from .database import Base
```

## 🚀 Benefits

1. **✅ Clean Imports**: No more same-level import issues
2. **✅ Package Structure**: Proper Python package organization
3. **✅ Maintainable**: Clear separation between entry point and modules
4. **✅ Scalable**: Easy to add new modules to `src/` package
5. **✅ Professional**: Industry-standard Python project structure

## 📋 Deployment Commands

### Celery Worker
```bash
celery -A src.tasks.celery worker --loglevel=info --concurrency=1 --detach
```

### FastAPI Server
```bash
uvicorn app:app --host 0.0.0.0 --port $PORT
```

## 🎯 Ready for Deployment

The reorganized structure is now ready for Render deployment with proper import resolution.