# Mock Mode - No Cost Testing

## 🎯 Overview

Mock Mode allows you to test the entire RAG system **without an OpenAI API key** and **without any costs**. The system uses deterministic fake embeddings and responses.

## ✅ What Works in Mock Mode

- ✅ **Document Ingestion** - Chunks text and generates deterministic embeddings
- ✅ **Vector Search** - pgvector semantic search works perfectly
- ✅ **Query Responses** - Returns mock answers with source citations
- ✅ **Caching** - Redis caching works normally
- ✅ **Tenant Isolation** - All security features work
- ✅ **Data Flow** - Complete end-to-end flow functional

## 🔧 How It Works

### Deterministic Embeddings
```python
# Same text = Same embedding EVERY TIME
"Hello" → [0.123, -0.456, 0.789, ...] (1536 dimensions)
"Hello" → [0.123, -0.456, 0.789, ...] (same!)
```

Uses SHA256 hash of text as seed for random number generator, ensuring:
- Same input text always produces same embedding
- pgvector can match and rank by similarity
- Vector search works exactly like real embeddings

### Mock LLM Responses
```json
{
  "answer": "MOCK ANSWER: Based on the provided context, [preview]... [Sources: doc_id_1, doc_id_2]",
  "sources": [...],
  "cached": false
}
```

## 🚀 How to Enable Mock Mode

### Option 1: Set API Key to "mock-key" (Recommended)
```bash
# In .env file
OPENAI_API_KEY=mock-key
```

### Option 2: Leave API Key Empty
```bash
# In .env file
OPENAI_API_KEY=
```

### Option 3: Don't set it at all
```bash
# Just comment it out or delete the line
# OPENAI_API_KEY=
```

## 📝 Testing in Mock Mode

### 1. Start Services
```bash
cd src/infra
docker-compose up -d
```

### 2. Create .env with Mock Key
```bash
cd ../backend
copy .env.example .env
# .env already has OPENAI_API_KEY=mock-key
```

### 3. Run Application
```bash
uvicorn main:app --reload
```

You should see:
```
🔧 MOCK MODE ENABLED - Using deterministic fake embeddings and responses
```

### 4. Create a Tenant
```bash
docker exec -it rag_postgres psql -U postgres -d rag_system -c "INSERT INTO tenants (id, name) VALUES ('11111111-1111-1111-1111-111111111111', 'Test Company');"
```

### 5. Test Ingestion
```bash
curl -X POST "http://localhost:8000/ingest" ^
  -H "Content-Type: application/json" ^
  -d "{\"tenant_id\": \"11111111-1111-1111-1111-111111111111\", \"content\": \"Python is a programming language used for web development and data science.\", \"metadata\": {\"title\": \"Python Guide\"}}"
```

Expected response:
```json
{
  "document_id": "some-uuid",
  "chunks_created": 1,
  "status": "success"
}
```

### 6. Test Query
```bash
curl -X POST "http://localhost:8000/query" ^
  -H "Content-Type: application/json" ^
  -d "{\"tenant_id\": \"11111111-1111-1111-1111-111111111111\", \"query\": \"What is Python?\"}"
```

Expected response:
```json
{
  "answer": "MOCK ANSWER: Based on the provided context, Python is a programming language... [Sources: doc-uuid]",
  "sources": [
    {
      "document_id": "doc-uuid",
      "chunk_text": "Python is a programming language...",
      "similarity_score": 0.95
    }
  ],
  "cached": false
}
```

### 7. Test Caching (Query Again)
```bash
# Run the same query again - should be cached
curl -X POST "http://localhost:8000/query" ^
  -H "Content-Type: application/json" ^
  -d "{\"tenant_id\": \"11111111-1111-1111-1111-111111111111\", \"query\": \"What is Python?\"}"
```

Expected: `"cached": true`

## 🔄 Switching to Real Mode

When you have an OpenAI API key:

```bash
# In .env file
OPENAI_API_KEY=sk-your-real-openai-api-key-here
```

Restart the application:
```bash
# Stop
Ctrl+C

# Start again
uvicorn main:app --reload
```

You should see normal startup (no mock mode message).

## 🎓 Perfect for Exams/Demos

Mock Mode is ideal for:
- ✅ Testing without costs
- ✅ Demonstrating the system architecture
- ✅ Verifying data flow and tenant isolation
- ✅ Debugging vector search logic
- ✅ Running automated tests
- ✅ Exam environments without API access

## 🔍 Verification

Check logs for mock mode indicators:
```
🔧 MOCK MODE ENABLED - Using deterministic fake embeddings and responses
🔧 Mock embeddings for 1 texts
🔧 Mock LLM response for query: What is Python?...
```

## ⚠️ Limitations

- Mock responses are generic (not real AI-generated)
- Embeddings are random (but deterministic)
- No actual language understanding
- Good for testing infrastructure, not AI quality

## 💡 Pro Tip

You can mix modes:
- Use Mock Mode for development/testing
- Switch to Real Mode for production
- No code changes needed - just update .env!
