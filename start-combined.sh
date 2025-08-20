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

# Start Celery worker in background with environment-aware configuration
echo "Starting Celery worker for environment: $ENVIRONMENT"
if [ "$ENVIRONMENT" = "preview" ]; then
    # Dev environment (Render: 512MB RAM, 0.1 vCPU) - minimal resources
    echo "Using minimal Celery configuration for resource-constrained environment"
    celery -A src.tasks.celery worker --loglevel=info --concurrency=1 -E --prefetch-multiplier=1 --max-tasks-per-child=10 &
else
    # Production environment (Lightsail: 2GB RAM, 2 vCPU) - optimized settings
    echo "Using high-performance Celery configuration for production"
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

# Start FastAPI server with environment-aware configuration
echo "Starting FastAPI server on port ${PORT:-8000}..."
if [ "$ENVIRONMENT" = "preview" ]; then
    # Dev environment (Render: 512MB RAM, 0.1 vCPU) - single lightweight worker
    echo "Using single uvicorn worker for resource-constrained environment"
    uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1
else
    # Production environment (Lightsail: 2GB RAM, 2 vCPU) - high-concurrency gunicorn
    echo "Using 5 gunicorn workers for high-performance production"
    gunicorn -w 5 -k uvicorn.workers.UvicornWorker app:app --bind 0.0.0.0:${PORT:-8000}
fi