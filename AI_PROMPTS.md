# AI Prompts Used for This Project

## Initial Project Request

**User Request:**
```
Role: You are a Senior AI Engineer building a Multi-tenant Internal Knowledge Assistant.

Task: Create a FastAPI backend that implements a RAG system with the following requirements:

1. Data Model: Use SQLAlchemy with a schema that enforces tenant_id on every table (Tenants, Documents, AI_Logs).
2. Vector DB: Use pgvector for storing document embeddings. All semantic searches must include a WHERE tenant_id = :tid filter.
3. Core API:
   - POST /ingest: Chunk text and store embeddings.
   - POST /query: Semantic search + LLM response.
4. Caching: Use Redis to cache identical queries for the same tenant to save costs.
5. Safety: System prompt must force the AI to cite sources and refuse to answer if the context is missing.
6. Structure: Use a clean service-layer pattern.

Tech Stack: Python, FastAPI, SQLAlchemy, pgvector, Redis, and LangChain (or direct OpenAI calls).

Output: Give me the main.py, database.py, and models.py that are production-ready.
```

## Spec Creation

**Approach:** Used Kiro's spec-driven development workflow to create:
- Requirements document with 12 detailed requirements
- Design document with 20 correctness properties
- Implementation plan with 8 main tasks

## Simplification Request

**User Request:**
```
Great spec. Please start implementing but SIMPLIFY for speed.
- Skip all Property-based testing for now.
- Keep the service layer simple (you can put logic in services.py or directly in main.py if it's short).
- Start by executing Task 1 (Setup) and Task 2 (DB Models). Show me the code when done.
```

## Docker Setup Request

**User Request:**
```
อะไรที่ต้องใช้ docker ให้ใช้ได้เลย ใช้ docker compose ก็ได้ ส่วน api key เดี๋ยวทำทีหลัง
```

**Response:** Created docker-compose.yml with PostgreSQL (pgvector) and Redis services.

## Mock Mode Implementation

**User Request:**
```
Task: Implement Deterministic Mocking for OpenAI APIs (No Cost Mode)

Context: I need to run this backend without a real OpenAI API key for the exam, but the Data Flow (Vector Search) must still work. If I ingest the text "Hello", it must produce the SAME embedding vector every time so that pgvector can match it.

Action: Modify backend/services.py to include a "Mock Mode".

1. Update get_embedding(text):
   - Check if os.getenv("OPENAI_API_KEY") starts with "mock" or is None.
   - If Mock:
     - Use hashlib.sha256(text.encode()).hexdigest() to get a seed.
     - random.seed(seed) (Make it deterministic!)
     - Generate a list of 1536 random floats (Must match text-embedding-ada-002 dimension).
     - Return the list.
   - If Real: Keep the existing OpenAI call.

2. Update get_llm_response(query, context):
   - If Mock: Return a JSON string with mock answer and sources.
   - If Real: Keep the existing OpenAI call.

3. Update .env setup:
   - Ensure the code doesn't crash if OPENAI_API_KEY is set to "mock-key".

Goal: I want to be able to hit /ingest and /query endpoints immediately after this change and see the data flow working without paying OpenAI.
```

**Implementation:**
- Added MOCK_MODE detection based on API key
- Implemented deterministic embedding generation using SHA256 hash as seed
- Created mock LLM responses with source citations
- Updated .env.example to use "mock-key" by default
- Created MOCK_MODE.md documentation

## Key Design Decisions

### 1. Tenant Isolation
- Every table has tenant_id with foreign key constraints
- All queries include WHERE tenant_id = :tid filter
- Cache keys include tenant_id to prevent cross-tenant pollution

### 2. Vector Search
- Used pgvector extension for PostgreSQL
- Cosine distance operator (<=>)
- 1536 dimensions matching OpenAI text-embedding-ada-002

### 3. Caching Strategy
- Redis cache key format: `query:{tenant_id}:{sha256(query)[:16]}`
- TTL: 3600 seconds (1 hour)
- Reduces OpenAI API costs for repeated queries

### 4. Mock Mode
- Deterministic embeddings using SHA256 hash as seed
- Same text always produces same embedding vector
- Enables testing without OpenAI API costs
- Perfect for exams and demonstrations

### 5. Service Layer
- EmbeddingService: OpenAI embeddings with retry logic
- CacheService: Redis operations
- IngestService: Document chunking and storage
- QueryService: Semantic search and LLM integration

### 6. Error Handling
- Global exception handler in FastAPI
- Proper HTTP status codes (400, 404, 500)
- Logging for all operations
- Transaction rollback on failures

## Testing Approach

### Mock Mode Testing
```bash
# 1. Start Docker services
docker-compose up -d

# 2. Create .env with mock-key
copy .env.example .env

# 3. Run application
uvicorn main:app --reload

# 4. Test endpoints
curl -X POST "http://localhost:8000/ingest" ...
curl -X POST "http://localhost:8000/query" ...
```

### Real Mode Testing
```bash
# Update .env with real OpenAI API key
OPENAI_API_KEY=sk-real-key-here

# Restart application
uvicorn main:app --reload
```

## Lessons Learned

1. **Deterministic Testing**: Using hash-based seeding for embeddings enables reproducible tests without API costs
2. **Tenant Isolation**: Foreign key constraints and indexed tenant_id columns are critical for multi-tenant security
3. **Caching**: Including tenant_id in cache keys prevents security vulnerabilities
4. **Mock Mode**: Essential for development, testing, and exam environments
5. **Docker Compose**: Simplifies setup with PostgreSQL + pgvector + Redis in one command

## Future Enhancements

1. Add authentication middleware (JWT or API keys)
2. Implement rate limiting per tenant
3. Add Alembic migrations for schema versioning
4. Create comprehensive test suite with pytest
5. Add monitoring and metrics (Prometheus/Grafana)
6. Implement async batch processing for large documents
7. Add support for multiple embedding models
8. Create admin API for tenant management
