from sqlalchemy import Column, String, Text, Integer, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector
from datetime import datetime
import uuid
from database import Base


class Tenant(Base):
    __tablename__ = "tenants"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Document(Base):
    __tablename__ = "documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    metadata = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index("idx_documents_tenant", "tenant_id"),
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_text = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    embedding = Column(Vector(1536), nullable=False)  # OpenAI ada-002 dimension
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index("idx_chunks_tenant", "tenant_id"),
        Index("idx_chunks_embedding", "embedding", postgresql_using="ivfflat", postgresql_ops={"embedding": "vector_cosine_ops"}),
    )


class AILog(Base):
    __tablename__ = "ai_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    query = Column(Text, nullable=False)
    response = Column(Text, nullable=False)
    cached = Column(Boolean, default=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    sources_used = Column(JSONB, nullable=True)
    
    __table_args__ = (
        Index("idx_ai_logs_tenant", "tenant_id"),
        Index("idx_ai_logs_timestamp", "timestamp"),
    )
