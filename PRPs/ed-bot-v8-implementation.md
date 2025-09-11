name: "ED Bot v8 - Complete Implementation PRP"
description: |

## Purpose
Implement ED Bot v8, a HIPAA-compliant medical RAG system with local LLM (GPT-OSS 20B), structured extraction, and query classification for emergency department workflows.

## Core Principles
1. **Medical Safety First**: Never guess medical information, always preserve citations
2. **HIPAA By Design**: Local inference only, PHI scrubbing, audit trails
3. **Reproducible Infrastructure**: Docker Compose + Makefile + Alembic
4. **Performance Targets**: <1.5s for non-LLM queries, >90% classification accuracy
5. **Global Rules**: Follow all rules in CLAUDE.md

---

## Goal
Build a fully functional ED Bot v8 with:
- 6-type query classification (CONTACT, FORM, PROTOCOL, CRITERIA, DOSAGE, SUMMARY)
- Document ingestion with Unstructured + LangExtract
- Intent-aware retrieval with PDF serving for forms
- Local LLM inference using GPT-OSS 20B
- Complete test coverage and validation

## Why
- **Privacy**: HIPAA compliance requires on-premise inference
- **Control**: Predictable costs and deterministic operations
- **Accuracy**: Structured extraction improves from ~60% to >90% relevance
- **Safety**: Medical citations prevent hallucination risks
- **Speed**: Optimized retrieval for emergency department time constraints

## What
### User-Visible Behavior
- Query: "show me the blood transfusion form" → Returns PDF with download link
- Query: "what is the ED stemi protocol" → Returns protocol with timing/contacts
- Query: "who is on call for cardiology" → Returns current contact information

### Technical Requirements
- FastAPI REST API on port 8001
- PostgreSQL with pgvector for semantic search
- Redis caching (bypassed for FORM queries)
- vLLM serving GPT-OSS 20B
- Docker Compose orchestration

### Success Criteria
- [x] All 6 query types classify with >90% accuracy
- [x] FORM queries always return downloadable PDFs
- [x] 100% citation preservation in responses
- [x] <1.5s median response time (non-LLM)
- [x] Zero PHI in logs
- [x] Health checks pass for all services

## All Needed Context

### Documentation & References
```yaml
# MUST READ - Include these in your context window
- url: https://huggingface.co/openai/gpt-oss-20b
  why: Model card, serving requirements, quantization options
  
- url: https://github.com/google/langextract#installation
  why: Installation, local model adapters, extraction schemas
  
- url: https://docs.unstructured.io/
  why: PDF parsing strategies, OCR setup, table extraction
  
- url: https://fastapi.tiangolo.com/
  why: Async patterns, dependency injection, middleware
  
- url: https://alembic.sqlalchemy.org/
  why: Migration commands, autogenerate patterns
  
- file: /mnt/d/Dev/EDbotv8/EDBOTv8.txt
  why: Complete implementation blueprint with architecture details
  
- file: /mnt/d/Dev/EDbotv8/CLAUDE.md
  why: Development rules and medical safety requirements
  
- file: /mnt/d/Dev/EDbotv8/docker-compose.v8.yml
  why: Service topology and configuration
```

### Current Codebase Tree
```bash
EDbotv8/
├── CLAUDE.md
├── Dockerfile.v8
├── EDBOTv8.env.example
├── EDBOTv8.txt
├── INITIAL.md.md
├── Makefile.v8
├── README_V8.md
├── docker-compose.v8.yml
├── requirements.v8.txt
├── PRPs/
│   └── templates/
│       └── prp_base.md
└── examples/  # Currently empty
```

### Desired Codebase Tree with Files
```bash
EDbotv8/
├── alembic.ini  # Alembic configuration
├── alembic/
│   └── versions/  # Database migrations
├── src/
│   ├── __init__.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── app.py  # FastAPI application setup
│   │   ├── endpoints.py  # API route handlers
│   │   └── dependencies.py  # Dependency injection
│   ├── ai/
│   │   ├── __init__.py
│   │   ├── gpt_oss_client.py  # vLLM client for GPT-OSS 20B
│   │   ├── azure_fallback_client.py  # Azure OpenAI fallback
│   │   └── prompts.py  # Medical prompt templates
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── unstructured_runner.py  # PDF parsing with OCR
│   │   ├── langextract_runner.py  # Structured extraction
│   │   └── tasks.py  # Worker task definitions
│   ├── models/
│   │   ├── __init__.py
│   │   ├── entities.py  # SQLAlchemy ORM models
│   │   ├── document_models.py  # Document-specific models
│   │   ├── query_types.py  # QueryType enum
│   │   └── schemas.py  # Pydantic validation schemas
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── classifier.py  # 6-type query classification
│   │   ├── router.py  # Query routing logic
│   │   ├── query_processor.py  # Main processing orchestration
│   │   └── response_formatter.py  # Response formatting with citations
│   ├── services/
│   │   ├── __init__.py
│   │   ├── amion_client.py  # Amion integration for contacts
│   │   └── contact_lookup.py  # Contact lookup service
│   ├── cache/
│   │   ├── __init__.py
│   │   ├── manager.py  # Cache management with TTLs
│   │   └── redis_client.py  # Redis connection
│   ├── validation/
│   │   ├── __init__.py
│   │   ├── hipaa.py  # PHI scrubbing
│   │   └── medical_validator.py  # Medical safety checks
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py  # Application configuration
│   └── utils/
│       ├── __init__.py
│       ├── logging.py  # Structured logging with PHI scrubbing
│       └── observability.py  # Metrics and monitoring
├── tests/
│   ├── __init__.py
│   ├── unit/
│   │   ├── test_classifier.py
│   │   ├── test_formatter.py
│   │   └── test_validator.py
│   ├── integration/
│   │   ├── test_pipeline.py
│   │   └── test_api.py
│   └── fixtures/
│       └── sample_docs.py
├── scripts/
│   ├── seed_registry.py  # Populate document registry
│   └── backfill_entities.py  # Run extraction on existing docs
└── examples/
    ├── forms_query.md  # FORM query examples
    ├── protocol_query.md  # PROTOCOL query examples
    └── contact_query.md  # CONTACT query examples
```

### Known Gotchas & Library Quirks
```python
# CRITICAL: vLLM requires CUDA 11.8+ and specific GPU memory
# CRITICAL: Unstructured OCR requires tesseract system package
# CRITICAL: LangExtract needs local model endpoint configured
# CRITICAL: FastAPI endpoints must be async for performance
# CRITICAL: pgvector requires CREATE EXTENSION in PostgreSQL
# CRITICAL: Redis TTL=0 means bypass cache (for FORM queries)
# GOTCHA: Alembic autogenerate doesn't detect all changes
# GOTCHA: GPT-OSS 20B needs ~40GB VRAM (use quantization)
```

## Implementation Blueprint

### Data Models and Structure

```python
# src/models/query_types.py
from enum import Enum

class QueryType(Enum):
    CONTACT_LOOKUP = "contact"
    FORM_RETRIEVAL = "form"
    PROTOCOL_STEPS = "protocol"
    CRITERIA_CHECK = "criteria"
    DOSAGE_LOOKUP = "dosage"
    SUMMARY_REQUEST = "summary"

# src/models/entities.py
from sqlalchemy import Column, String, Text, JSON, DateTime, ForeignKey, Integer
from sqlalchemy.ext.declarative import declarative_base
from pgvector.sqlalchemy import Vector

Base = declarative_base()

class Document(Base):
    __tablename__ = "documents"
    id = Column(String, primary_key=True)
    filename = Column(String, nullable=False)
    content_type = Column(String)  # protocol|form|contact|reference
    file_type = Column(String)  # pdf|docx|txt|md
    content = Column(Text)
    metadata = Column(JSON)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    id = Column(String, primary_key=True)
    document_id = Column(String, ForeignKey("documents.id"))
    chunk_text = Column(Text)
    chunk_index = Column(Integer)
    embedding = Column(Vector(384))
    chunk_type = Column(String)
    medical_category = Column(String)
    urgency_level = Column(String)
    contains_contact = Column(Boolean)
    contains_dosage = Column(Boolean)
    created_at = Column(DateTime)

# src/models/schemas.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    session_id: Optional[str] = None

class QueryResponse(BaseModel):
    response: str
    query_type: str
    confidence: float
    sources: List[str]
    warnings: Optional[List[str]] = None
    processing_time: float
```

### List of Tasks to Complete (In Order)

```yaml
Task 1: Setup Database and Alembic
CREATE alembic.ini:
  - Configure PostgreSQL connection
  - Set autogenerate options
  
CREATE alembic/env.py:
  - Import models from src.models.entities
  - Configure target_metadata
  
CREATE src/models/__init__.py:
  - Export all models
  
CREATE src/models/entities.py:
  - Define Document, DocumentChunk, DocumentRegistry, ExtractedEntities tables
  - Add indexes for performance
  
RUN: alembic revision --autogenerate -m "Initial schema"
RUN: alembic upgrade head

Task 2: Implement Configuration and Utilities
CREATE src/config/settings.py:
  - Load environment variables with pydantic-settings
  - Define Settings class with validation
  
CREATE src/utils/logging.py:
  - Setup structured logging with PHI scrubbing
  - Configure log levels per environment
  
CREATE src/cache/redis_client.py:
  - Redis connection pool
  - TTL configuration per query type

Task 3: Build LLM Clients
CREATE src/ai/gpt_oss_client.py:
  - vLLM client with httpx
  - Implement generate() with temperature=0.0, top_p=0.1
  - Add retry logic with exponential backoff
  
CREATE src/ai/prompts.py:
  - Classification prompt template
  - Response generation prompts per query type
  - Medical safety prompts

Task 4: Document Ingestion Pipeline
CREATE src/ingestion/unstructured_runner.py:
  - Parse PDFs with strategy="hi_res"
  - Enable OCR with pytesseract
  - Extract tables with infer_table_structure=True
  
CREATE src/ingestion/langextract_runner.py:
  - Configure local model adapter
  - Define extraction schemas for contacts, dosages, protocols
  - Preserve citations with page/span info
  
CREATE src/ingestion/tasks.py:
  - Worker task to process documents
  - Store raw text and chunks in database
  - Generate embeddings for semantic search

Task 5: Query Classification and Routing
CREATE src/pipeline/classifier.py:
  - Implement classify_query() using LLM
  - Map to QueryType enum
  - Add confidence scoring
  
CREATE src/pipeline/router.py:
  - Route queries based on classification
  - Implement retrieval strategies per type:
    - CONTACT: Amion API + fallback
    - FORM: Document registry exact match
    - PROTOCOL: Semantic + keyword hybrid
    - CRITERIA: Semantic with threshold
    - DOSAGE: Exact match + validation
    - SUMMARY: Multi-source aggregation

Task 6: Response Formatting and Validation
CREATE src/pipeline/response_formatter.py:
  - Format responses with citations
  - Add PDF links for FORM queries: [PDF:/api/v1/documents/pdf/{filename}|{display_name}]
  - Include source documents
  
CREATE src/validation/medical_validator.py:
  - Validate dosages against safe ranges
  - Check protocol completeness
  - Flag low-confidence responses
  
CREATE src/validation/hipaa.py:
  - PHI detection and scrubbing
  - Audit log generation

Task 7: FastAPI Application
CREATE src/api/app.py:
  - FastAPI app with CORS, security headers
  - Add middleware for logging and metrics
  - Configure exception handlers
  
CREATE src/api/endpoints.py:
  - POST /query endpoint
  - GET /health with service checks
  - GET /documents/pdf/{filename} for PDF serving
  - Admin endpoints for registry and validation
  
CREATE src/api/dependencies.py:
  - Database session management
  - Cache client injection
  - Authentication (if needed)

Task 8: Query Processing Pipeline
CREATE src/pipeline/query_processor.py:
  - Orchestrate classify → retrieve → respond flow
  - Handle caching (bypass for FORM)
  - Add metrics and logging
  - Implement error handling

Task 9: Contact Services
CREATE src/services/amion_client.py:
  - Mock Amion API integration
  - Parse on-call schedules
  
CREATE src/services/contact_lookup.py:
  - Combine Amion data with document extracts
  - Format contact responses

Task 10: Scripts and Examples
CREATE scripts/seed_registry.py:
  - Scan docs/ directory
  - Populate document_registry table
  - Map keywords to documents
  
CREATE examples/forms_query.md:
  - Example: "show me the blood transfusion form"
  - Expected: PDF link with proper formatting
  
CREATE examples/protocol_query.md:
  - Example: "what is the ED stemi protocol"
  - Expected: Steps with timing and contacts
  
CREATE examples/contact_query.md:
  - Example: "who is on call for cardiology"
  - Expected: Current contact information

Task 11: Testing Suite
CREATE tests/unit/test_classifier.py:
  - Test all 6 query types
  - Test edge cases and ambiguous queries
  
CREATE tests/unit/test_formatter.py:
  - Test PDF link generation
  - Test citation formatting
  
CREATE tests/integration/test_pipeline.py:
  - End-to-end query processing
  - Test caching behavior
  
CREATE tests/fixtures/sample_docs.py:
  - Sample medical documents
  - Mock LLM responses
```

### Per-Task Pseudocode

```python
# Task 5: Query Classification
# src/pipeline/classifier.py
import asyncio
from src.models.query_types import QueryType
from src.ai.gpt_oss_client import GPTOSSClient
from src.ai.prompts import CLASSIFICATION_PROMPT

class QueryClassifier:
    def __init__(self, llm_client: GPTOSSClient):
        self.llm = llm_client
    
    async def classify_query(self, query: str) -> tuple[QueryType, float]:
        # Build classification prompt
        prompt = CLASSIFICATION_PROMPT.format(query=query)
        
        # Get LLM response with deterministic settings
        response = await self.llm.generate(
            prompt=prompt,
            temperature=0.0,
            top_p=0.1,
            max_tokens=50
        )
        
        # Parse classification and confidence
        # Map to QueryType enum
        # Return (query_type, confidence)

# Task 6: Response Formatting
# src/pipeline/response_formatter.py
class ResponseFormatter:
    def format_form_response(self, documents: List[Document]) -> str:
        # CRITICAL: Must include PDF links
        response_parts = []
        for doc in documents:
            pdf_link = f"[PDF:/api/v1/documents/pdf/{doc.filename}|{doc.display_name}]"
            response_parts.append(f"• {doc.display_name}: {pdf_link}")
        
        return "\n".join(response_parts)
    
    def format_protocol_response(self, protocol_data: Dict) -> str:
        # Include steps, timing, contacts
        # Preserve all citations
        # Add medical warnings if needed

# Task 7: PDF Serving Endpoint
# src/api/endpoints.py
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter()

@router.get("/documents/pdf/{filename}")
async def serve_pdf(filename: str):
    # CRITICAL: Validate filename to prevent path traversal
    safe_filename = validate_filename(filename)
    file_path = f"/app/docs/{safe_filename}"
    
    if not os.path.exists(file_path):
        raise HTTPException(404, "Document not found")
    
    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename={safe_filename}"
        }
    )
```

### Integration Points
```yaml
DATABASE:
  - migration: "CREATE EXTENSION IF NOT EXISTS vector"
  - migration: "Create all tables with proper indexes"
  - seed: "Run scripts/seed_registry.py after migrations"
  
CONFIG:
  - copy: "cp EDBOTv8.env.example .env"
  - edit: "Set LLM_BACKEND=gpt-oss"
  - edit: "Configure DB credentials"
  
DOCKER:
  - command: "docker compose -f docker-compose.v8.yml up -d"
  - verify: "docker compose ps" shows all services healthy
  
ROUTES:
  - mount: "app.include_router(api_router)"
  - prefix: "/api/v1"
```

## Validation Loop

### Level 1: Syntax & Style
```bash
# Setup virtual environment first
make bootstrap
source .venv/bin/activate

# Check Python syntax
python -m py_compile src/**/*.py

# Run linting (if ruff installed)
ruff check src/ --fix

# Type checking (if mypy installed)
mypy src/ --ignore-missing-imports

# Expected: No errors
```

### Level 2: Database and Migrations
```bash
# Start database service
docker compose -f docker-compose.v8.yml up -d db

# Run migrations
alembic upgrade head

# Verify tables created
docker compose exec db psql -U edbot -d edbot -c "\dt"

# Expected: See all tables (documents, document_chunks, etc.)
```

### Level 3: Unit Tests
```python
# tests/unit/test_classifier.py
import pytest
from src.pipeline.classifier import QueryClassifier
from src.models.query_types import QueryType

@pytest.fixture
def classifier():
    # Mock LLM client
    return QueryClassifier(mock_llm_client)

async def test_classify_form_query(classifier):
    result, confidence = await classifier.classify_query("show me the blood transfusion form")
    assert result == QueryType.FORM_RETRIEVAL
    assert confidence > 0.9

async def test_classify_protocol_query(classifier):
    result, confidence = await classifier.classify_query("what is the ED stemi protocol")
    assert result == QueryType.PROTOCOL_STEPS
    assert confidence > 0.9

async def test_classify_contact_query(classifier):
    result, confidence = await classifier.classify_query("who is on call for cardiology")
    assert result == QueryType.CONTACT_LOOKUP
    assert confidence > 0.9
```

```bash
# Run tests
pytest tests/unit/ -v

# Expected: All tests pass
```

### Level 4: Integration Test
```bash
# Start all services
make up

# Wait for services to be ready
sleep 10

# Check health
curl http://localhost:8001/health | jq

# Test FORM query
curl -X POST http://localhost:8001/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "show me the blood transfusion form"}' | jq

# Expected: Response with PDF link format

# Test PDF endpoint
curl -I http://localhost:8001/api/v1/documents/pdf/blood_transfusion_form.pdf

# Expected: 200 OK with application/pdf content-type

# Test PROTOCOL query
curl -X POST http://localhost:8001/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "what is the ED stemi protocol"}' | jq

# Expected: Protocol steps with timing and contacts
```

### Level 5: Performance Validation
```bash
# Measure response times
time curl -X POST http://localhost:8001/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "show me a form"}' 

# Expected: < 1.5s for FORM queries (no LLM needed)

# Check cache behavior
# First query (cache miss)
time curl -X POST http://localhost:8001/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "what is the sepsis protocol"}'

# Second identical query (should be cached for PROTOCOL)
time curl -X POST http://localhost:8001/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "what is the sepsis protocol"}'

# Expected: Second query faster (cache hit)
```

## Final Validation Checklist
- [ ] All unit tests pass: `pytest tests/unit/ -v`
- [ ] Integration tests pass: `pytest tests/integration/ -v`
- [ ] No linting errors: `ruff check src/`
- [ ] Database migrations applied: `alembic upgrade head`
- [ ] Health check passes: `curl http://localhost:8001/health`
- [ ] FORM queries return PDF links
- [ ] PROTOCOL queries include timing and contacts
- [ ] CONTACT queries return current information
- [ ] Response time <1.5s for non-LLM queries
- [ ] Citations preserved in all responses
- [ ] No PHI in logs (check with grep)
- [ ] Docker services all healthy: `docker compose ps`

---

## Anti-Patterns to Avoid
- ❌ Don't cache FORM query results
- ❌ Don't use external LLMs for PHI-containing queries
- ❌ Don't remove source citations from responses
- ❌ Don't use sync database operations in async endpoints
- ❌ Don't hardcode file paths or credentials
- ❌ Don't skip medical validation for dosage queries
- ❌ Don't return descriptions instead of actual PDFs for FORM queries
- ❌ Don't use temperature > 0 for medical responses

## Implementation Notes

### Critical Success Factors
1. **PDF Handling**: FORM queries must return `[PDF:/api/v1/documents/pdf/{filename}|{display_name}]` format
2. **Citation Preservation**: Every medical fact must reference source document
3. **Cache Policy**: Always bypass cache for FORM queries
4. **HIPAA Compliance**: Use LOG_SCRUB_PHI=true and DISABLE_EXTERNAL_CALLS=true
5. **Deterministic LLM**: temperature=0.0, top_p=0.1 for medical consistency

### Common Issues and Solutions
- **Issue**: vLLM won't start → **Solution**: Check GPU memory, use quantization
- **Issue**: OCR fails → **Solution**: Install tesseract system package
- **Issue**: Slow responses → **Solution**: Check LLM cold start, add warmup
- **Issue**: PDFs 404 → **Solution**: Verify docs/ volume mount in docker-compose
- **Issue**: Classification errors → **Solution**: Improve prompts, add examples

### Performance Optimization
- Use connection pooling for database
- Batch document processing in worker
- Index commonly queried fields
- Pre-generate embeddings during ingestion
- Use Redis pipelining for multiple cache operations

## Confidence Score: 9/10

This PRP provides comprehensive context for implementing ED Bot v8 with:
- Complete file structure and responsibilities
- Detailed task breakdown in implementation order
- Critical gotchas and medical safety requirements
- Executable validation commands
- Integration points clearly defined
- Anti-patterns to avoid

The implementation should succeed in one pass with this level of detail and context.