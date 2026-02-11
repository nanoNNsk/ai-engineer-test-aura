# Design Document: Multi-tenant RAG System

## Overview

This design describes a production-ready Multi-tenant RAG (Retrieval-Augmented Generation) system built with FastAPI, SQLAlchemy, pgvector, and Redis. The system enforces strict tenant isolation at every layer, optimizes costs through intelligent caching, and ensures AI safety through mandatory source citations.

The architecture follows a clean service-layer pattern with clear separation between API routes, business logic, data access, and external integrations.

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        FastAPI Layer                         │
│                    (main.py - Routes)                        │
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

### Technology Stack

- **API Framework**: FastAPI (async support, automatic OpenAPI docs)
- **ORM**: SQLAlchemy 2.0 (with async support)
- **Vector Database**: pgvector extension for PostgreSQL
- **Cache**: Redis (with async client)
- **LLM Integration**: LangChain or direct OpenAI API calls
- **Embedding Model**: OpenAI text-embedding-ada-002
- **Database**: PostgreSQL 15+ with pgvector extension

## Components and Interfaces

### 1. API Layer (main.py)

**Responsibilities:**
- Define FastAPI application and routes
- Request validation using Pydantic models
- Response formatting
- Error handling middleware
- Dependency injection for services

**Key Endpoints:**

```python
POST /ingest
Request:
{
  "tenant_id": "uuid",
  "content": "string",
  "metadata": {"title": "string", "source": "string"}  # optional
}
Response:
{
  "document_id": "uuid",
  "chunks_created": int,
  "status": "success"
}

POST /query
Request:
{
  "tenant_id": "uuid",
  "query": "string",
  "top_k": int  # optional, default 5
}
Response:
{
  "answer": "string",
  "sources": [
    {
      "document_id": "uuid",
      "chunk_text": "string",
      "similarity_score": float
    }
  ],
  "cached": boolean
}
```

### 2. Database Layer (database.py, models.py)

**Responsibilities:**
- Database connection management
- Session lifecycle management
- SQLAlchemy model definitions
- Migration support (Alembic)

**Models:**

```python
class Tenant(Base):
    __tablename__ = "tenants"
    id: UUID (primary key)
    name: str
    created_at: datetime

class Document(Base):
    __tablename__ = "documents"
    id: UUID (primary key)
    tenant_id: UUID (foreign key, indexed, not null)
    content: Text
    metadata: JSONB
    created_at: datetime
    
class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    id: UUID (primary key)
    document_id: UUID (foreign key)
    tenant_id: UUID (foreign key, indexed, not null)
    chunk_text: Text
    chunk_index: int
    embedding: Vector(1536)  # pgvector type
    created_at: datetime

class AILog(Base):
    __tablename__ = "ai_logs"
    id: UUID (primary key)
    tenant_id: UUID (foreign key, indexed, not null)
    query: Text
    response: Text
    cached: bool
    timestamp: datetime
    sources_used: JSONB
```

**Database Connection:**
- Use async SQLAlchemy engine
- Connection pooling with configurable pool size
- Automatic session management via FastAPI dependencies

### 3. Ingest Service

**Responsibilities:**
- Document chunking with overlap
- Embedding generation via OpenAI API
- Transactional storage of documents and embeddings
- Error handling and rollback

**Interface:**

```python
class IngestService:
    def __init__(self, db_session, vector_store, embedding_client):
        pass
    
    async def ingest_document(
        self, 
        tenant_id: UUID, 
        content: str, 
        metadata: dict = None
    ) -> IngestResult:
        """
        1. Validate tenant exists
        2. Create Document record
        3. Chunk the content
        4. Generate embeddings for each chunk
        5. Store chunks and embeddings in DocumentChunk table
        6. Return document_id and chunk count
        """
        pass
```

**Chunking Strategy:**
- Use LangChain's RecursiveCharacterTextSplitter
- Chunk size: 1000 characters (configurable)
- Overlap: 200 characters (configurable)
- Preserve sentence boundaries when possible

### 4. Query Service

**Responsibilities:**
- Cache lookup and management
- Query embedding generation
- Semantic search with tenant filtering
- LLM prompt construction and execution
- Response formatting with source citations

**Interface:**

```python
class QueryService:
    def __init__(
        self, 
        db_session, 
        vector_store, 
        cache_service, 
        llm_client
    ):
        pass
    
    async def query(
        self, 
        tenant_id: UUID, 
        query: str, 
        top_k: int = 5
    ) -> QueryResult:
        """
        1. Check cache for query result
        2. If cache hit, return cached result
        3. If cache miss:
           a. Generate query embedding
           b. Perform semantic search with tenant_id filter
           c. If no results, return "cannot answer" response
           d. If results found, construct prompt with context
           e. Call LLM with safety prompt
           f. Parse response and extract citations
           g. Cache the result
           h. Log to AI_Logs table
        4. Return answer with sources
        """
        pass
```

**System Prompt Template:**

```
You are a helpful assistant that answers questions based ONLY on the provided context.

RULES:
1. You MUST cite the source document for every claim you make
2. Use the format [Source: doc_id] after each cited fact
3. If the context does not contain information to answer the question, you MUST respond with: "I cannot answer this question based on the available documents."
4. Do NOT use your general knowledge - only use the provided context
5. Be concise and accurate

CONTEXT:
{context}

QUESTION:
{query}

ANSWER:
```

### 5. Vector Store Service

**Responsibilities:**
- Embedding storage and retrieval using pgvector
- Similarity search with tenant isolation
- Index management

**Interface:**

```python
class VectorStoreService:
    def __init__(self, db_session):
        pass
    
    async def store_embeddings(
        self,
        tenant_id: UUID,
        document_id: UUID,
        chunks: List[ChunkData]
    ) -> None:
        """
        Store document chunks with embeddings in DocumentChunk table
        """
        pass
    
    async def similarity_search(
        self,
        tenant_id: UUID,
        query_embedding: List[float],
        top_k: int = 5
    ) -> List[SearchResult]:
        """
        Perform cosine similarity search with tenant_id filter
        SQL: SELECT * FROM document_chunks 
             WHERE tenant_id = :tid 
             ORDER BY embedding <=> :query_vec 
             LIMIT :top_k
        """
        pass
```

**pgvector Configuration:**
- Use cosine distance operator: `<=>`
- Create index: `CREATE INDEX ON document_chunks USING ivfflat (embedding vector_cosine_ops)`
- Index parameters tuned for dataset size

### 6. Cache Service

**Responsibilities:**
- Redis connection management
- Cache key generation (tenant_id + query hash)
- TTL management
- Cache invalidation

**Interface:**

```python
class CacheService:
    def __init__(self, redis_client):
        pass
    
    async def get_cached_query(
        self, 
        tenant_id: UUID, 
        query: str
    ) -> Optional[QueryResult]:
        """
        Generate cache key: f"query:{tenant_id}:{hash(query)}"
        Retrieve from Redis if exists
        """
        pass
    
    async def cache_query_result(
        self,
        tenant_id: UUID,
        query: str,
        result: QueryResult,
        ttl: int = 3600
    ) -> None:
        """
        Store query result in Redis with TTL
        """
        pass
```

**Cache Key Strategy:**
- Format: `query:{tenant_id}:{sha256(query)[:16]}`
- TTL: 1 hour (configurable)
- Serialization: JSON

### 7. Embedding Client

**Responsibilities:**
- OpenAI API integration
- Batch embedding generation
- Rate limiting and retry logic
- Error handling

**Interface:**

```python
class EmbeddingClient:
    def __init__(self, api_key: str, model: str = "text-embedding-ada-002"):
        pass
    
    async def generate_embeddings(
        self, 
        texts: List[str]
    ) -> List[List[float]]:
        """
        Generate embeddings using OpenAI API
        Handle rate limits with exponential backoff
        """
        pass
```

### 8. LLM Client

**Responsibilities:**
- OpenAI Chat API integration
- Prompt construction
- Response parsing
- Token usage tracking

**Interface:**

```python
class LLMClient:
    def __init__(self, api_key: str, model: str = "gpt-4"):
        pass
    
    async def generate_response(
        self,
        system_prompt: str,
        user_query: str,
        context: str
    ) -> LLMResponse:
        """
        Call OpenAI Chat API with system prompt and context
        Parse response and extract citations
        """
        pass
```

## Data Models

### Pydantic Request/Response Models

```python
class IngestRequest(BaseModel):
    tenant_id: UUID
    content: str
    metadata: Optional[Dict[str, Any]] = None

class IngestResponse(BaseModel):
    document_id: UUID
    chunks_created: int
    status: str

class QueryRequest(BaseModel):
    tenant_id: UUID
    query: str
    top_k: Optional[int] = 5

class SourceReference(BaseModel):
    document_id: UUID
    chunk_text: str
    similarity_score: float

class QueryResponse(BaseModel):
    answer: str
    sources: List[SourceReference]
    cached: bool
```

### Database Schema

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_documents_tenant ON documents(tenant_id);

CREATE TABLE document_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    chunk_text TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    embedding vector(1536) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_chunks_tenant ON document_chunks(tenant_id);
CREATE INDEX idx_chunks_embedding ON document_chunks USING ivfflat (embedding vector_cosine_ops);

CREATE TABLE ai_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    query TEXT NOT NULL,
    response TEXT NOT NULL,
    cached BOOLEAN DEFAULT FALSE,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sources_used JSONB
);

CREATE INDEX idx_ai_logs_tenant ON ai_logs(tenant_id);
CREATE INDEX idx_ai_logs_timestamp ON ai_logs(timestamp);
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*


### Property 1: Tenant ID Enforcement on All Operations

*For any* database operation (create, read, update, delete), the system should require a valid tenant_id and reject operations that attempt to access data without proper tenant_id validation.

**Validates: Requirements 1.2, 1.4, 1.5**

### Property 2: Vector Search Tenant Isolation

*For any* semantic search query, all returned results should only contain document chunks belonging to the specified tenant_id, and the query should include a WHERE tenant_id = :tid filter.

**Validates: Requirements 1.3, 3.3, 7.5**

### Property 3: Document Chunking Consistency

*For any* document ingested, the system should split it into chunks and generate exactly one embedding per chunk, with chunk count equal to embedding count.

**Validates: Requirements 2.2, 2.3**

### Property 4: Embedding Storage with Tenant Association

*For any* document ingestion, all generated embeddings and document records should be stored with the correct tenant_id in both the Documents and DocumentChunks tables.

**Validates: Requirements 2.4, 2.5, 7.2**

### Property 5: Transaction Rollback on Failure

*For any* ingestion or database operation that fails at any step, the system should roll back all partial changes and return a descriptive error message, leaving the database in a consistent state.

**Validates: Requirements 2.6, 10.6**

### Property 6: Cache Hit Prevents LLM Call

*For any* query that has been cached, the system should return the cached response without calling the LLM API, and the response should be marked as cached.

**Validates: Requirements 4.2**

### Property 7: Cache Key Tenant Isolation

*For any* query result cached, the cache key should include the tenant_id to prevent cross-tenant cache pollution, ensuring tenant A cannot retrieve tenant B's cached results.

**Validates: Requirements 4.1, 4.5**

### Property 8: Cache Miss Stores Result

*For any* query that is not cached, after processing the query and generating a response, the system should store the result in Redis with an appropriate TTL.

**Validates: Requirements 4.3, 4.4**

### Property 9: System Prompt Enforcement

*For any* LLM call, the system should include a system prompt that mandates source citations and requires the LLM to refuse answering when context is insufficient.

**Validates: Requirements 3.6, 5.1**

### Property 10: Response Contains Sources

*For any* successful query response, the system should include both the AI-generated answer and source document references with document IDs for all cited sources.

**Validates: Requirements 3.7, 5.2, 5.5**

### Property 11: Context Required for LLM

*For any* query, the system should only call the LLM when relevant context is found, and should not allow the LLM to generate responses based solely on its training data without document context.

**Validates: Requirements 3.5, 5.4**

### Property 12: Foreign Key Constraint Enforcement

*For any* attempt to create a record with an invalid tenant_id (non-existent tenant), the database should reject the operation due to foreign key constraint violation.

**Validates: Requirements 6.4**

### Property 13: Input Validation Returns 400

*For any* API request with missing required fields or invalid data, the system should return HTTP 400 status code with descriptive error details.

**Validates: Requirements 9.3**

### Property 14: Success Returns Appropriate Status

*For any* successful API operation, the system should return appropriate HTTP status codes (200 for queries, 201 for ingestion) with properly formatted JSON responses.

**Validates: Requirements 9.4, 9.6**

### Property 15: Error Handling Returns Appropriate Status

*For any* error condition (not found, server error), the system should return appropriate HTTP status codes (404, 500) with error details, without exposing sensitive information or stack traces.

**Validates: Requirements 9.5, 10.1, 10.5**

### Property 16: AI Interactions Logged

*For any* query processed (cached or not), the system should create an entry in the AI_Logs table with tenant_id, query, response, timestamp, and cached flag.

**Validates: Requirements 10.4**

### Property 17: Operations Logged

*For any* key operation (ingestion start/complete, query start/complete, cache hit/miss, errors), the system should create appropriate log entries with sufficient detail for debugging.

**Validates: Requirements 10.2, 10.3**

### Property 18: Embedding Model Consistency

*For any* document or query embedding generation, the system should use the same configured embedding model consistently and store the model version with embeddings.

**Validates: Requirements 12.1, 12.3**

### Property 19: Chunking Configuration

*For any* document chunked, the system should use the configured chunk size and overlap parameters, and chunks should respect these boundaries.

**Validates: Requirements 12.2**

### Property 20: Embedding API Retry on Failure

*For any* embedding API failure, the system should retry with exponential backoff and log the failure, eventually returning an error if retries are exhausted.

**Validates: Requirements 12.4**

## Error Handling

### Error Categories

1. **Validation Errors (400)**
   - Missing required fields (tenant_id, content, query)
   - Invalid UUID format
   - Empty content or query strings
   - Invalid metadata format

2. **Not Found Errors (404)**
   - Tenant does not exist
   - Document does not exist
   - No results found for query

3. **Server Errors (500)**
   - Database connection failures
   - Redis connection failures
   - OpenAI API failures (after retries)
   - Unexpected exceptions

### Error Response Format

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "User-friendly error message",
    "details": {
      "field": "tenant_id",
      "reason": "Invalid UUID format"
    }
  }
}
```

### Error Handling Strategy

1. **Input Validation**: Use Pydantic models for automatic validation
2. **Database Errors**: Catch SQLAlchemy exceptions, rollback transactions, log details
3. **External API Errors**: Implement retry logic with exponential backoff
4. **Logging**: Log all errors with context (tenant_id, request_id, stack trace)
5. **User-Facing Messages**: Never expose internal details, stack traces, or sensitive data

### Retry Configuration

- **Embedding API**: 3 retries with exponential backoff (1s, 2s, 4s)
- **LLM API**: 3 retries with exponential backoff (1s, 2s, 4s)
- **Redis**: 2 retries with 500ms delay
- **Database**: No automatic retries (fail fast)

## Testing Strategy

### Dual Testing Approach

The system will use both unit tests and property-based tests for comprehensive coverage:

- **Unit tests**: Verify specific examples, edge cases, and error conditions
- **Property tests**: Verify universal properties across all inputs using randomized testing

### Property-Based Testing

**Framework**: Use `hypothesis` library for Python property-based testing

**Configuration**:
- Minimum 100 iterations per property test
- Each test tagged with: `# Feature: multi-tenant-rag-system, Property {N}: {property_text}`
- Custom generators for UUIDs, tenant data, documents, queries

**Property Test Coverage**:
- Each of the 20 correctness properties above will have a corresponding property-based test
- Tests will generate random valid inputs and verify properties hold
- Edge cases (empty strings, large documents, special characters) will be included in generators

### Unit Testing

**Focus Areas**:
- API endpoint integration tests
- Service layer method tests with mocked dependencies
- Database model tests
- Cache service tests with Redis mock
- Error handling specific scenarios
- Configuration loading tests

**Test Structure**:
```
tests/
  unit/
    test_api.py
    test_ingest_service.py
    test_query_service.py
    test_vector_store.py
    test_cache_service.py
    test_models.py
  property/
    test_tenant_isolation_properties.py
    test_caching_properties.py
    test_embedding_properties.py
    test_error_handling_properties.py
  integration/
    test_end_to_end.py
```

### Test Data Generators

**Hypothesis Strategies**:
```python
@st.composite
def tenant_id_strategy(draw):
    return draw(st.uuids())

@st.composite
def document_strategy(draw):
    return {
        "tenant_id": draw(st.uuids()),
        "content": draw(st.text(min_size=100, max_size=10000)),
        "metadata": draw(st.dictionaries(st.text(), st.text()))
    }

@st.composite
def query_strategy(draw):
    return {
        "tenant_id": draw(st.uuids()),
        "query": draw(st.text(min_size=10, max_size=500))
    }
```

### Testing Tenant Isolation

Critical property tests for tenant isolation:
1. Vector search never returns other tenant's data
2. Cache keys prevent cross-tenant access
3. Database queries always filter by tenant_id
4. API operations validate tenant_id matches authenticated tenant

### Mocking Strategy

- **OpenAI API**: Mock with deterministic responses for unit tests
- **Redis**: Use fakeredis for unit tests
- **Database**: Use SQLite in-memory for fast unit tests, PostgreSQL for integration tests
- **pgvector**: Mock vector operations for unit tests, use real pgvector for integration tests

### Performance Testing

- Load test with multiple concurrent tenants
- Measure cache hit rate and cost savings
- Benchmark vector search performance with varying dataset sizes
- Monitor memory usage during large document ingestion

## Deployment Considerations

### Environment Variables

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname

# Redis
REDIS_URL=redis://host:6379/0

# OpenAI
OPENAI_API_KEY=sk-...

# Configuration
EMBEDDING_MODEL=text-embedding-ada-002
LLM_MODEL=gpt-4
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
CACHE_TTL=3600
TOP_K_RESULTS=5
```

### Database Migrations

Use Alembic for schema migrations:
```bash
alembic init migrations
alembic revision --autogenerate -m "Initial schema"
alembic upgrade head
```

### Docker Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Health Checks

Implement `/health` endpoint that checks:
- Database connectivity
- Redis connectivity
- pgvector extension availability

### Monitoring

- Log all requests with tenant_id and request_id
- Track cache hit rate metrics
- Monitor OpenAI API usage and costs per tenant
- Alert on error rate thresholds
- Track query latency percentiles (p50, p95, p99)

### Security

- Use environment variables for secrets (never commit)
- Implement rate limiting per tenant
- Add authentication middleware (JWT or API keys)
- Validate all inputs with Pydantic
- Use parameterized queries to prevent SQL injection
- Implement CORS policies for API access
