#!/bin/bash

# Environment detection and logging
ENVIRONMENT=${ENVIRONMENT:-production}
echo "=== MIZUAL BACKEND STARTUP ==="
echo "Environment: $ENVIRONMENT"
echo "Database Schema: ${DATABASE_SCHEMA:-public}"
echo "Port: ${PORT:-8000}"
echo "Redis URL: ${CELERY_BROKER_URL:-not_set}"
echo "================================"

# Run database migrations first
echo "Running database migrations..."
python migrate.py
if [ $? -ne 0 ]; then
    echo "Database migration failed. Exiting."
    exit 1
fi
echo "Database migrations completed successfully"

# Start Celery worker in background
echo "Starting Celery worker for environment: $ENVIRONMENT"
if [ "$ENVIRONMENT" = "preview" ]; then
    # Dev environment - single worker for cost efficiency
    celery -A src.tasks.celery worker --loglevel=info --concurrency=1 -E --prefetch-multiplier=1 --max-tasks-per-child=25 &
else
    # Production environment - optimized settings
    celery -A src.tasks.celery worker --loglevel=warning --concurrency=2 -E --prefetch-multiplier=1 --max-tasks-per-child=100 &
fi

# Give Celery a moment to start and show any errors
echo "Waiting for Celery worker to initialize..."
sleep 3

# Check if Celery worker started successfully
if pgrep -f "celery.*worker" > /dev/null; then
    echo "Celery worker started successfully"
else
    echo "WARNING: Celery worker may not have started properly"
fi

# Start FastAPI server with production configuration
echo "Starting FastAPI server with gunicorn on port ${PORT:-8000}..."
if [ "$ENVIRONMENT" = "preview" ]; then
    # Preview environment - single worker for resource efficiency
    uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}
else
    # Production environment - optimized gunicorn configuration
    gunicorn -w 5 -k uvicorn.workers.UvicornWorker app:app --bind 0.0.0.0:${PORT:-8000}
fi