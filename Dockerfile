# Multi-stage Dockerfile for FastAPI
FROM python:3.11-slim AS base

# Set working directory
WORKDIR /code

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Development stage
FROM base AS development

# Copy application code
COPY . /code

# Expose port
EXPOSE 8000

# Set Python path
ENV PYTHONPATH=/code

# Start development server with hot reload
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# Production stage
FROM base AS production

# Copy application code
COPY . /code

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash mizual
RUN chown -R mizual:mizual /code
USER mizual

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Default command
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]