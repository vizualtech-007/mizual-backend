# Mizual - AI-Powered Image Editor

Mizual is a production-ready, web-based AI image editing platform that combines the power of advanced language models with state-of-the-art image generation APIs. Built with a modern tech stack, Mizual provides users with intuitive AI-powered image editing capabilities through natural language prompts.

## 🌟 Features

### ✅ **Core Features (Implemented)**

- **🖼️ AI-Powered Image Editing:** Upload images and edit them using natural language prompts
- **🤖 Agentic LLM System:** Intelligent prompt enhancement using Google Gemini for better edit results
- **📊 Real-time Progress Tracking:** Dynamic progress indicators with user-friendly status messages
- **👍👎 User Feedback System:** Thumbs up/down feedback with conditional text input for improvements
- **🔗 Follow-up Image Editing:** Chain up to 5 edits together for iterative refinement workflows
- **🔄 Asynchronous Processing:** Non-blocking image processing with Celery and Redis
- **☁️ Cloud Storage:** Secure image storage with S3-compatible services
- **🌍 Multi-Environment Support:** Separate development and production environments
- **🔧 Health Monitoring:** Built-in health checks for monitoring and load balancers
- **🗄️ Automated Database Migrations:** Environment-aware schema management
- **🛡️ Rate Limiting & Security:** API protection and input validation
- **📈 Chain Analytics:** Usage statistics and edit chain insights

### 🚀 **Future Enhancements**

- **📊 Advanced Analytics Dashboard:** Comprehensive usage analytics and insights
- **🎨 Style Presets:** Pre-configured editing styles for common use cases
- **📱 Mobile App:** Native iOS/Android applications
- **🤝 Team Collaboration:** Shared editing workspaces

## 🏗️ Architecture Overview

Mizual follows a modern microservices architecture with clear separation of concerns:

```mermaid
graph TB
    subgraph "Frontend Layer"
        FE[Next.js Frontend]
    end
    
    subgraph "API Layer"
        API[FastAPI Backend]
        LB[Load Balancer]
    end
    
    subgraph "Processing Layer"
        CELERY[Celery Workers]
        REDIS[Redis Queue]
    end
    
    subgraph "AI Services"
        GEMINI[Google Gemini LLM]
        BFL[BFL Flux API]
    end
    
    subgraph "Data Layer"
        DB[(Supabase PostgreSQL)]
        S3[(S3 Storage)]
    end
    
    subgraph "Infrastructure"
        RENDER[Render.com]
        MONITOR[Health Monitoring]
    end
    
    FE --> API
    API --> REDIS
    API --> DB
    REDIS --> CELERY
    CELERY --> GEMINI
    CELERY --> BFL
    CELERY --> S3
    CELERY --> DB
    API --> MONITOR
    
    style FE fill:#e1f5fe
    style API fill:#f3e5f5
    style CELERY fill:#fff3e0
    style GEMINI fill:#e8f5e8
    style BFL fill:#e8f5e8
    style DB fill:#fce4ec
    style S3 fill:#fce4ec
```

## 🔄 Complete Image Processing Flow

```mermaid
sequenceDiagram
    participant U as User
    participant FE as Frontend
    participant API as FastAPI
    participant DB as Database
    participant Q as Redis Queue
    participant W as Celery Worker
    participant G as Gemini LLM
    participant BFL as BFL Flux API
    participant S3 as S3 Storage
    
    U->>FE: Upload image + prompt
    FE->>API: POST /edit-image/
    API->>S3: Upload original image
    API->>DB: Create edit record (pending)
    API->>Q: Queue processing task
    API->>FE: Return edit_uuid
    FE->>U: Show "Your edit is queued..."
    
    Q->>W: Trigger process_image_edit
    W->>DB: Update stage: "enhancing_prompt"
    W->>G: Enhance user prompt
    G->>W: Return enhanced prompt
    W->>DB: Save enhanced prompt
    
    W->>DB: Update stage: "processing_image"
    W->>S3: Fetch original image
    W->>BFL: Send image + enhanced prompt
    BFL->>W: Return edited image
    
    W->>DB: Update stage: "uploading_result"
    W->>S3: Upload edited image
    W->>DB: Update status: "completed"
    
    loop Progress Polling
        FE->>API: GET /edit/{uuid}
        API->>DB: Get current status
        API->>FE: Return progress info
        FE->>U: Update progress UI
    end
    
    FE->>U: Show completed result
    U->>FE: Submit feedback (optional)
    FE->>API: POST /feedback/
    API->>DB: Store user feedback
```

## 💻 Tech Stack

### **Backend Services**
- **[FastAPI](https://fastapi.tiangolo.com/):** Modern, high-performance web framework with automatic API documentation
- **[Celery](https://docs.celeryq.dev/):** Distributed task queue for asynchronous image processing
- **[Redis](https://redis.io/):** In-memory message broker and caching layer
- **[PostgreSQL (Supabase)](https://supabase.com/):** Production-grade database with multi-schema support
- **[SQLAlchemy](https://www.sqlalchemy.org/):** Advanced ORM with environment-aware schema management

### **AI & ML Services**
- **[Google Gemini](https://ai.google.dev/):** Advanced LLM for intelligent prompt enhancement
- **[BFL Flux API](https://www.bfl.ai/):** State-of-the-art image generation and editing
- **Agentic LLM System:** Intelligent prompt optimization pipeline

### **Frontend**
- **[Next.js 14](https://nextjs.org/):** React framework with App Router and server components
- **[TypeScript](https://www.typescriptlang.org/):** Type-safe development with enhanced developer experience
- **[Tailwind CSS](https://tailwindcss.com/):** Utility-first CSS framework for rapid UI development
- **[Shadcn/ui](https://ui.shadcn.com/):** Modern component library built on Radix UI

### **Infrastructure & DevOps**
- **[Render.com](https://render.com/):** Cloud platform for backend deployment and scaling
- **[Vercel](https://vercel.com/):** Frontend deployment with global CDN
- **S3-Compatible Storage:** Secure, scalable image storage
- **[Docker](https://www.docker.com/):** Containerized development environment

### **Monitoring & Security**
- **Health Check Endpoints:** Built-in monitoring for uptime tracking
- **Rate Limiting:** API protection against abuse with slowapi
- **Input Validation:** Comprehensive request validation with Pydantic
- **Error Handling:** Graceful error responses with detailed logging

## 🤖 Agentic LLM System

Mizual implements an intelligent agentic system that enhances user prompts for better image editing results:

```mermaid
graph LR
    subgraph "Agentic LLM Pipeline"
        UP[User Prompt] --> PA[Prompt Analyzer]
        PA --> PE[Prompt Enhancer]
        PE --> PO[Prompt Optimizer]
        PO --> EP[Enhanced Prompt]
    end
    
    subgraph "LLM Processing"
        EP --> GEMINI[Google Gemini]
        GEMINI --> AI[AI Enhancement]
        AI --> FP[Final Prompt]
    end
    
    subgraph "Image Generation"
        FP --> BFL[BFL Flux API]
        BFL --> RESULT[Enhanced Result]
    end
    
    style UP fill:#e3f2fd
    style EP fill:#f3e5f5
    style FP fill:#e8f5e8
    style RESULT fill:#fff3e0
```

### **How the Agentic System Works:**

1. **Prompt Analysis:** Analyzes user input for context and intent
2. **Intelligent Enhancement:** Uses Gemini to improve prompt clarity and specificity
3. **Optimization:** Tailors prompts for optimal BFL Flux API performance
4. **Result Generation:** Produces higher-quality edits through better prompts

### **Example Enhancement:**
```
User Input: "make it blue"
Enhanced:   "Transform the image with a vibrant blue color scheme, maintaining natural lighting and preserving important details while applying a cohesive blue tone throughout"
```

## 🎯 Implemented Features Deep Dive

### **Feature 1: Real-time Progress Tracking**

**Implementation:** Dynamic status updates with user-friendly messaging

```mermaid
stateDiagram-v2
    [*] --> pending: User submits edit
    pending --> enhancing_prompt: Celery task starts
    enhancing_prompt --> processing_image: Gemini enhancement complete
    processing_image --> uploading_result: BFL processing complete
    uploading_result --> completed: S3 upload complete
    
    pending --> failed: Validation error
    enhancing_prompt --> failed: Gemini API error
    processing_image --> failed: BFL API error
    uploading_result --> failed: S3 upload error
    
    completed --> [*]
    failed --> [*]
```

**Progress Stages:**
- **pending (10%):** "Your edit is queued..."
- **enhancing_prompt (25%):** "Enhancing your prompt with AI..."
- **processing_image (60%):** "Processing your edit..."
- **uploading_result (90%):** "Finalizing your edit..."
- **completed (100%):** "Edit completed successfully!"

**API Response:**
```json
{
  "status": "processing_image",
  "message": "Processing your edit...",
  "progress_percent": 60,
  "is_complete": false,
  "is_error": false
}
```

### **Feature 2: User Feedback System**

**Implementation:** Intuitive thumbs up/down feedback with conditional text input

```mermaid
graph TD
    A[User sees result] --> B[Thumbs Up/Down buttons]
    B -->|Thumbs Up| C[Submit positive feedback]
    B -->|Thumbs Down| D[Text box appears: What went wrong?]
    C --> E[Thank you message]
    D --> F[User explains issue]
    F --> G[Submit with feedback text]
    E --> H[Store in database]
    G --> H
    H --> I[Analytics & Insights]
```

**Database Schema:**
```sql
CREATE TABLE edit_feedback (
    id SERIAL PRIMARY KEY,
    edit_uuid VARCHAR UNIQUE NOT NULL,
    rating INTEGER CHECK (rating IN (0, 1)),  -- 0 = thumbs down, 1 = thumbs up
    feedback_text TEXT,  -- Required for thumbs down (0), optional for thumbs up (1)
    user_ip INET,
    created_at TIMESTAMP DEFAULT NOW()
);
```

**API Endpoints:**
- `POST /feedback/` - Submit feedback (rate limited: 5/minute)
- `GET /feedback/{edit_uuid}` - Retrieve feedback for edit

**Validation & Security:**
- ✅ One feedback per edit (unique constraint)
- ✅ Binary rating validation (0 or 1)
- ✅ Required text for negative feedback (rating = 0)
- ✅ Rate limiting to prevent spam
- ✅ Privacy-friendly (only IP, no user tracking)

### **Feature 3: Environment-Aware Database Migrations**

**Implementation:** Automated, safe database schema management

```mermaid
graph LR
    subgraph "Migration System"
        MS[Migration Script] --> ENV{Environment?}
        ENV -->|preview| PS[Preview Schema]
        ENV -->|production| PROD[Public Schema]
    end
    
    subgraph "Deployment Flow"
        DEPLOY[Render Deployment] --> MIGRATE[Run Migrations]
        MIGRATE --> START[Start Application]
    end
    
    subgraph "Safety Features"
        TRACK[Migration Tracking]
        ROLLBACK[Rollback Scripts]
        VALIDATE[Schema Validation]
    end
```

**Migration Features:**
- **Environment Detection:** Automatically targets correct schema (preview/public)
- **Idempotent:** Safe to run multiple times
- **Tracking:** Records applied migrations in `migration_history` table
- **Automated:** Runs on every deployment
- **Rollback Ready:** Comprehensive rollback procedures

## 🚀 Getting Started

### **Production Deployment**

Mizual is deployed on modern cloud infrastructure:

- **Frontend:** [https://mizual.vercel.app](https://mizual.vercel.app) (Vercel)
- **Backend API:** [https://mizual-backend.onrender.com](https://mizual-backend.onrender.com) (Render)
- **Database:** Supabase PostgreSQL
- **Storage:** S3-compatible cloud storage

### **Local Development**

#### **Prerequisites**
- [Docker](https://docs.docker.com/get-docker/) & [Docker Compose](https://docs.docker.com/compose/install/)
- [Node.js 18+](https://nodejs.org/) for frontend development
- API keys for external services

#### **Environment Setup**

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-org/mizual.git
   cd mizual
   ```

2. **Backend Environment Variables:**
   Create `mizual-backend/.env.local`:
   ```env
   # Environment
   ENVIRONMENT=preview
   
   # Database
   DATABASE_URL=postgresql://user:password@localhost:5432/mizual
   
   # AI Services
   BFL_API_KEY=your-bfl-api-key
   GEMINI_API_KEY=your-gemini-api-key
   
   # Storage
   S3_ENDPOINT=http://localhost:9000
   S3_ACCESS_KEY=minioadmin
   S3_SECRET_KEY=minioadmin
   S3_BUCKET_NAME=mizual-images
   
   # Redis
   REDIS_URL=redis://localhost:6379
   ```

3. **Frontend Environment Variables:**
   Create `mizual-frontend/.env.local`:
   ```env
   NEXT_PUBLIC_API_URL=http://localhost:10000
   ```

#### **Development Workflow**

1. **Start Backend Services:**
   ```bash
   cd mizual-backend
   docker-compose up -d  # Database, Redis, MinIO
   pip install -r requirements.txt
   python app.py  # FastAPI server
   celery -A src.tasks.celery worker --loglevel=info  # Worker
   ```

2. **Start Frontend:**
   ```bash
   cd mizual-frontend
   npm install
   npm run dev
   ```

3. **Access Development Environment:**
   - **Frontend:** [http://localhost:3000](http://localhost:3000)
   - **Backend API:** [http://localhost:10000/docs](http://localhost:10000/docs)
   - **MinIO Console:** [http://localhost:9001](http://localhost:9001)

## 📁 Project Structure

```
mizual/
├── mizual-backend/                 # FastAPI Backend
│   ├── src/                       # Source code
│   │   ├── llm/                   # LLM providers (Gemini, OpenAI)
│   │   ├── models.py              # Database models
│   │   ├── schemas.py             # Pydantic schemas
│   │   ├── crud.py                # Database operations
│   │   ├── tasks.py               # Celery tasks
│   │   ├── flux_api.py            # BFL API integration
│   │   ├── s3.py                  # S3 storage operations
│   │   └── status_messages.py     # Progress messages
│   ├── migrations/                # Database migrations
│   ├── app.py                     # FastAPI application
│   ├── migrate.py                 # Migration runner
│   ├── requirements.txt           # Python dependencies
│   ├── render.yaml               # Render deployment config
│   └── docker-compose.yml        # Local development services
│
├── mizual-frontend/               # Next.js Frontend
│   ├── app/                      # App Router pages
│   ├── components/               # React components
│   ├── lib/                      # Utilities
│   ├── public/                   # Static assets
│   ├── package.json              # Node dependencies
│   └── next.config.mjs           # Next.js configuration
│
├── future-implement.md           # Implementation roadmap
└── README.md                     # This file
```

## 🔌 API Documentation

### **Core Endpoints**

#### **Image Editing**
```http
POST /edit-image/
Content-Type: application/json

{
  "prompt": "make the sky more dramatic",
  "image_data": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQ..."
}

Response:
{
  "edit_id": "550e8400-e29b-41d4-a716-446655440000",
  "polling_url": "/edit/550e8400-e29b-41d4-a716-446655440000"
}
```

#### **Status Polling**
```http
GET /edit/{edit_uuid}

Response:
{
  "uuid": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing_image",
  "processing_stage": "processing_image",
  "message": "Processing your edit...",
  "progress_percent": 60,
  "is_complete": false,
  "is_error": false,
  "edited_image_url": null,
  "created_at": "2024-12-01T14:30:00Z"
}
```

#### **Feedback System**

**Thumbs Up (Simple):**
```http
POST /feedback/
Content-Type: application/json

{
  "edit_uuid": "550e8400-e29b-41d4-a716-446655440000",
  "rating": 1
}

Response:
{
  "success": true,
  "message": "Thank you for your feedback!",
  "feedback_id": 123
}
```

**Thumbs Down (With Required Text):**
```http
POST /feedback/
Content-Type: application/json

{
  "edit_uuid": "550e8400-e29b-41d4-a716-446655440000",
  "rating": 0,
  "feedback_text": "The colors look unnatural and the lighting is too harsh"
}

Response:
{
  "success": true,
  "message": "Thank you for helping us improve!",
  "feedback_id": 124
}
```

#### **Follow-up Image Editing**

**Create Follow-up Edit:**
```http
POST /edit-image/
Content-Type: application/json

{
  "prompt": "add more dramatic lighting",
  "image_data": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQ...",
  "parent_edit_uuid": "550e8400-e29b-41d4-a716-446655440000"
}

Response:
{
  "edit_id": "660f9500-f39c-52e5-b827-557766551111",
  "polling_url": "/edit/660f9500-f39c-52e5-b827-557766551111"
}
```

**Get Chain History:**
```http
GET /chain/{edit_uuid}

Response:
{
  "edit_uuid": "660f9500-f39c-52e5-b827-557766551111",
  "chain_length": 3,
  "chain_history": [
    {
      "edit": { "uuid": "edit-1", "prompt": "make it blue", "chain_position": 1 },
      "parent_edit_uuid": null
    },
    {
      "edit": { "uuid": "edit-2", "prompt": "add flowers", "chain_position": 2 },
      "parent_edit_uuid": "edit-1"
    },
    {
      "edit": { "uuid": "edit-3", "prompt": "dramatic lighting", "chain_position": 3 },
      "parent_edit_uuid": "edit-2"
    }
  ]
}
```

**Chain Analytics:**
```http
GET /analytics/chains

Response:
{
  "success": true,
  "analytics": {
    "total_chains": 156,
    "average_chain_length": 2.3
  }
}
```

#### **Health Check**
```http
GET /health

Response:
{
  "status": "ok",
  "message": "Service is running"
}
```

### **Rate Limits**
- **Image editing:** 10 requests per minute
- **Status polling:** 60 requests per minute  
- **Feedback submission:** 5 requests per minute
- **Chain history:** 10 requests per minute
- **Chain analytics:** 5 requests per minute
- **Health check:** No limit

### **Error Responses**
```json
{
  "detail": "Edit not found",
  "error_code": "EDIT_NOT_FOUND",
  "timestamp": "2024-12-01T14:30:00Z"
}
```

### **Status Codes**
- **200:** Success
- **400:** Bad Request (validation error)
- **404:** Resource not found
- **409:** Conflict (duplicate feedback)
- **422:** Unprocessable Entity (invalid input)
- **429:** Rate limit exceeded
- **500:** Internal server error

## 🚀 Deployment & Infrastructure

### **Production Architecture**

```mermaid
graph TB
    subgraph "CDN & Frontend"
        VERCEL[Vercel Frontend]
        CDN[Global CDN]
    end
    
    subgraph "Backend Services"
        RENDER[Render Backend]
        CELERY[Celery Workers]
    end
    
    subgraph "Managed Services"
        SUPABASE[(Supabase PostgreSQL)]
        UPSTASH[Upstash Redis]
        S3[S3 Storage]
    end
    
    subgraph "AI Services"
        GEMINI[Google Gemini]
        BFL[BFL Flux API]
    end
    
    subgraph "Monitoring"
        HEALTH[Health Checks]
        LOGS[Centralized Logging]
    end
    
    CDN --> VERCEL
    VERCEL --> RENDER
    RENDER --> SUPABASE
    RENDER --> UPSTASH
    RENDER --> S3
    CELERY --> GEMINI
    CELERY --> BFL
    RENDER --> HEALTH
    CELERY --> LOGS
    
    style VERCEL fill:#e1f5fe
    style RENDER fill:#f3e5f5
    style SUPABASE fill:#fce4ec
    style GEMINI fill:#e8f5e8
    style BFL fill:#e8f5e8
```

### **Deployment Features**

- **🌍 Global CDN:** Vercel's edge network for fast frontend delivery
- **⚡ Auto-scaling:** Render automatically scales backend based on demand
- **🔄 Zero-downtime deployments:** Rolling updates with health checks
- **📊 Environment separation:** Isolated dev/staging/production environments
- **🗄️ Automated migrations:** Database schema updates on every deployment
- **📈 Monitoring:** Health checks, error tracking, and performance monitoring

### **Environment Configuration**

#### **Development**
- **Frontend:** `localhost:3000` (Next.js dev server)
- **Backend:** `localhost:10000` (FastAPI with hot reload)
- **Database:** Local PostgreSQL or Supabase preview
- **Storage:** Local MinIO container
- **Queue:** Local Redis container

#### **Production**
- **Frontend:** `mizual.vercel.app` (Vercel)
- **Backend:** `mizual-backend.onrender.com` (Render)
- **Database:** Supabase PostgreSQL (public schema)
- **Storage:** S3-compatible cloud storage
- **Queue:** Upstash Redis

## 🔧 Development & Contribution

### **Code Quality**
- **TypeScript:** Full type safety in frontend
- **Pydantic:** Runtime validation in backend
- **ESLint & Prettier:** Code formatting and linting
- **Pre-commit hooks:** Automated code quality checks

### **Testing Strategy**
- **Unit tests:** Core business logic
- **Integration tests:** API endpoints
- **E2E tests:** Critical user flows
- **Load testing:** Performance validation

### **Contributing Guidelines**

1. **Fork the repository** and create a feature branch
2. **Follow code standards** (TypeScript, Python type hints)
3. **Add tests** for new functionality
4. **Update documentation** as needed
5. **Submit a pull request** with clear description

### **Performance Optimizations**

- **Image optimization:** WebP conversion, compression
- **Caching:** Redis caching for frequent queries
- **Database indexing:** Optimized queries with proper indexes
- **CDN:** Static asset delivery via global CDN
- **Lazy loading:** Progressive image loading in frontend

## 📊 Monitoring & Analytics

### **Health Monitoring**
```http
GET /health
# Returns service status for monitoring tools
```

### **Key Metrics Tracked**
- **Response times:** API endpoint performance
- **Success rates:** Edit completion rates
- **User engagement:** Session duration, edit frequency
- **Error rates:** Failed edits, API errors
- **Resource usage:** CPU, memory, database connections

### **Feedback Analytics**
- **User satisfaction:** Rating distribution
- **Feature usage:** Most popular edit types
- **Performance insights:** Processing time analysis
- **Quality metrics:** Feedback sentiment analysis

## 🛡️ Security & Privacy

### **Data Protection**
- **Minimal data collection:** Only essential information stored
- **Image privacy:** Automatic cleanup of processed images
- **No user tracking:** Privacy-first approach
- **Secure storage:** Encrypted data transmission and storage

### **API Security**
- **Rate limiting:** Protection against abuse
- **Input validation:** Comprehensive request validation
- **Error handling:** No sensitive information in error responses
- **CORS configuration:** Restricted cross-origin requests

---

## System Design

```mermaid
graph TD
    subgraph User
        UserBrowser[User Browser]
    end

    subgraph Docker Host
        subgraph Docker Network
            Frontend(Frontend Service)
            BackendAPI(Backend API Service)
            Worker(Celery Worker Service)
            DB(PostgreSQL Service)
            MinIO(MinIO Service)
            Redis(Redis Service)
        end

        UserBrowser -- Port 3000 --> Frontend
        UserBrowser -- Port 8000 --> BackendAPI
        UserBrowser -- Port 9000/9001 --> MinIO
    end

    subgraph External
        BFLAI[BFL AI API]
    end

    Frontend -- HTTP --> BackendAPI
    BackendAPI -- DB Connection --> DB
    BackendAPI -- S3 API --> MinIO
    BackendAPI -- Redis Protocol --> Redis
    BackendAPI -- Task Queue --> Worker
    Worker -- DB Connection --> DB
    Worker -- S3 API --> MinIO
    Worker -- HTTP --> BFLAI
    Worker -- Redis Protocol --> Redis
```

The system is designed as a containerized, distributed application leveraging Docker Compose for local development and deployment.

*   **Containerization:** Each core component (Frontend, Backend API, Database, Object Storage, Message Broker, Worker) runs in its own Docker container, ensuring isolation and portability.
*   **Service Discovery:** Within the Docker network, services communicate using their service names (e.g., `web`, `db`, `redis`, `minio`).
*   **Port Mapping:** Essential services (Frontend, Backend API, MinIO Console) have their internal container ports mapped to host machine ports, allowing external access (e.g., via a web browser).
*   **Data Persistence:** Docker volumes are used for the PostgreSQL database (`postgres_data`) and MinIO storage (`minio_data`) to ensure data persists across container restarts.
*   **Scalability Considerations (Conceptual):**
    *   **Backend API:** Can be scaled horizontally by running multiple instances behind a load balancer.
    *   **Celery Worker:** Can be scaled horizontally by adding more worker instances to process tasks concurrently.
    *   **Redis/PostgreSQL/MinIO:** Can be replaced with managed cloud services or clustered deployments for high availability and scalability in production environments.
*   **Asynchronous Processing:** The use of Celery and Redis offloads long-running image processing tasks from the main API thread, improving API responsiveness and user experience.
*   **External API Dependency:** The system relies on the external BFL AI API for the core image editing functionality. Robust error handling and retry mechanisms are implemented in the worker to manage potential API failures.
*   **Environment Configuration:** Environment variables are used for sensitive information (API keys, database credentials) and configurable parameters (S3 bucket names, API URLs), promoting flexibility and security.

