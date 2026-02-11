import os
import hashlib
import json
import random
from typing import List, Optional, Dict, Any
from uuid import UUID
import asyncio
from openai import AsyncOpenAI
import redis.asyncio as redis
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from models import Document, DocumentChunk, AILog, Tenant
from dotenv import load_dotenv

load_dotenv()

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-ada-002")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1000"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))
CACHE_TTL = int(os.getenv("CACHE_TTL", "3600"))
TOP_K_RESULTS = int(os.getenv("TOP_K_RESULTS", "5"))

# Check if we're in mock mode
MOCK_MODE = not OPENAI_API_KEY or OPENAI_API_KEY.startswith("mock")

# Initialize OpenAI client (only if not in mock mode)
if not MOCK_MODE:
    openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
else:
    openai_client = None
    print("🔧 MOCK MODE ENABLED - Using deterministic fake embeddings and responses")

# Initialize Redis client
redis_client = redis.from_url(REDIS_URL, decode_responses=True)


class EmbeddingService:
    """Service for generating embeddings using OpenAI API or Mock Mode"""
    
    @staticmethod
    def _generate_mock_embedding(text: str) -> List[float]:
        """Generate deterministic mock embedding from text (1536 dimensions)"""
        # Use SHA256 hash as seed for deterministic randomness
        seed = int(hashlib.sha256(text.encode()).hexdigest(), 16) % (2**32)
        random.seed(seed)
        
        # Generate 1536 random floats (matching text-embedding-ada-002 dimension)
        embedding = [random.uniform(-1, 1) for _ in range(1536)]
        
        # Normalize the vector (optional but good practice)
        magnitude = sum(x**2 for x in embedding) ** 0.5
        normalized = [x / magnitude for x in embedding]
        
        return normalized
    
    @staticmethod
    async def generate_embedding(text: str) -> List[float]:
        """Generate embedding for a single text"""
        # Mock mode: deterministic fake embeddings
        if MOCK_MODE:
            print(f"🔧 Mock embedding for: {text[:50]}...")
            return EmbeddingService._generate_mock_embedding(text)
        
        # Real mode: OpenAI API
        try:
            response = await openai_client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"Error generating embedding: {e}")
            # Retry logic with exponential backoff
            for attempt in range(3):
                await asyncio.sleep(2 ** attempt)
                try:
                    response = await openai_client.embeddings.create(
                        model=EMBEDDING_MODEL,
                        input=text
                    )
                    return response.data[0].embedding
                except Exception as retry_error:
                    if attempt == 2:
                        raise retry_error
            raise e
    
    @staticmethod
    async def generate_embeddings(texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        # Mock mode: deterministic fake embeddings
        if MOCK_MODE:
            print(f"🔧 Mock embeddings for {len(texts)} texts")
            return [EmbeddingService._generate_mock_embedding(text) for text in texts]
        
        # Real mode: OpenAI API
        try:
            response = await openai_client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=texts
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            print(f"Error generating embeddings: {e}")
            raise e


class CacheService:
    """Service for Redis caching operations"""
    
    @staticmethod
    def _generate_cache_key(tenant_id: UUID, query: str) -> str:
        """Generate cache key with tenant_id and query hash"""
        query_hash = hashlib.sha256(query.encode()).hexdigest()[:16]
        return f"query:{tenant_id}:{query_hash}"
    
    @staticmethod
    async def get_cached_query(tenant_id: UUID, query: str) -> Optional[Dict[str, Any]]:
        """Get cached query result"""
        try:
            cache_key = CacheService._generate_cache_key(tenant_id, query)
            cached_data = await redis_client.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
            return None
        except Exception as e:
            print(f"Cache get error: {e}")
            return None
    
    @staticmethod
    async def cache_query_result(tenant_id: UUID, query: str, result: Dict[str, Any]) -> None:
        """Cache query result with TTL"""
        try:
            cache_key = CacheService._generate_cache_key(tenant_id, query)
            await redis_client.setex(
                cache_key,
                CACHE_TTL,
                json.dumps(result)
            )
        except Exception as e:
            print(f"Cache set error: {e}")


class IngestService:
    """Service for document ingestion and processing"""
    
    @staticmethod
    def chunk_text(text: str) -> List[str]:
        """Split text into chunks with overlap"""
        chunks = []
        start = 0
        text_length = len(text)
        
        while start < text_length:
            end = start + CHUNK_SIZE
            chunk = text[start:end]
            chunks.append(chunk)
            start += CHUNK_SIZE - CHUNK_OVERLAP
        
        return chunks if chunks else [text]
    
    @staticmethod
    async def ingest_document(
        db: AsyncSession,
        tenant_id: UUID,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Ingest document: chunk, embed, and store"""
        try:
            # Verify tenant exists
            result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
            tenant = result.scalar_one_or_none()
            if not tenant:
                raise ValueError(f"Tenant {tenant_id} not found")
            
            # Create document record
            document = Document(
                tenant_id=tenant_id,
                content=content,
                metadata=metadata
            )
            db.add(document)
            await db.flush()
            
            # Chunk the text
            chunks = IngestService.chunk_text(content)
            
            # Generate embeddings for all chunks
            embeddings = await EmbeddingService.generate_embeddings(chunks)
            
            # Store chunks with embeddings
            for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                chunk_record = DocumentChunk(
                    document_id=document.id,
                    tenant_id=tenant_id,
                    chunk_text=chunk,
                    chunk_index=idx,
                    embedding=embedding
                )
                db.add(chunk_record)
            
            await db.commit()
            
            return {
                "document_id": str(document.id),
                "chunks_created": len(chunks),
                "status": "success"
            }
        
        except Exception as e:
            await db.rollback()
            print(f"Ingestion error: {e}")
            raise e


class QueryService:
    """Service for semantic search and LLM response generation"""
    
    SYSTEM_PROMPT = """You are a helpful assistant that answers questions based ONLY on the provided context.

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

ANSWER:"""
    
    @staticmethod
    async def semantic_search(
        db: AsyncSession,
        tenant_id: UUID,
        query_embedding: List[float],
        top_k: int = TOP_K_RESULTS
    ) -> List[Dict[str, Any]]:
        """Perform semantic search with tenant isolation"""
        try:
            # Convert embedding to string format for pgvector
            embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"
            
            # Query with cosine distance and tenant filter
            query = text("""
                SELECT 
                    id,
                    document_id,
                    chunk_text,
                    embedding <=> :embedding::vector AS distance
                FROM document_chunks
                WHERE tenant_id = :tenant_id
                ORDER BY embedding <=> :embedding::vector
                LIMIT :top_k
            """)
            
            result = await db.execute(
                query,
                {
                    "embedding": embedding_str,
                    "tenant_id": str(tenant_id),
                    "top_k": top_k
                }
            )
            
            rows = result.fetchall()
            
            return [
                {
                    "id": str(row[0]),
                    "document_id": str(row[1]),
                    "chunk_text": row[2],
                    "similarity_score": 1 - row[3]  # Convert distance to similarity
                }
                for row in rows
            ]
        
        except Exception as e:
            print(f"Semantic search error: {e}")
            raise e
    
    @staticmethod
    async def generate_response(
        context_chunks: List[Dict[str, Any]],
        query: str
    ) -> str:
        """Generate LLM response with context"""
        # Mock mode: deterministic fake response
        if MOCK_MODE:
            print(f"🔧 Mock LLM response for query: {query[:50]}...")
            
            if not context_chunks:
                return "I cannot answer this question based on the available documents."
            
            # Create a mock response with source citations
            doc_ids = [chunk['document_id'] for chunk in context_chunks[:3]]
            context_preview = context_chunks[0]['chunk_text'][:100] if context_chunks else ""
            
            mock_answer = f"MOCK ANSWER: Based on the provided context, {context_preview}... "
            mock_answer += f"[Sources: {', '.join(doc_ids)}]"
            
            return mock_answer
        
        # Real mode: OpenAI API
        try:
            # Build context from chunks
            context = "\n\n".join([
                f"[Document {chunk['document_id']}]: {chunk['chunk_text']}"
                for chunk in context_chunks
            ])
            
            # Format prompt
            prompt = QueryService.SYSTEM_PROMPT.format(
                context=context,
                query=query
            )
            
            # Call OpenAI
            response = await openai_client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            return response.choices[0].message.content
        
        except Exception as e:
            print(f"LLM generation error: {e}")
            raise e
    
    @staticmethod
    async def query(
        db: AsyncSession,
        tenant_id: UUID,
        query: str,
        top_k: int = TOP_K_RESULTS
    ) -> Dict[str, Any]:
        """Execute full query pipeline: cache check, search, LLM, cache store"""
        try:
            # Check cache
            cached_result = await CacheService.get_cached_query(tenant_id, query)
            if cached_result:
                print(f"Cache hit for tenant {tenant_id}")
                return {**cached_result, "cached": True}
            
            print(f"Cache miss for tenant {tenant_id}")
            
            # Generate query embedding
            query_embedding = await EmbeddingService.generate_embedding(query)
            
            # Semantic search
            search_results = await QueryService.semantic_search(
                db, tenant_id, query_embedding, top_k
            )
            
            # Check if we have context
            if not search_results:
                answer = "I cannot answer this question based on the available documents."
                sources = []
            else:
                # Generate LLM response
                answer = await QueryService.generate_response(search_results, query)
                sources = [
                    {
                        "document_id": chunk["document_id"],
                        "chunk_text": chunk["chunk_text"][:200] + "...",  # Truncate for response
                        "similarity_score": chunk["similarity_score"]
                    }
                    for chunk in search_results
                ]
            
            result = {
                "answer": answer,
                "sources": sources,
                "cached": False
            }
            
            # Cache the result
            await CacheService.cache_query_result(tenant_id, query, result)
            
            # Log to database
            log_entry = AILog(
                tenant_id=tenant_id,
                query=query,
                response=answer,
                cached=False,
                sources_used=sources
            )
            db.add(log_entry)
            await db.commit()
            
            return result
        
        except Exception as e:
            print(f"Query error: {e}")
            raise e
