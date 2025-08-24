# CLAUDE.md - Backend Documentation

This file provides guidance to Claude Code (claude.ai/code) when working with the Mizual backend codebase.

**Last Updated**: August 24, 2025
**Framework**: FastAPI + Celery
**Production Status**: Fully operational with zero-downtime deployment
**Performance**: 11.7 seconds per image (73% improvement from original 40s)

## Project Overview

Mizual Backend is a sophisticated FastAPI + Celery system optimized for AI-powered image processing on resource-constrained environments (2GB RAM/2 vCPU Lightsail instances). The backend provides RESTful APIs for image editing using natural language prompts, with real-time progress tracking and chained editing capabilities.

### Key Features

- **AI-Powered Image Editing**: Integration with BFL Flux API and Google Gemini for prompt enhancement
- **Real-time Progress Tracking**: WebSocket-style polling with detailed processing stages
- **Edit Chaining**: Sequential edits with parent-child relationships (configurable max length)
- **High Performance**: 11.7s average processing time with 73% improvement over original architecture
- **Rate Limiting**: Configurable daily limits and burst protection
- **Caching Layer**: Redis-based caching for improved performance
- **Zero-Downtime Deployment**: Docker Registry + Watchtower architecture
- **Comprehensive Monitoring**: Health checks, performance tracking, and error handling

## Architecture Overview

### Technology Stack

- **Web Framework**: FastAPI 0.68+ with async support
- **Task Queue**: Celery with Redis broker
- **Database**: PostgreSQL with raw psycopg operations (SQLAlchemy eliminated)
- **Storage**: S3-compatible (AWS S3 / Backblaze B2)
- **Caching**: Redis with environment-prefixed keys
- **AI Services**: BFL Flux API, Google Gemini LLM
- **Image Processing**: PyVips with garbage collection optimization
- **HTTP Client**: httpx with connection pooling
- **Monitoring**: Performance tracking, health checks, debug endpoints

### Core Components

#### File Structure
```
mizual-backend/
├── app.py                      # Main FastAPI application
├── migrate.py                  # Database migration runner
├── start-combined.sh           # Production deployment script
├── requirements.txt            # Python dependencies
├── migrations/                 # SQL migration files
├── docker-compose.zero-downtime.yml  # Zero-downtime deployment config
├── lightsail-setup/           # Server setup and deployment scripts
│   ├── CLAUDE.md              # Deployment-specific documentation
│   ├── setup-lightsail.sh     # Server setup automation
│   ├── verify-deployment.sh   # Deployment verification
│   └── debug-watchtower.sh    # Troubleshooting tools
└── src/                       
    ├── db_raw.py              # Raw psycopg operations (primary database interface)
    ├── schemas.py             # Pydantic validation schemas
    ├── tasks.py               # Celery async task definitions
    ├── task_stages.py         # Stage-based processing with retry logic
    ├── flux_api.py            # BFL Flux API integration
    ├── s3.py                  # S3/Backblaze B2 storage
    ├── cache.py               # Redis caching layer
    ├── status_messages.py     # User-friendly progress messages
    ├── performance_tracker.py # Performance monitoring and optimization
    ├── logger.py              # Structured logging
    └── llm/                   # LLM provider abstraction
        ├── __init__.py        # Provider factory
        ├── base.py            # Abstract base provider
        ├── gemini_provider.py # Google Gemini implementation
        └── openai_provider.py # OpenAI implementation
```

### Request Flow Architecture

```mermaid
graph TD
    A[Client Request] --> B[FastAPI Router]
    B --> C[Rate Limiting]
    C --> D[Input Validation]
    D --> E[Image Type Detection]
    E --> F[S3 Upload]
    F --> G[Database Record Creation]
    G --> H[Celery Task Queue]
    H --> I[Stage-Based Processing]
    I --> J[LLM Prompt Enhancement]
    J --> K[BFL Flux API Call]
    K --> L[Result Processing]
    L --> M[S3 Result Upload]
    M --> N[Database Update]
    N --> O[Client Polling]
```

## API Endpoints Reference

### Core Endpoints

#### 1. **POST /edit-image/** - Main Image Editing Endpoint
```python
@app.post("/edit-image/", response_model=schemas.EditCreateResponse)
@limiter.limit(f"{RATE_LIMIT_DAILY_IMAGES}/day")
@limiter.limit(f"1/{RATE_LIMIT_BURST_SECONDS}seconds")
async def edit_image_endpoint(request: Request, edit_request: EditImageRequest)
```

**Request Body**:
```json
{
  "prompt": "Blur background and enhance lighting",
  "image": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEAYABgAAD...",
  "parent_edit_uuid": "optional-uuid-for-chaining"
}
```

**Response**:
```json
{
  "edit_id": "550e8400-e29b-41d4-a716-446655440000",
  "polling_url": "/edit/550e8400-e29b-41d4-a716-446655440000"
}
```

**Features**:
- **Rate Limiting**: Configurable daily limits per IP (default 3/day)
- **Burst Protection**: Configurable burst window (default 10 seconds)
- **Image Validation**: Magic byte detection for format validation
- **Edit Chaining**: Support for sequential edits with parent-child relationships
- **Chain Length Validation**: Configurable maximum chain length (default 5)
- **Async Processing**: Immediate response with Celery task queuing

**Supported Image Formats**:
- **Allowed**: JPEG, PNG, WebP, BMP, TIFF
- **Blocked**: HEIC, AVIF, GIF (configurable via `UNSUPPORTED_IMAGE_TYPES`)

#### 2. **GET /edit/{edit_uuid}** - Status Polling Endpoint
```python
@app.get("/edit/{edit_uuid}", response_model=schemas.EditStatusResponse)
@limiter.limit(f"{RATE_LIMIT_STATUS_CHECKS_PER_MINUTE}/minute")
def get_edit_status(request: Request, edit_uuid: str)
```

**Response**:
```json
{
  "uuid": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "processing_stage": "ai_processing",
  "message": "Creating your edited image with AI...",
  "progress_percent": 65,
  "is_complete": false,
  "is_error": false,
  "edited_image_url": null,
  "created_at": "2025-08-24T10:30:00Z"
}
```

**Processing Stages**:
1. `pending` - Initial state
2. `enhancing_prompt` - LLM prompt enhancement (optional)
3. `fetching_image` - S3 image download
4. `ai_processing` - BFL Flux API processing
5. `uploading_result` - S3 result upload
6. `completed` - Processing complete

**Caching**: Redis-based caching with 30-second TTL for performance optimization

#### 3. **POST /feedback/** - User Feedback Endpoint
```python
@app.post("/feedback/", response_model=schemas.FeedbackResponse)
@limiter.limit("5/minute")
async def submit_feedback(request: Request, feedback: schemas.FeedbackCreate)
```

**Request Body**:
```json
{
  "edit_uuid": "550e8400-e29b-41d4-a716-446655440000",
  "rating": 1,
  "feedback_text": "Great result, very professional looking!"
}
```

**Features**:
- **Binary Rating**: 0 (thumbs down) or 1 (thumbs up)
- **Required Text**: Feedback text required for thumbs down ratings
- **One Per Edit**: Prevents duplicate feedback for same edit
- **IP Tracking**: User IP stored for analytics (anonymized)

#### 4. **GET /chain/{edit_uuid}** - Edit Chain History
```python
@app.get("/chain/{edit_uuid}")
@limiter.limit("10/minute")
async def get_edit_chain_history(request: Request, edit_uuid: str)
```

**Response**:
```json
{
  "edit_uuid": "550e8400-e29b-41d4-a716-446655440000",
  "chain_length": 3,
  "chain_history": [
    {
      "edit": { /* complete edit object */ },
      "chain_position": 1,
      "parent_edit_uuid": null
    },
    // ... more chain entries
  ]
}
```

### Health & Debug Endpoints

#### **GET /health** - Basic Health Check
```python
@app.get("/health")
def health_check()
```
Simple health check for load balancers and monitoring systems.

#### **GET /health/celery** - Celery Worker Status
```python
@app.get("/health/celery")
@limiter.limit("10/minute")
async def celery_health_check(request: Request)
```
Detailed Celery worker connectivity and status information.

#### **GET /version** - Deployment Information
```python
@app.get("/version")
def version_info()
```
Returns deployment metadata including git commit, deploy time, and environment.

#### **GET /debug/db-schema** - Database Schema Information
```python
@app.get("/debug/db-schema")
@limiter.limit("5/minute")
async def debug_database_schema(request: Request)
```

#### **GET /debug/cache-stats** - Cache Performance Statistics
```python
@app.get("/debug/cache-stats")
@limiter.limit("5/minute")
async def debug_cache_stats(request: Request)
```

#### **GET /debug/db-performance** - Database Performance Metrics
```python
@app.get("/debug/db-performance")
@limiter.limit("3/minute")
async def debug_database_performance(request: Request)
```

## Database Schema

### Environment-Aware Architecture
The database uses schema-based environment separation:
- **Production**: `public` schema
- **Preview/Development**: `preview` schema

### Table Definitions

#### **Edit Table**
```sql
CREATE TABLE edits (
    id SERIAL PRIMARY KEY,
    uuid UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    prompt TEXT NOT NULL,
    enhanced_prompt TEXT,
    original_image_url TEXT NOT NULL,
    edited_image_url TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    processing_stage VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_edits_uuid ON edits(uuid);
CREATE INDEX idx_edits_status ON edits(status);
CREATE INDEX idx_edits_created_at ON edits(created_at DESC);
```

#### **EditFeedback Table**
```sql
CREATE TABLE edit_feedback (
    id SERIAL PRIMARY KEY,
    edit_uuid UUID NOT NULL REFERENCES edits(uuid) ON DELETE CASCADE,
    rating INTEGER NOT NULL CHECK (rating IN (0, 1)),
    feedback_text TEXT,
    user_ip INET,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_edit_feedback_unique ON edit_feedback(edit_uuid);
CREATE INDEX idx_edit_feedback_rating ON edit_feedback(rating);
```

#### **EditChain Table**
```sql
CREATE TABLE edit_chains (
    id SERIAL PRIMARY KEY,
    edit_uuid UUID NOT NULL REFERENCES edits(uuid) ON DELETE CASCADE,
    parent_edit_uuid UUID REFERENCES edits(uuid) ON DELETE CASCADE,
    chain_position INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_edit_chains_uuid ON edit_chains(edit_uuid);
CREATE INDEX idx_edit_chains_parent ON edit_chains(parent_edit_uuid);
CREATE INDEX idx_edit_chains_position ON edit_chains(chain_position);
```

### Database Interface (src/db_raw.py)

#### Primary Database Operations

**SQLAlchemy Eliminated**: The backend uses only raw psycopg operations for maximum performance and PgBouncer compatibility.

```python
def get_connection():
    """Get database connection with schema-aware configuration"""
    # Optimized connection with keepalive and autocommit

def create_edit(prompt: str, enhanced_prompt: str, original_image_url: str, parent_edit_uuid: str = None):
    """Create new edit record with chain handling"""

def get_edit_by_uuid(edit_uuid: str):
    """Retrieve edit by UUID with caching optimization"""

def update_edit_status(edit_id: int, status: str):
    """Update edit status with performance tracking"""

def update_edit_processing_stage(edit_id: int, stage: str):
    """Update processing stage for real-time progress"""
```

#### Performance Optimizations

**Connection Management**:
- Single connection pattern for PgBouncer compatibility
- Autocommit=True for transaction optimization  
- TCP keepalive configuration for connection stability
- Schema-aware connections (environment-based)

**Query Optimization**:
- Separate SQL operations instead of complex CTEs
- Optimized indexing strategy
- 15-25ms per operation (vs 50-80ms with ORM)
- Connection pooling at application level

## Processing Pipeline

### Stage-Based Processing Architecture

The image processing pipeline uses a sophisticated stage-based system with individual retry logic for each stage.

#### Processing Stages (src/task_stages.py)

```python
def process_edit_with_stage_retries(edit_id: int):
    """Main processing function with stage-specific error handling"""
    
    stages = [
        ("initialization", initialize_edit),
        ("enhancing_prompt", enhance_prompt_with_llm),
        ("fetching_image", fetch_and_cache_image),
        ("ai_processing", process_with_flux_api),
        ("uploading_result", upload_result_to_s3),
        ("completion", finalize_edit)
    ]
    
    for stage_name, stage_function in stages:
        with stage_retry_context(edit_id, stage_name):
            stage_function(edit_id)
```

#### Retry Configuration

```python
STAGE_RETRY_CONFIG = {
    "enhancing_prompt": {"max_retries": 2, "delay": 3},
    "fetching_image": {"max_retries": 2, "delay": 5},
    "ai_processing": {"max_retries": 0, "delay": 0},  # No retries for fast feedback
    "uploading_result": {"max_retries": 2, "delay": 5},
    "completion": {"max_retries": 3, "delay": 2}
}
```

#### Individual Stage Details

**1. Initialization**
- Database status updates
- Image caching preparation
- Performance tracking setup

**2. Prompt Enhancement (Optional)**
- Google Gemini LLM integration
- 3-step workflow: Planning → Validation → Architecture
- Graceful fallback to original prompt on failure
- 3-second base delay with exponential backoff

**3. Image Fetching**
- S3 download with connection pooling
- Image caching between stages
- PyVips image processing
- Garbage collection optimization

**4. AI Processing**
- BFL Flux API integration
- No retries for immediate user feedback
- 5-minute timeout with 0.5s polling
- Custom error classification (temporary/permanent)

**5. Result Upload**
- S3 upload with optimization
- Progressive JPEG at 85% quality
- CDN-friendly public URLs
- 2 retries with 5s base delay

**6. Completion**
- Final database updates
- Cache invalidation
- Performance metrics recording
- Resource cleanup

### Error Handling & Recovery

#### Error Classification System

```python
class ProcessingError(Exception):
    def __init__(self, message: str, stage: str, is_retryable: bool = True):
        self.message = message
        self.stage = stage
        self.is_retryable = is_retryable
```

#### Recovery Strategies

**Temporary Failures**:
- Exponential backoff retry logic
- Stage-specific retry counts
- Context preservation across retries
- Performance impact minimization

**Permanent Failures**:
- Immediate failure reporting
- User-friendly error messages
- Detailed logging for debugging
- Resource cleanup

**Partial Recovery**:
- Stage completion tracking
- Resume from last successful stage
- Progress preservation
- State consistency maintenance

## External Service Integrations

### BFL Flux API Integration (src/flux_api.py)

#### Configuration
```python
MODEL_NAME = "flux-kontext-pro"
SAFETY_LEVEL = 2  # Moderate safety filtering
TIMEOUT = 300     # 5-minute total timeout
POLL_INTERVAL = 0.5  # 500ms polling interval
```

#### API Workflow
```python
async def process_image_with_flux(prompt: str, image_data: bytes) -> str:
    """Complete Flux API processing workflow"""
    
    # 1. Submit processing request
    task_id = await submit_flux_request(prompt, image_data)
    
    # 2. Poll for completion
    result = await poll_flux_status(task_id)
    
    # 3. Download result image
    image_url = await download_flux_result(result.output_url)
    
    return image_url
```

#### Error Handling
```python
class FluxAPIError(Exception):
    """Custom exception for Flux API errors"""
    pass

# Error classification:
- Network timeouts: Retryable
- Rate limiting: Retryable with delay
- Invalid prompts: Non-retryable
- Processing failures: Non-retryable
```

#### Connection Pooling
- httpx async client with connection reuse
- Configurable limits (5 keepalive, 10 max connections)
- Per-request client creation to avoid event loop issues
- Automatic retry logic for network failures

### Google Gemini Integration (src/llm/gemini_provider.py)

#### Model Configuration
```python
MODEL_NAME = "gemini-1.5-flash"
MAX_TOKENS = 150
TEMPERATURE = 0.3
```

#### Prompt Enhancement Workflow
```python
def enhance_prompt(self, original_prompt: str, image_data: bytes) -> str:
    """3-step prompt enhancement process"""
    
    # Step 1: Planning
    plan = self._create_enhancement_plan(original_prompt)
    
    # Step 2: Validation  
    validated_plan = self._validate_plan(plan, image_data)
    
    # Step 3: Architecture
    enhanced_prompt = self._architect_final_prompt(validated_plan)
    
    return enhanced_prompt
```

#### Image Processing
- PyVips image resizing to 1024px maximum
- Format conversion to JPEG for API compatibility
- Memory-efficient streaming processing
- Automatic cleanup and garbage collection

#### Fallback Strategy
```python
try:
    enhanced_prompt = gemini_provider.enhance_prompt(original_prompt, image_data)
except Exception as e:
    logger.warning(f"Prompt enhancement failed: {e}")
    enhanced_prompt = original_prompt  # Graceful fallback
```

### S3/Backblaze B2 Integration (src/s3.py)

#### Configuration
```python
# Environment-based folder structure
STORAGE_PATH_PREFIX = os.environ.get("STORAGE_PATH_PREFIX", "production")
# Results in: mizual-images/production/... or mizual-images/preview/...
```

#### Client Management
```python
def get_s3_client():
    """Lazy client initialization with connection pooling"""
    if not hasattr(_thread_local, 's3_client'):
        _thread_local.s3_client = boto3.client(
            's3',
            endpoint_url=S3_ENDPOINT_URL,
            aws_access_key_id=S3_ACCESS_KEY_ID,
            aws_secret_access_key=S3_SECRET_ACCESS_KEY,
            region_name=S3_REGION_NAME,
            config=Config(
                retries={'max_attempts': 3},
                max_pool_connections=10
            )
        )
    return _thread_local.s3_client
```

#### Upload Optimization
```python
def upload_file_to_s3(file_data: bytes, file_name: str) -> str:
    """Optimized S3 upload with retry logic"""
    
    extra_args = {
        'ContentType': 'image/jpeg',
        'CacheControl': 'public, max-age=31536000',  # 1 year cache
        'ACL': 'public-read'  # CDN-friendly
    }
    
    # Upload with automatic retry
    s3_client.put_object(
        Bucket=S3_BUCKET_NAME,
        Key=s3_key,
        Body=file_data,
        **extra_args
    )
```

## Performance Optimization

### Current Performance Metrics

#### Processing Time Breakdown
- **Total Processing**: 11.7 seconds average
- **AI Processing**: 6.8s (58% of total time)
- **Prompt Enhancement**: 3.4s (29% of total time)
- **Result Upload**: 1.0s (9% of total time)
- **Image Fetching**: 0.035s (0.3% of total time)
- **Untracked Overhead**: 0.4s (3% of total time)

#### Performance Improvements Achieved
- **73% faster** than original Mumbai-based architecture
- **50% faster** AI processing through regional optimization
- **51% faster** prompt enhancement via LLM optimization
- **85% faster** upload operations through CDN proximity
- **98% faster** image fetching via caching and regional storage

### Optimization Techniques

#### 1. Database Performance
```python
# Eliminated SQLAlchemy ORM overhead
# Before: 50-80ms per database operation
# After: 15-25ms per database operation

def get_connection():
    return psycopg.connect(
        DATABASE_URL,
        autocommit=True,  # Optimized for PgBouncer
        options=f"-c search_path={DATABASE_SCHEMA}",
        keepalives_idle=600,
        keepalives_interval=30,
        keepalives_count=3
    )
```

#### 2. Memory Management
```python
# Explicit garbage collection after image processing
import gc

def process_image_stage():
    # Process image data
    result = heavy_image_processing()
    
    # Explicit cleanup
    del intermediate_data
    gc.collect()
    
    return result
```

#### 3. HTTP Connection Pooling
```python
# Async HTTP client with connection reuse
async def create_http_client():
    return httpx.AsyncClient(
        limits=httpx.Limits(
            max_keepalive_connections=5,
            max_connections=10,
            keepalive_expiry=30
        ),
        timeout=httpx.Timeout(30.0)
    )
```

#### 4. Redis Caching Layer (src/cache.py)
```python
# Environment-aware caching with TTL optimization
CACHE_CONFIG = {
    "edit_status": {"ttl": 30, "prefix": f"{ENVIRONMENT}:status:"},
    "edit_feedback": {"ttl": 300, "prefix": f"{ENVIRONMENT}:feedback:"},
    "chain_history": {"ttl": 60, "prefix": f"{ENVIRONMENT}:chain:"}
}

def cache_edit_status(edit_uuid: str, status_data: dict):
    """Cache edit status with optimized TTL"""
    cache_key = f"{ENVIRONMENT}:status:{edit_uuid}"
    redis_client.setex(cache_key, 30, json.dumps(status_data))
```

#### 5. Image Processing Optimization
```python
# PyVips streaming processing with memory efficiency
import pyvips

def process_image_efficiently(image_data: bytes):
    # Stream processing without loading entire image to memory
    image = pyvips.Image.new_from_buffer(image_data, '')
    
    # Progressive JPEG optimization
    result = image.jpegsave_buffer(
        Q=85,  # Quality optimization
        optimize_coding=True,
        strip=True,  # Remove metadata
        interlace=True  # Progressive loading
    )
    
    return result
```

### Resource Management

#### Memory Configuration (2GB RAM Environment)
```python
# Celery worker configuration
CELERY_CONCURRENCY = int(os.environ.get("CELERY_CONCURRENCY", "1"))
CELERY_MEMORY_LIMIT = os.environ.get("CELERY_WORKER_MEMORY_LIMIT", "600MB")

# Container resource limits
BACKEND_MEMORY_LIMIT = "400MB"
CELERY_MEMORY_LIMIT = "600MB"  
REDIS_MEMORY_LIMIT = "200MB"
```

#### Concurrent User Handling
```python
# Optimized for 3 concurrent users
MAX_WORKERS = int(os.environ.get("MAX_WORKERS", "3"))

# Dynamic scaling based on load
if system_memory_available() > 1500:  # MB
    MAX_WORKERS = min(MAX_WORKERS + 1, 5)
```

## Caching Strategy

### Redis Caching Architecture (src/cache.py)

#### Cache Configuration
```python
ENVIRONMENT = os.environ.get("ENVIRONMENT", "production")

CACHE_CONFIG = {
    "edit_status": {
        "ttl": 30,  # Short TTL for frequently changing data
        "prefix": f"{ENVIRONMENT}:status:"
    },
    "edit_feedback": {
        "ttl": 300,  # Longer TTL for stable data
        "prefix": f"{ENVIRONMENT}:feedback:"
    },
    "chain_history": {
        "ttl": 60,  # Medium TTL for semi-static data
        "prefix": f"{ENVIRONMENT}:chain:"
    }
}
```

#### Implementation
```python
def get_cached_edit_status(edit_uuid: str) -> Optional[dict]:
    """Retrieve cached edit status with error handling"""
    try:
        cache_key = f"{ENVIRONMENT}:status:{edit_uuid}"
        cached_data = redis_client.get(cache_key)
        return json.loads(cached_data) if cached_data else None
    except Exception as e:
        logger.warning(f"Cache retrieval failed for {edit_uuid}: {e}")
        return None

def cache_edit_status(edit_uuid: str, status_data: dict):
    """Cache edit status with automatic expiration"""
    try:
        cache_key = f"{ENVIRONMENT}:status:{edit_uuid}"
        redis_client.setex(cache_key, 30, json.dumps(status_data))
    except Exception as e:
        logger.warning(f"Cache storage failed for {edit_uuid}: {e}")
```

### Cache Performance Impact

#### Hit Rate Optimization
- **Status Checks**: ~80% cache hit rate (reduces DB load)
- **Feedback Queries**: ~95% cache hit rate (feedback rarely changes)
- **Chain History**: ~70% cache hit rate (moderate complexity queries)

#### Performance Metrics
```python
def get_cache_stats() -> dict:
    """Retrieve cache performance statistics"""
    try:
        info = redis_client.info()
        return {
            "connected_clients": info.get("connected_clients", 0),
            "used_memory_human": info.get("used_memory_human", "0B"),
            "keyspace_hits": info.get("keyspace_hits", 0),
            "keyspace_misses": info.get("keyspace_misses", 0),
            "hit_rate": calculate_hit_rate(info),
            "environment": ENVIRONMENT
        }
    except Exception as e:
        return {"error": f"Failed to get cache stats: {e}"}
```

## Rate Limiting & Security

### Rate Limiting Configuration

#### Configurable Limits
```python
# Environment-based rate limiting
RATE_LIMIT_DAILY_IMAGES = os.environ.get("RATE_LIMIT_DAILY_IMAGES", "3")
RATE_LIMIT_BURST_SECONDS = os.environ.get("RATE_LIMIT_BURST_SECONDS", "10")  
RATE_LIMIT_STATUS_CHECKS_PER_MINUTE = os.environ.get("RATE_LIMIT_STATUS_CHECKS_PER_MINUTE", "30")
```

#### Implementation
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/edit-image/")
@limiter.limit(f"{RATE_LIMIT_DAILY_IMAGES}/day")
@limiter.limit(f"1/{RATE_LIMIT_BURST_SECONDS}seconds")
async def edit_image_endpoint(request: Request, edit_request: EditImageRequest):
    # Rate limited endpoint logic
```

#### Rate Limiting Strategy
- **Daily Limits**: Prevent abuse while allowing legitimate use
- **Burst Protection**: Prevent rapid-fire requests
- **Per-Endpoint Limits**: Different limits for different operations
- **IP-Based**: Simple but effective for web applications

### Security Measures

#### Input Validation
```python
def validate_image_type(image_bytes: bytes) -> tuple[bool, str]:
    """Validate image format using magic bytes"""
    detected_type = detect_image_type(image_bytes)
    
    if detected_type in UNSUPPORTED_IMAGE_TYPES:
        return False, f"Format '{detected_type}' not supported"
    
    return True, detected_type

def detect_image_type(image_bytes: bytes) -> str:
    """Magic byte detection for security"""
    if image_bytes.startswith(b'\xff\xd8\xff'):
        return 'jpeg'
    elif image_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'png'
    # ... additional format checks
```

#### CORS Configuration
```python
# Environment-aware CORS
ENVIRONMENT = os.environ.get("ENVIRONMENT", "production")

if ENVIRONMENT == "preview":
    allowed_origins = ["*"]  # Development flexibility
else:
    allowed_origins = [
        "https://mizual.ai",
        "https://www.mizual.ai",
        "https://mizual-frontend-git-main-*.vercel.app"
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False if ENVIRONMENT == "preview" else True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)
```

#### Error Handling
```python
# Secure error responses
try:
    result = process_sensitive_operation()
except Exception as e:
    logger.error(f"Operation failed: {str(e)}")  # Detailed logging
    return {"error": "Processing failed"}  # Generic user message
```

## Environment Configuration

### Required Environment Variables

#### Core Configuration
```env
# Environment identification
ENVIRONMENT=preview                    # or production
LOG_LEVEL=INFO                        # DEBUG, INFO, WARNING, ERROR

# Database configuration
DATABASE_URL=postgresql://user:pass@host:5432/db
DATABASE_SCHEMA=preview               # or public for production
```

#### Redis/Celery Configuration
```env
# Redis configuration
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# Worker configuration  
MAX_WORKERS=3                         # Celery worker count
CELERY_CONCURRENCY=3                  # Worker concurrency level
CELERY_WORKER_MEMORY_LIMIT=600MB      # Memory limit per worker
```

#### Storage Configuration
```env
# S3/Backblaze B2 configuration
S3_BUCKET_NAME=mizual-images
S3_ENDPOINT_URL=https://s3.us-west-000.backblazeb2.com
S3_ACCESS_KEY_ID=your-access-key
S3_SECRET_ACCESS_KEY=your-secret-key
S3_REGION_NAME=us-west-000
STORAGE_PATH_PREFIX=preview           # or production
```

#### AI Services Configuration
```env
# BFL Flux API
BFL_API_KEY=your-bfl-api-key

# Google Gemini LLM
GEMINI_API_KEY=your-gemini-key
LLM_PROVIDER=gemini                   # or openai
LLM_MODEL=gemini-1.5-flash
LLM_API_KEY=your-llm-key
ENABLE_PROMPT_ENHANCEMENT=true
```

#### Rate Limiting Configuration
```env
# Rate limiting
RATE_LIMIT_DAILY_IMAGES=3            # Max images per day per IP
RATE_LIMIT_BURST_SECONDS=10          # Burst protection window
RATE_LIMIT_STATUS_CHECKS_PER_MINUTE=30  # Status polling limit
```

#### Image Processing Configuration
```env
# Image validation
UNSUPPORTED_IMAGE_TYPES=heic,avif,gif  # Blocked formats
MAX_CHAIN_LENGTH=5                     # Maximum edit chain length
```

### Environment-Specific Configuration

#### Preview Environment (Development)
```env
ENVIRONMENT=preview
DATABASE_SCHEMA=preview
STORAGE_PATH_PREFIX=preview
RATE_LIMIT_DAILY_IMAGES=50           # Higher limits for testing
MAX_CHAIN_LENGTH=50                  # Longer chains for testing
LOG_LEVEL=DEBUG
```

#### Production Environment
```env
ENVIRONMENT=production
DATABASE_SCHEMA=public
STORAGE_PATH_PREFIX=production
RATE_LIMIT_DAILY_IMAGES=3           # Conservative limits
MAX_CHAIN_LENGTH=5                  # Reasonable chain length
LOG_LEVEL=INFO
```

## Development Commands

### Local Development Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env.local
# Edit .env.local with your configuration

# Run database migrations
python migrate.py

# Start FastAPI development server (port 10000)
python app.py
# Or with uvicorn:
uvicorn app:app --host 0.0.0.0 --port 10000 --reload

# Run Celery worker (separate terminal)
celery -A src.tasks.celery worker --loglevel=info

# Optional: Run Redis locally
redis-server
```

### Production Deployment

```bash
# Combined API + Worker deployment
./start-combined.sh

# Or manually:
gunicorn -w 2 -k uvicorn.workers.UvicornWorker app:app --bind 0.0.0.0:8000 &
celery -A src.tasks.celery worker --loglevel=info --concurrency=1 &
```

### Docker Development

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services  
docker-compose down

# Check service health
docker-compose ps
```

### Testing Commands

```bash
# Health checks
curl http://localhost:10000/health
curl http://localhost:10000/health/celery

# Debug endpoints
curl http://localhost:10000/debug/db-schema
curl http://localhost:10000/debug/cache-stats
curl http://localhost:10000/debug/db-performance

# Version information
curl http://localhost:10000/version
```

## Database Migrations

### Migration System

#### Migration File Structure
```
migrations/
├── 20241201_143000_add_feedback_system_env.sql
├── 20241201_160000_update_feedback_to_thumbs.sql
├── 20241208_143000_add_processing_stage_env.sql
└── 20241215_143000_add_edit_chains_table_env.sql
```

#### Migration Template
```sql
-- Migration: Description of changes
-- Environment: _env suffix indicates environment-aware migration

-- Apply migration
BEGIN;

-- Your DDL/DML statements here
ALTER TABLE edits ADD COLUMN IF NOT EXISTS processing_stage VARCHAR(50) DEFAULT 'pending';
CREATE INDEX IF NOT EXISTS idx_edits_processing_stage ON edits(processing_stage);

COMMIT;

-- Rollback migration (commented)
-- BEGIN;
-- ALTER TABLE edits DROP COLUMN IF EXISTS processing_stage;
-- COMMIT;
```

#### Running Migrations
```python
# migrate.py
def run_migrations():
    """Run pending migrations with environment awareness"""
    
    # Get current schema based on environment
    schema = get_current_schema()
    
    # Find and execute pending migrations
    migration_files = get_pending_migrations()
    
    for migration_file in migration_files:
        execute_migration(migration_file, schema)
```

### Database Performance Optimization

#### Connection Configuration
```python
def get_connection():
    """Optimized database connection"""
    return psycopg.connect(
        DATABASE_URL,
        autocommit=True,  # Avoid transaction overhead
        options=f"-c search_path={DATABASE_SCHEMA}",
        
        # Connection keepalive for stability
        keepalives_idle=600,    # 10 minutes
        keepalives_interval=30, # 30 seconds
        keepalives_count=3      # 3 retries
    )
```

#### Query Optimization Examples
```python
# Optimized: Separate operations
def update_edit_with_stage(edit_id: int, status: str, stage: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Separate updates for better performance
            cur.execute("UPDATE edits SET status = %s WHERE id = %s", (status, edit_id))
            cur.execute("UPDATE edits SET processing_stage = %s WHERE id = %s", (stage, edit_id))

# Less optimal: Complex CTE
def update_edit_with_cte(edit_id: int, status: str, stage: str):
    # Avoid complex CTEs for simple operations
    query = """
        WITH updated AS (
            UPDATE edits SET status = %s, processing_stage = %s 
            WHERE id = %s RETURNING *
        )
        SELECT * FROM updated
    """
    # This creates unnecessary complexity for simple updates
```

## Deployment Architecture

### Zero-Downtime Deployment

The backend uses a sophisticated zero-downtime deployment system with Docker Registry + Watchtower. Full deployment documentation is available in [`lightsail-setup/CLAUDE.md`](./lightsail-setup/CLAUDE.md).

#### Key Components
- **Local Docker Registry**: `localhost:5000` for image storage
- **Watchtower**: Automatic container updates (1-minute polling)
- **GitHub Actions**: Automated build and deployment pipeline
- **Health Checks**: Comprehensive service monitoring

#### Deployment Flow
1. **Code Push**: Triggers GitHub Actions workflow
2. **Image Build**: Ultra-slim Docker image (433MB)
3. **Transfer**: SCP image to server
4. **Registry Push**: Push to local registry with `:latest` tag
5. **Watchtower Update**: Automatic rolling update detection
6. **Verification**: Health check and version confirmation

#### Infrastructure Requirements
- **AWS Lightsail**: 2GB RAM, 2 vCPU instances  
- **Registry Storage**: `/opt/mizual/registry-data` (persistent)
- **Resource Overhead**: Only 14.7MB total (Registry: 7.4MB + Watchtower: 7.3MB)

### Environment Setup Scripts

#### Server Setup (`lightsail-setup/setup-lightsail.sh`)
```bash
# Automated server setup for new instances
bash lightsail-setup/setup-lightsail.sh

# Features:
- Docker and Docker Compose installation
- Firewall configuration (ports 22, 80)
- Directory structure creation
- User permissions setup
- Non-interactive installation
```

#### Deployment Verification (`lightsail-setup/verify-deployment.sh`)  
```bash
# Comprehensive deployment check
bash lightsail-setup/verify-deployment.sh

# Checks:
- Docker service status
- Container health
- API endpoint functionality
- Database connectivity
- Registry status
- Resource usage
```

## Monitoring & Health Checks

### Health Check Endpoints

#### Basic Health Check
```python
@app.get("/health")
def health_check():
    return {"status": "ok", "message": "Service is running"}
```

#### Celery Health Check
```python
@app.get("/health/celery")  
async def celery_health_check():
    # Check worker connectivity
    inspect = celery.control.inspect()
    active_workers = inspect.active()
    
    return {
        "status": "healthy" if active_workers else "unhealthy",
        "worker_count": len(active_workers or []),
        "workers": list(active_workers.keys() if active_workers else [])
    }
```

#### Performance Monitoring
```python
@app.get("/debug/db-performance")
async def debug_database_performance():
    return {
        "connection_info": get_connection_stats(),
        "query_performance": get_slow_queries(),
        "index_usage": get_index_statistics(),
        "recommendations": get_optimization_suggestions()
    }
```

### Performance Tracking

#### Processing Time Monitoring
```python
# src/performance_tracker.py
class PerformanceTracker:
    def track_stage_performance(self, stage_name: str, duration: float):
        """Track individual stage performance"""
        logger.info(f"Stage '{stage_name}' completed in {duration:.2f}s")
        
    def get_performance_summary(self) -> dict:
        """Get comprehensive performance metrics"""
        return {
            "total_processing_time": self.total_time,
            "stage_breakdown": self.stage_times,
            "memory_usage": self.memory_stats,
            "optimization_suggestions": self.get_optimizations()
        }
```

## Troubleshooting & Debugging

### Common Issues & Solutions

#### 1. **Database Connection Issues**
```python
# Check database connectivity
def test_database_connection():
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                return {"status": "connected", "schema": DATABASE_SCHEMA}
    except Exception as e:
        return {"status": "error", "error": str(e)}
```

#### 2. **Celery Worker Problems** 
```bash
# Check worker status
celery -A src.tasks.celery inspect active

# Check Redis connectivity
redis-cli ping

# Restart workers
pkill -f celery
celery -A src.tasks.celery worker --loglevel=info
```

#### 3. **S3/Storage Issues**
```python
def test_s3_connectivity():
    try:
        s3_client = get_s3_client()
        s3_client.head_bucket(Bucket=S3_BUCKET_NAME)
        return {"status": "connected", "bucket": S3_BUCKET_NAME}
    except Exception as e:
        return {"status": "error", "error": str(e)}
```

#### 4. **Performance Issues**
```python
# Check system resources
def get_system_health():
    return {
        "memory_usage": get_memory_usage(),
        "cpu_usage": get_cpu_usage(),
        "disk_usage": get_disk_usage(),
        "active_connections": get_connection_count()
    }
```

### Debug Utilities

#### Watchtower Debugging
```bash
# Debug watchtower deployment issues
bash lightsail-setup/debug-watchtower.sh

# Features:
- Container status verification
- Registry connectivity check
- Image tag validation
- Health check execution
- Manual update trigger
```

#### Log Analysis
```bash
# View container logs
docker logs mizual-backend --tail 100
docker logs mizual-celery --tail 100

# Follow log output
docker logs mizual-backend -f

# Check system logs
journalctl -u docker.service --tail 50
```

#### Performance Debugging
```python
# Enable detailed performance logging
LOG_LEVEL=DEBUG

# Check processing bottlenecks
curl http://localhost/debug/db-performance
curl http://localhost/debug/cache-stats

# Monitor resource usage
docker stats
```

## Development Best Practices

### Code Organization

#### Module Structure
```python
# Recommended import order
import os
import sys
from typing import Optional, Dict, List

import fastapi
import pydantic

from src import db_raw, cache, logger
from src.tasks import celery
```

#### Error Handling
```python
# Consistent error handling pattern
try:
    result = risky_operation()
    logger.info(f"Operation succeeded: {result}")
    return result
except SpecificError as e:
    logger.error(f"Specific error in operation: {e}")
    raise HTTPException(status_code=400, detail="User-friendly message")
except Exception as e:
    logger.error(f"Unexpected error in operation: {e}")
    raise HTTPException(status_code=500, detail="Internal server error")
```

#### Database Operations
```python
# Use context managers for connections
def database_operation():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM edits WHERE id = %s", (edit_id,))
            return cur.fetchone()
```

### Performance Guidelines

#### Memory Management
```python
# Explicit cleanup for large objects
def process_large_image():
    image_data = load_large_image()
    
    try:
        result = process_image(image_data)
        return result
    finally:
        del image_data
        gc.collect()
```

#### Async Operations
```python
# Use async for I/O bound operations
async def fetch_external_data():
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.json()
```

#### Caching Strategy
```python
# Cache expensive operations
@lru_cache(maxsize=128)
def expensive_computation(input_data: str) -> str:
    # Expensive operation here
    return result
```

### Security Guidelines

#### Input Sanitization
```python
def sanitize_prompt(prompt: str) -> str:
    # Remove potentially harmful content
    sanitized = prompt.strip()[:1000]  # Limit length
    return sanitized
```

#### Secure Logging
```python
# Avoid logging sensitive information
logger.info(f"Processing edit for user {user_id[:8]}...")  # Only log prefix
# Don't log: API keys, full user data, image content
```

---

**Related Documentation**:
- **Deployment Setup**: [`lightsail-setup/CLAUDE.md`](./lightsail-setup/CLAUDE.md)
- **Monitoring Guide**: [`lightsail-setup/MONITORING.md`](./lightsail-setup/MONITORING.md) 
- **Zero-Downtime Setup**: [`lightsail-setup/SETUP-ZERO-DOWNTIME.md`](./lightsail-setup/SETUP-ZERO-DOWNTIME.md)

**Next Steps**: This documentation should be updated when:
- New API endpoints are added
- Processing pipeline stages are modified
- Performance optimizations are implemented
- External service integrations change
- Database schema updates are made