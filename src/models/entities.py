import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


def generate_uuid():
    """Generate a UUID string."""
    return str(uuid.uuid4())


class Document(Base):
    """Main document storage table."""

    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=generate_uuid)
    filename = Column(String, nullable=False, unique=True)
    content_type = Column(String)  # protocol|form|contact|reference
    file_type = Column(String)  # pdf|docx|txt|md
    content = Column(Text)
    meta = Column("metadata", JSON, default={})
    file_hash = Column(String)  # For deduplication
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    chunks = relationship(
        "DocumentChunk", back_populates="document", cascade="all, delete-orphan"
    )
    registry_entries = relationship(
        "DocumentRegistry", back_populates="document", cascade="all, delete-orphan"
    )
    extracted_entities = relationship(
        "ExtractedEntity", back_populates="document", cascade="all, delete-orphan"
    )
    tables = relationship(
        "ExtractedTable", back_populates="document", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_document_content_type", "content_type"),
        Index("idx_document_filename", "filename"),
        Index("idx_document_file_hash", "file_hash"),
    )


class DocumentChunk(Base):
    """Document chunks for semantic search."""

    __tablename__ = "document_chunks"

    id = Column(String, primary_key=True, default=generate_uuid)
    document_id = Column(
        String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    chunk_text = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    embedding = Column(Vector(384))  # Using 384-dim embeddings (e.g., all-MiniLM-L6-v2)
    chunk_type = Column(String)  # header|body|table|list
    medical_category = Column(String)  # cardiology|emergency|pharmacy|etc
    urgency_level = Column(String)  # routine|urgent|stat|emergent
    contains_contact = Column(Boolean, default=False)
    contains_dosage = Column(Boolean, default=False)
    page_number = Column(Integer)
    
    # Source highlighting fields (PRP 17)
    page_span_start = Column(Integer, nullable=True)  # Character offset in page
    page_span_end = Column(Integer, nullable=True)
    document_span_start = Column(Integer, nullable=True)  # Absolute offset in document
    document_span_end = Column(Integer, nullable=True)
    bbox = Column(JSON, nullable=True)  # {"x": 10, "y": 20, "width": 100, "height": 50}
    
    meta = Column("metadata", JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    document = relationship("Document", back_populates="chunks")

    __table_args__ = (
        Index("idx_chunk_document_id", "document_id"),
        Index("idx_chunk_medical_category", "medical_category"),
        Index("idx_chunk_urgency", "urgency_level"),
        Index("idx_chunk_contains_contact", "contains_contact"),
        Index("idx_chunk_contains_dosage", "contains_dosage"),
        Index("idx_chunk_page", "document_id", "page_number"),  # For page-based retrieval (PRP 17)
        UniqueConstraint("document_id", "chunk_index", name="uq_document_chunk_index"),
    )


class DocumentRegistry(Base):
    """Registry for quick document lookup."""

    __tablename__ = "document_registry"

    id = Column(String, primary_key=True, default=generate_uuid)
    document_id = Column(
        String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    keywords = Column(JSON, default=[])  # Array of keywords
    display_name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    quick_access = Column(Boolean, default=False)
    category = Column(String)  # form|protocol|reference|contact
    priority = Column(Integer, default=0)  # Higher priority shown first
    meta = Column("metadata", JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Enhanced categorization fields (PRP 32)
    query_type = Column(String)  # Maps to QueryType enum values
    confidence = Column(Float, default=0.0)  # Classification confidence
    classification_method = Column(String)  # 'filename'|'content'|'hybrid'
    medical_specialty = Column(String)  # cardiology|emergency|etc
    urgency_level = Column(String)  # stat|urgent|routine
    primary_keywords = Column(JSON, default=[])  # High-confidence terms
    medical_terms = Column(JSON, default=[])  # Medical terminology
    abbreviations = Column(JSON, default=[])  # Common medical abbreviations

    # Relationships
    document = relationship("Document", back_populates="registry_entries")

    __table_args__ = (
        Index("idx_registry_document_id", "document_id"),
        Index("idx_registry_keywords", "keywords", postgresql_using="gin"),
        Index("idx_registry_category", "category"),
        Index("idx_registry_quick_access", "quick_access"),
        Index("idx_registry_priority", "priority"),
        # Enhanced categorization indexes (PRP 32)
        Index("idx_registry_query_type", "query_type"),
        Index("idx_registry_medical_specialty", "medical_specialty"),
        Index("idx_registry_urgency", "urgency_level"),
        Index("idx_registry_confidence", "confidence"),
    )


class ExtractedEntity(Base):
    """Structured entities extracted via LangExtract."""

    __tablename__ = "extracted_entities"

    id = Column(String, primary_key=True, default=generate_uuid)
    document_id = Column(
        String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    entity_type = Column(
        String, nullable=False
    )  # contact|dosage|protocol_step|criteria|timing
    page_no = Column(Integer)
    span = Column(JSON)  # {"start": 120, "end": 185}
    payload = Column(JSON, nullable=False)  # Full extracted entity data
    confidence = Column(Float)
    evidence_text = Column(Text)  # Raw text that was extracted from
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    document = relationship("Document", back_populates="extracted_entities")

    __table_args__ = (
        Index("idx_entity_document_id", "document_id"),
        Index("idx_entity_type", "entity_type"),
        Index("idx_entity_page", "page_no"),
        Index("idx_entity_payload", "payload", postgresql_using="gin"),
    )


class ChatSession(Base):
    """User chat sessions for context management."""

    __tablename__ = "chat_sessions"

    session_id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String)  # Optional user identifier
    session_name = Column(String)
    meta = Column("metadata", JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    messages = relationship(
        "ChatMessage", back_populates="session", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_session_user_id", "user_id"),
        Index("idx_session_last_activity", "last_activity"),
    )


class ChatMessage(Base):
    """Individual chat messages with responses."""

    __tablename__ = "chat_messages"

    id = Column(String, primary_key=True, default=generate_uuid)
    session_id = Column(
        String,
        ForeignKey("chat_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    )
    message_type = Column(String, nullable=False)  # user|assistant|system
    content = Column(Text, nullable=False)
    query_type = Column(String)  # Classification result
    response_time = Column(Float)  # Response time in seconds
    confidence_score = Column(Float)
    sources = Column(JSON, default=[])  # Array of source references
    warnings = Column(JSON, default=[])  # Any medical warnings
    meta = Column("metadata", JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    session = relationship("ChatSession", back_populates="messages")

    __table_args__ = (
        Index("idx_message_session_id", "session_id"),
        Index("idx_message_type", "message_type"),
        Index("idx_message_query_type", "query_type"),
        Index("idx_message_created_at", "created_at"),
    )


class QueryResponseCache(Base):
    """Store response data for PDF viewer (PRP 18)."""

    __tablename__ = "query_response_cache"

    id = Column(String, primary_key=True, default=generate_uuid)
    query = Column(Text, nullable=False)
    response = Column(JSON, nullable=False)
    highlights = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)

    __table_args__ = (
        Index("idx_response_expires", "expires_at"),
    )


class ExtractedTable(Base):
    """Store extracted tables from documents (PRP 19)."""

    __tablename__ = "extracted_tables"

    id = Column(String, primary_key=True, default=generate_uuid)
    document_id = Column(
        String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    page_number = Column(Integer, nullable=False)
    table_index = Column(Integer, nullable=False)  # Index of table on page

    # Table metadata
    table_type = Column(String, nullable=True)  # "dosage", "protocol", "reference", etc.
    title = Column(Text, nullable=True)  # Extracted or inferred title
    caption = Column(Text, nullable=True)

    # Structured content
    headers = Column(JSON, nullable=False)  # ["Drug", "Dose", "Route", "Frequency"]
    rows = Column(JSON, nullable=False)  # [["Aspirin", "325mg", "PO", "Daily"], ...]
    units = Column(JSON, nullable=True)  # {"Dose": "mg", ...}

    # Search optimization
    content_text = Column(Text, nullable=False)  # Flattened for search
    content_vector = Column(Vector(384), nullable=True)  # Embedding

    # Position info
    bbox = Column(JSON, nullable=True)
    confidence = Column(Float, default=1.0)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    document = relationship("Document", back_populates="tables")

    # Indexes
    __table_args__ = (
        Index("idx_table_document", "document_id", "page_number"),
        Index("idx_table_type", "table_type"),
        Index("idx_table_content_vector", "content_vector", postgresql_using="ivfflat", postgresql_ops={"content_vector": "vector_cosine_ops"}),
    )
