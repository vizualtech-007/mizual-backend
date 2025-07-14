#!/bin/bash

# Start Celery worker in background
celery -A app.tasks.celery worker --loglevel=info --concurrency=1 --detach

# Start FastAPI server
uvicorn app.main:app --host 0.0.0.0 --port $PORT