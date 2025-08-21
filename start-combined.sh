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

# Start Celery worker in background (unified configuration for 2GB RAM, 2 vCPU)
echo "Starting Celery worker for environment: $ENVIRONMENT"
echo "Using unified Celery configuration for Lightsail 2GB/2vCPU"
celery -A src.tasks.celery worker --loglevel=warning --concurrency=2 -E --prefetch-multiplier=1 --max-tasks-per-child=100 &

# Give Celery a moment to start and show any errors
echo "Waiting for Celery worker to initialize..."
sleep 3

# Check if Celery worker started successfully
if pgrep -f "celery.*worker" > /dev/null; then
    echo "Celery worker started successfully"
else
    echo "WARNING: Celery worker may not have started properly"
fi

# Start FastAPI server (unified configuration for 2GB RAM, 2 vCPU)
echo "Starting FastAPI server on port ${PORT:-8000}..."
echo "Using 5 gunicorn workers for Lightsail 2GB/2vCPU"
gunicorn -w 5 -k uvicorn.workers.UvicornWorker app:app --bind 0.0.0.0:${PORT:-8000}