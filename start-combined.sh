#!/bin/bash

# Start Celery worker in background
echo "🚀 Starting Celery worker..."
celery -A src.tasks.celery worker --loglevel=info --concurrency=1 --detach

# Start FastAPI server
echo "🚀 Starting FastAPI server..."
uvicorn app:app --host 0.0.0.0 --port $PORT