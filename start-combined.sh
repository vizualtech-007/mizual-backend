#!/bin/bash

# Run database migrations first
echo "Running database migrations..."
python migrate.py
if [ $? -ne 0 ]; then
    echo "Database migration failed. Exiting."
    exit 1
fi
echo "Database migrations completed"

# Start Celery worker in background
echo "Starting Celery worker..."
celery -A src.tasks.celery worker --loglevel=info --concurrency=2 -E --prefetch-multiplier=1 --max-tasks-per-child=50 &

# Give Celery a moment to start and show any errors
sleep 2

# Start FastAPI server
echo "Starting FastAPI server..."
uvicorn app:app --host 0.0.0.0 --port $PORT