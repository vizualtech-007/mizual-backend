#!/bin/bash

# Debug mode - test all connections first
echo "🔍 Running connection debug script..."
python debug_connections.py

# If debug passes, start the actual services
if [ $? -eq 0 ]; then
    echo "✅ All connections successful! Starting services..."
    
    # Start Celery worker in background
    celery -A src.tasks.celery worker --loglevel=info --concurrency=1 --detach
    
    # Start FastAPI server
    uvicorn app:app --host 0.0.0.0 --port $PORT
else
    echo "❌ Connection tests failed! Check the logs above."
    exit 1
fi