# Implementation Plan: Multi-tenant RAG System (Hackathon MVP)

## Overview

This is a simplified implementation plan focused on getting a working multi-tenant RAG system in 60 minutes. We'll skip migrations, complex abstractions, and focus on core functionality: /ingest and /query endpoints with tenant isolation.

## Tasks

- [x] 1. Set up project structure and dependencies
  - Create requirements.txt with FastAPI, SQLAlchemy, pgvector, redis, openai, langchain
  - Create .env.example file with required environment variables
  - _Requirements: 11.1, 11.2, 11.3_

- [x] 2. Create database models and connection (models.py, database.py)
  - [x] 2.1 Implement database connection with async SQLAlchemy
    - Create async engine and session factory
    - Add get_db() dependency for FastAPI
    - _Requirements: 6.1, 6.2, 6.3_
  
  - [x] 2.2 Define SQLAlchemy models with tenant_id enforcement
    - Create Tenant, Document, DocumentChunk, AILog models
    - Add tenant_id foreign keys and indexes
    - Include pgvector column for embeddings (Vector(1536))
    - _Requirements: 1.1, 6.4, 7.1_
  
  - [x] 2.3 Add create_all() initialization function
    - Create function to initialize database schema on startup
    - Include pgvector extension creation
    - _Requirements: 6.1, 6.2, 6.3_

- [ ]* 2.4 Write property test for tenant_id enforcement
  - **Property 1: Tenant ID Enforcement on All Operations**
  - **Validates: Requirements 1.2, 1.4, 1.5**

- [x] 3. Implement core services (services.py)
  - [x] 3.1 Create EmbeddingService for OpenAI embeddings
    - Implement generate_embedding() for single text
    - Implement generate_embeddings() for batch processing
    - Add retry logic with exponential backoff
    - _Requirements: 12.1, 12.4_
  
  - [x] 3.2 Create CacheService for Redis operations
    - Implement get_cached_query() with tenant_id in key
    - Implement cache_query_result() with TTL
    - Use format: query:{tenant_id}:{hash(query)}
    - _Requirements: 4.1, 4.3, 4.4, 4.5_
  
  - [x] 3.3 Create IngestService for document processing
    - Implement chunk_text() using simple splitting (1000 chars, 200 overlap)
    - Implement ingest_document() that chunks, embeds, and stores
    - Add transaction handling with rollback on failure
    - _Requirements: 2.2, 2.3, 2.4, 2.5, 2.6_
  
  - [x] 3.4 Create QueryService for semantic search and LLM
    - Implement semantic_search() with pgvector cosine similarity
    - Ensure WHERE tenant_id = :tid filter in all queries
    - Implement generate_response() with system prompt for citations
    - Add logic to refuse answering when no context found
    - _Requirements: 3.2, 3.3, 3.4, 3.5, 3.6, 5.1, 5.3_

- [ ]* 3.5 Write property test for vector search tenant isolation
  - **Property 2: Vector Search Tenant Isolation**
  - **Validates: Requirements 1.3, 3.3, 7.5**

- [ ]* 3.6 Write property test for cache tenant isolation
  - **Property 7: Cache Key Tenant Isolation**
  - **Validates: Requirements 4.1, 4.5**

- [ ] 4. Checkpoint - Ensure services are working
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement FastAPI application (main.py)
  - [x] 5.1 Create FastAPI app with startup event
    - Initialize database with create_all()
    - Initialize Redis connection
    - Add health check endpoint
    - _Requirements: 11.6_
  
  - [x] 5.2 Define Pydantic request/response models
    - Create IngestRequest, IngestResponse
    - Create QueryRequest, QueryResponse, SourceReference
    - _Requirements: 9.1, 9.2_
  
  - [x] 5.3 Implement POST /ingest endpoint
    - Accept tenant_id, content, optional metadata
    - Call IngestService.ingest_document()
    - Return document_id and chunks_created
    - Add error handling with appropriate status codes
    - _Requirements: 2.1, 9.1, 9.3, 9.4, 9.5_
  
  - [x] 5.4 Implement POST /query endpoint
    - Accept tenant_id and query string
    - Check cache first via CacheService
    - If cache miss, call QueryService for semantic search and LLM response
    - Cache the result
    - Log to AI_Logs table
    - Return answer with sources and cached flag
    - _Requirements: 3.1, 3.7, 4.2, 10.4_

- [ ]* 5.5 Write property test for API input validation
  - **Property 13: Input Validation Returns 400**
  - **Validates: Requirements 9.3**

- [ ]* 5.6 Write unit tests for API endpoints
  - Test /ingest with valid and invalid inputs
  - Test /query with cache hit and cache miss scenarios
  - Test error responses
  - _Requirements: 9.3, 9.4, 9.5_

- [x] 6. Add error handling and logging
  - [x] 6.1 Add global exception handler to FastAPI
    - Catch all exceptions and return appropriate status codes
    - Log errors with context (tenant_id, stack trace)
    - Never expose sensitive information in responses
    - _Requirements: 10.1, 10.2, 10.5_
  
  - [x] 6.2 Add logging for key operations
    - Log ingestion start/complete
    - Log query start/complete
    - Log cache hits/misses
    - _Requirements: 10.3_

- [ ]* 6.3 Write property test for error handling
  - **Property 15: Error Handling Returns Appropriate Status**
  - **Validates: Requirements 9.5, 10.1, 10.5**

- [x] 7. Create configuration and setup files
  - [x] 7.1 Create .env.example with all required variables
    - DATABASE_URL, REDIS_URL, OPENAI_API_KEY
    - CHUNK_SIZE, CHUNK_OVERLAP, CACHE_TTL
    - _Requirements: 11.1, 11.2, 11.3, 11.4_
  
  - [x] 7.2 Create README.md with setup instructions
    - Installation steps
    - Environment setup
    - Running the application
    - API usage examples
  
  - [x] 7.3 Create simple test script to verify end-to-end flow
    - Create a test tenant
    - Ingest a sample document
    - Query the system
    - Verify response includes sources

- [ ] 8. Final checkpoint - End-to-end testing
  - Ensure all tests pass, ask the user if questions arise.
  - Test complete flow: ingest → query → cached query
  - Verify tenant isolation works
  - Verify cache is working

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Focus on getting /ingest and /query working first
- Use simple functions or a single Service class - no complex abstractions
- Use create_all() instead of Alembic migrations
- All database operations must include tenant_id for isolation
- System prompt must enforce source citations
- Cache keys must include tenant_id to prevent cross-tenant pollution
- Property tests validate universal correctness properties with 100+ iterations
- Unit tests validate specific examples and edge cases

## Quick Start Order

1. Set up dependencies and environment (Task 1)
2. Create database models (Task 2.1, 2.2, 2.3)
3. Implement services (Task 3.1, 3.2, 3.3, 3.4)
4. Create FastAPI app and endpoints (Task 5)
5. Add error handling (Task 6)
6. Test end-to-end (Task 8)
