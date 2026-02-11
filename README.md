# Multi-tenant RAG System

A production-ready Multi-tenant RAG (Retrieval-Augmented Generation) system built with FastAPI, PostgreSQL (pgvector), Redis, and OpenAI. Features strict tenant isolation, intelligent caching, and mandatory source citations.

## 📁 Project Structure

```
/
├── src/
│   ├── backend/          # FastAPI application
│   │   ├── main.py       # API routes and endpoints
│   │   ├── models.py     # SQLAlchemy models
│   │   ├── database.py   # Database connection
│   │   ├── services.py   # Business logic services
│   │   ├── Dockerfile    # Backend container
│   │   ├── requirements.txt
│   │   ├── .env.example
│   │   └── test_e2e.py   # End-to-end tests
│   └── infra/            # Infrastructure (legacy)
├── docker-compose.yml    # Docker services configuration
├── test_docker_startup.py # Startup verification script
├── README.md             # This file
├── AI_PROMPTS.md         # AI prompts used for development
└── MOCK_MODE.md          # Mock mode documentation
```

## 🎯 Approach & Design Decisions

### Architecture
- **Service Layer Pattern**: Clean separation between API routes, business logic, and data access
- **Async-First**: Built with async SQLAlchemy and FastAPI for high performance
- **Multi-tenancy**: Strict tenant isolation enforced at database level with foreign keys and indexes

### Key Features
1. **Tenant Isolation**: Every table has `tenant_id` with foreign key constraints. All queries include `WHERE tenant_id = :tid` filter
2. **Vector Search**: pgvector extension with cosine similarity for semantic search (1536 dimensions matching OpenAI ada-002)
3. **Smart Caching**: Redis cache with tenant-scoped keys (`query:{tenant_id}:{hash}`) to prevent cross-tenant pollution
4. **Mock Mode**: Deterministic embeddings using SHA256 hash as seed - enables testing without OpenAI costs
5. **AI Safety**: System prompts enforce source citations and refuse to answer without context

### Trade-offs
- **Simplicity over Abstraction**: Single `services.py` file instead of complex service hierarchy for faster development
- **Mock Mode**: Sacrifices AI quality for cost-free testing and development
- **No Migrations**: Uses `create_all()` instead of Alembic for rapid prototyping (would add migrations for production)
- **Synchronous Docker Build**: Backend waits for DB health checks (adds ~10s startup time but ensures reliability)

### What I Would Improve with More Time
1. **Authentication**: Add JWT-based auth middleware with tenant validation
2. **Rate Limiting**: Per-tenant rate limiting to prevent abuse
3. **Monitoring**: Prometheus metrics + Grafana dashboards
4. **Testing**: Comprehensive pytest suite with property-based tests
5. **Migrations**: Alembic for schema versioning
6. **Batch Processing**: Async queue for large document ingestion
7. **Admin API**: Tenant management endpoints
8. **Observability**: Structured logging with correlation IDs

## 🚀 Runbook

### Prerequisites
- Docker Desktop installed and running
- Docker Compose V2 (comes with Docker Desktop)
- Python 3.11+ (for local development only)

### One-Command Startup

```bash
docker compose up --build
```

This command will:
1. Build the FastAPI backend image
2. Start PostgreSQL 15 with pgvector extension
3. Start Redis cache
4. Initialize database schema automatically
5. Start backend API on port 8000

Wait ~30 seconds for all services to be healthy, then access:
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

### Environment Variables

The system uses these environment variables (configured in `docker-compose.yml`):

```bash
# Database
DATABASE_URL=postgresql+asyncpg://postgres:password@postgres:5432/rag_system

# Redis
REDIS_URL=redis://redis:6379/0

# OpenAI (use "mock-key" for testing without costs)
OPENAI_API_KEY=mock-key

# Configuration
EMBEDDING_MODEL=text-embedding-ada-002
LLM_MODEL=gpt-4
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
CACHE_TTL=3600
TOP_K_RESULTS=5
```

### Sample .env.example

See `src/backend/.env.example` for local development configuration.

### Health Checks

The system includes built-in health checks:

```bash
# Check if system is ready
curl http://localhost:8000/health

# Expected response:
# {"status": "healthy", "service": "multi-tenant-rag"}
```

### How to Verify the System Works

#### Method 1: Automated Test Script

```bash
python test_docker_startup.py
```

This script will:
- Clean up any existing containers
- Check port availability
- Build and start all services
- Poll health endpoint until ready
- Show logs if anything fails

#### Method 2: Manual Testing

**Step 1: Create a Tenant**
```bash
docker exec -it rag_postgres psql -U postgres -d rag_system -c "INSERT INTO tenants (id, name) VALUES ('11111111-1111-1111-1111-111111111111', 'Test Company');"
```

**Step 2: Ingest a Document**
```bash
curl -X POST "http://localhost:8000/ingest" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "11111111-1111-1111-1111-111111111111",
    "content": "Python is a high-level programming language. It is widely used for web development, data science, machine learning, and automation. Python has a simple syntax that emphasizes readability.",
    "metadata": {"title": "Python Introduction", "source": "test"}
  }'
```

Expected response:
```json
{
  "document_id": "some-uuid",
  "chunks_created": 1,
  "status": "success"
}
```

**Step 3: Query the System**
```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "11111111-1111-1111-1111-111111111111",
    "query": "What is Python used for?",
    "top_k": 3
  }'
```

Expected response:
```json
{
  "answer": "MOCK ANSWER: Based on the provided context, Python is a high-level programming language... [Sources: doc-uuid]",
  "sources": [
    {
      "document_id": "doc-uuid",
      "chunk_text": "Python is a high-level programming language...",
      "similarity_score": 0.95
    }
  ],
  "cached": false
}
```

**Step 4: Verify Caching**
```bash
# Run the same query again
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "11111111-1111-1111-1111-111111111111",
    "query": "What is Python used for?",
    "top_k": 3
  }'
```

Expected: `"cached": true` in response

### Example API Calls Demonstrating Core Flow

**Complete End-to-End Flow:**

```bash
# 1. Health check
curl http://localhost:8000/health

# 2. Create tenant (via database)
docker exec -it rag_postgres psql -U postgres -d rag_system -c \
  "INSERT INTO tenants (id, name) VALUES ('22222222-2222-2222-2222-222222222222', 'Acme Corp') RETURNING id, name;"

# 3. Ingest multiple documents
curl -X POST "http://localhost:8000/ingest" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "22222222-2222-2222-2222-222222222222",
    "content": "FastAPI is a modern web framework for building APIs with Python. It is fast, easy to use, and includes automatic API documentation.",
    "metadata": {"title": "FastAPI Guide"}
  }'

curl -X POST "http://localhost:8000/ingest" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "22222222-2222-2222-2222-222222222222",
    "content": "Docker is a platform for developing, shipping, and running applications in containers. Containers are lightweight and portable.",
    "metadata": {"title": "Docker Basics"}
  }'

# 4. Query with semantic search
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "22222222-2222-2222-2222-222222222222",
    "query": "How do I build APIs?",
    "top_k": 5
  }'

# 5. Verify tenant isolation (query with different tenant - should get no results)
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "11111111-1111-1111-1111-111111111111",
    "query": "How do I build APIs?",
    "top_k": 5
  }'
```

### Stopping the System

```bash
# Stop all services
docker compose down

# Stop and remove all data (volumes)
docker compose down -v
```

### Troubleshooting

**Port already in use:**
```bash
# Check what's using the port
netstat -ano | findstr :8000

# Kill the process or change port in docker-compose.yml
```

**Database connection errors:**
```bash
# Check if PostgreSQL is healthy
docker compose ps

# View logs
docker compose logs postgres

# Wait 10-15 seconds after startup for DB initialization
```

**Backend not starting:**
```bash
# View backend logs
docker compose logs backend

# Check if dependencies are healthy
docker compose ps
```

**Mock Mode not working:**
```bash
# Verify OPENAI_API_KEY is set to "mock-key" in docker-compose.yml
# Check backend logs for "🔧 MOCK MODE ENABLED" message
docker compose logs backend | findstr "MOCK"
```

## 📚 Additional Documentation

- **MOCK_MODE.md**: Detailed guide on using the system without OpenAI API costs
- **AI_PROMPTS.md**: Complete record of AI prompts used to build this system
- **setup.md**: Quick setup guide (Thai language)

## 🔧 Tech Stack

- **API Framework**: FastAPI (async support, automatic OpenAPI docs)
- **ORM**: SQLAlchemy 2.0 (with async support)
- **Vector Database**: pgvector extension for PostgreSQL
- **Cache**: Redis (with async client)
- **LLM Integration**: OpenAI API (with mock mode for testing)
- **Embedding Model**: OpenAI text-embedding-ada-002
- **Database**: PostgreSQL 15+ with pgvector extension
- **Containerization**: Docker + Docker Compose

## 📄 License

MIT License

## Features

- 🔒 **Tenant Isolation**: Strict data separation at database level with tenant_id enforcement
- 🚀 **Vector Search**: Semantic search using pgvector with cosine similarity
- 💾 **Smart Caching**: Redis-based query caching to reduce LLM API costs
- 📚 **Source Citations**: AI responses always cite source documents
- ⚡ **Async Architecture**: Built with async SQLAlchemy and FastAPI for high performance
- 🛡️ **Safety First**: System prompts enforce context-only responses

## Tech Stack

- **API**: FastAPI
- **Database**: PostgreSQL 15+ with pgvector extension
- **Cache**: Redis
- **LLM**: OpenAI GPT-4
- **Embeddings**: OpenAI text-embedding-ada-002
- **ORM**: SQLAlchemy 2.0 (async)

## Prerequisites

- Python 3.11+
- PostgreSQL 15+ with pgvector extension
- Redis
- OpenAI API key

## Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd multi-tenant-rag-system
```

2. **Install dependencies**
```bash
cd src/backend
pip install -r requirements.txt
```

3. **Set up infrastructure with Docker**
```bash
cd ../infra
docker-compose up -d
```

This will start:
- PostgreSQL 15 with pgvector extension (port 5432)
- Redis (port 6379)

4. **Configure environment variables**
```bash
cd ../backend
copy .env.example .env
# Edit .env if needed (default uses mock-key for testing)
```

## 🚀 Quick Start (5 Minutes)

### 1. Start Infrastructure
```bash
cd src/infra
docker-compose up -d
```

### 2. Setup Backend
```bash
cd ../backend
pip install -r requirements.txt
copy .env.example .env
```

### 3. Run Application
```bash
uvicorn main:app --reload
```

### 4. Test
Open browser: http://localhost:8000/docs

**Note:** Default configuration uses Mock Mode (no OpenAI API key required). See MOCK_MODE.md for details.

## Running the Application

**Development mode:**
```bash
cd src/backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Production mode:**
```bash
cd src/backend
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

The API will be available at `http://localhost:8000`

Interactive API docs: `http://localhost:8000/docs`

## API Usage

### 1. Create a Tenant (Manual - via database)

First, create a tenant in the database:
```sql
INSERT INTO tenants (id, name) VALUES (gen_random_uuid(), 'Acme Corp');
```

### 2. Ingest Documents

```bash
curl -X POST "http://localhost:8000/ingest" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "your-tenant-uuid",
    "content": "Your document content here...",
    "metadata": {
      "title": "Document Title",
      "source": "https://example.com"
    }
  }'
```

Response:
```json
{
  "document_id": "doc-uuid",
  "chunks_created": 5,
  "status": "success"
}
```

### 3. Query Documents

```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "your-tenant-uuid",
    "query": "What is the main topic?",
    "top_k": 5
  }'
```

Response:
```json
{
  "answer": "The main topic is... [Source: doc-uuid]",
  "sources": [
    {
      "document_id": "doc-uuid",
      "chunk_text": "Relevant text chunk...",
      "similarity_score": 0.92
    }
  ],
  "cached": false
}
```

### 4. Health Check

```bash
curl http://localhost:8000/health
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        FastAPI Layer                         │
│                 (src/backend/main.py)                        │
└────────────────┬────────────────────────┬───────────────────┘
                 │                        │
                 ▼                        ▼
┌────────────────────────────┐  ┌──────────────────────────┐
│    Ingest Service          │  │    Query Service         │
│  - Document chunking       │  │  - Cache lookup          │
│  - Embedding generation    │  │  - Semantic search       │
│  - Storage orchestration   │  │  - LLM interaction       │
└────────┬───────────────────┘  └──────┬───────────────────┘
         │                              │
         ▼                              ▼
┌────────────────────────────────────────────────────────────┐
│                    Data Access Layer                        │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │ Vector Store │  │ Cache Service│  │ Database Layer  │  │
│  │  (pgvector)  │  │   (Redis)    │  │ (SQLAlchemy)    │  │
│  └──────────────┘  └──────────────┘  └─────────────────┘  │
└────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────────┐
│  PostgreSQL  │    │    Redis     │    │   PostgreSQL     │
│  (pgvector)  │    │              │    │  (metadata)      │
└──────────────┘    └──────────────┘    └──────────────────┘
```

## Database Schema

- **tenants**: Tenant information
- **documents**: Full document storage with tenant_id
- **document_chunks**: Text chunks with embeddings (Vector(1536))
- **ai_logs**: Query and response logging

All tables enforce tenant_id foreign keys and indexes for isolation and performance.

## Configuration

Environment variables in `.env`:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/rag_system

# Redis
REDIS_URL=redis://localhost:6379/0

# OpenAI
OPENAI_API_KEY=sk-your-api-key-here

# Application Settings
EMBEDDING_MODEL=text-embedding-ada-002
LLM_MODEL=gpt-4
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
CACHE_TTL=3600
TOP_K_RESULTS=5
```

## Key Features Explained

### Tenant Isolation
Every database operation includes a `tenant_id` filter. Vector searches use:
```sql
WHERE tenant_id = :tenant_id
ORDER BY embedding <=> :query_embedding
```

### Caching Strategy
Cache keys include tenant_id to prevent cross-tenant pollution:
```
query:{tenant_id}:{sha256(query)[:16]}
```

### AI Safety
System prompt enforces:
- Context-only responses (no general knowledge)
- Mandatory source citations
- Explicit refusal when context is insufficient

## Development

**Project structure:**
```
src/
├── backend/
│   ├── main.py           # FastAPI application and routes
│   ├── database.py       # Database connection and session management
│   ├── models.py         # SQLAlchemy models
│   ├── services.py       # Business logic (Ingest, Query, Cache, Embedding)
│   ├── requirements.txt  # Python dependencies
│   ├── .env.example      # Environment variable template
│   └── test_e2e.py       # End-to-end tests
└── infra/
    └── docker-compose.yml # Docker services (PostgreSQL, Redis)
```

## Troubleshooting

**pgvector extension not found:**
```bash
# Install pgvector for your PostgreSQL version
# Then in psql:
CREATE EXTENSION vector;
```

**Redis connection error:**
```bash
# Start Redis
redis-server
```

**OpenAI API errors:**
- Check your API key is valid
- Ensure you have sufficient credits
- Check rate limits

## License

MIT License
