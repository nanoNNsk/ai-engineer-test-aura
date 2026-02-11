from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from uuid import UUID
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db, init_db
from services import IngestService, QueryService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Multi-tenant RAG System",
    description="RAG system with tenant isolation, caching, and source citations",
    version="1.0.0"
)


# Pydantic Models
class IngestRequest(BaseModel):
    tenant_id: UUID = Field(..., description="Tenant identifier")
    content: str = Field(..., min_length=1, description="Document content to ingest")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional metadata")


class IngestResponse(BaseModel):
    document_id: str
    chunks_created: int
    status: str


class QueryRequest(BaseModel):
    tenant_id: UUID = Field(..., description="Tenant identifier")
    query: str = Field(..., min_length=1, description="Query string")
    top_k: Optional[int] = Field(5, ge=1, le=20, description="Number of results to return")


class SourceReference(BaseModel):
    document_id: str
    chunk_text: str
    similarity_score: float


class QueryResponse(BaseModel):
    answer: str
    sources: List[SourceReference]
    cached: bool


class ErrorResponse(BaseModel):
    error: Dict[str, Any]


# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize database and connections on startup"""
    try:
        logger.info("Initializing database...")
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "multi-tenant-rag"}


# Ingest endpoint
@app.post(
    "/ingest",
    response_model=IngestResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
        500: {"model": ErrorResponse, "description": "Internal Server Error"}
    }
)
async def ingest_document(
    request: IngestRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Ingest a document: chunk text, generate embeddings, and store in vector database.
    
    - **tenant_id**: UUID of the tenant
    - **content**: Document text content
    - **metadata**: Optional metadata (title, source, etc.)
    """
    try:
        logger.info(f"Ingesting document for tenant {request.tenant_id}")
        
        result = await IngestService.ingest_document(
            db=db,
            tenant_id=request.tenant_id,
            content=request.content,
            metadata=request.metadata
        )
        
        logger.info(f"Document ingested successfully: {result['document_id']}")
        return IngestResponse(**result)
    
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "VALIDATION_ERROR",
                "message": str(e)
            }
        )
    except Exception as e:
        logger.error(f"Ingestion error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "INGESTION_ERROR",
                "message": "Failed to ingest document"
            }
        )


# Query endpoint
@app.post(
    "/query",
    response_model=QueryResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
        500: {"model": ErrorResponse, "description": "Internal Server Error"}
    }
)
async def query_documents(
    request: QueryRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Query the knowledge base: semantic search + LLM response with source citations.
    
    - **tenant_id**: UUID of the tenant
    - **query**: Question or search query
    - **top_k**: Number of relevant chunks to retrieve (default: 5)
    """
    try:
        logger.info(f"Processing query for tenant {request.tenant_id}")
        
        result = await QueryService.query(
            db=db,
            tenant_id=request.tenant_id,
            query=request.query,
            top_k=request.top_k
        )
        
        logger.info(f"Query processed successfully (cached: {result['cached']})")
        return QueryResponse(**result)
    
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "VALIDATION_ERROR",
                "message": str(e)
            }
        )
    except Exception as e:
        logger.error(f"Query error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "QUERY_ERROR",
                "message": "Failed to process query"
            }
        )


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Catch-all exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred"
            }
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
