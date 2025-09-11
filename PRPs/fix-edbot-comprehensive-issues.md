# PRP: Fix ED Bot v8 Comprehensive Issues

## Problem Description
The ED Bot v8 system has multiple critical issues preventing production readiness:
1. Import errors preventing full stack from running
2. Text extraction not implemented (PDFs/DOCX using placeholders)
3. Vector embeddings not connected to retrieval
4. LLM not integrated with query processing
5. Query responses returning incorrect content

## Success Criteria
- [ ] Full API stack runs without import errors
- [ ] PDF/DOCX text extraction working
- [ ] Vector embeddings generated and stored for all documents
- [ ] LLM generates dynamic responses based on retrieved content
- [ ] All 6 query types return accurate, relevant responses
- [ ] All existing tests pass
- [ ] No breaking changes to working emergency_api.py

## Technical Context

### Existing Infrastructure
The codebase already has most components but they're not connected:

**Embedding Infrastructure (Already Present):**
- `src/cache/embedding_service.py` - Embedding service interface
- `src/models/entities.py` - pgvector columns (384-dim) configured
- Vector columns: `DocumentChunk.embedding`, `DocumentRegistry.content_vector`

**LLM Clients (Already Present):**
- `src/ai/ollama_client.py` - Ollama integration
- `src/ai/llm_client.py` - Unified LLM interface
- Medical prompts in `src/ai/medical_prompts.py`

**Text Processing (Partially Present):**
- `src/ingestion/pdf_processor.py` - PDF processing skeleton
- `src/ingestion/unstructured_runner.py` - Unstructured integration

**Retrieval Systems (Already Present):**
- `src/pipeline/rag_retriever.py` - RAG retrieval
- `src/pipeline/hybrid_retriever.py` - Hybrid search
- `src/pipeline/enhanced_medical_retriever.py` - Medical-specific retrieval

### Root Cause Analysis

**Import Errors:**
Files using incorrect relative imports (missing `src.` prefix):
- `src/pipeline/query_processor.py:11` - `from cache.semantic_cache` should be `from src.cache.semantic_cache`
- `src/search/elasticsearch_client.py:6` - `from config.settings` should be `from src.config.settings`

**Text Extraction Missing:**
- Libraries not installed: PyPDF2, python-docx, pdfplumber
- `mass_seeder.py` creates placeholder content instead of extracting real text

**Vector Search Not Connected:**
- Embeddings not generated during document seeding
- RAGRetriever using text search fallback instead of vector similarity

**LLM Not Integrated:**
- `emergency_api.py` returns pre-formatted responses
- Not calling LLM client for response generation

## Implementation Blueprint

### Phase 1: Fix Import Errors (Non-Breaking)
```python
# Fix pattern - Add src. prefix to all absolute imports
# FROM: from cache.semantic_cache import SemanticCache
# TO:   from src.cache.semantic_cache import SemanticCache

# Files to fix:
# - src/pipeline/query_processor.py
# - src/search/elasticsearch_client.py
# - src/ingestion/tasks.py (if needed)
```

### Phase 2: Verify Extraction Libraries (Already Installed)
```bash
# Libraries already present in requirements.v8.txt:
unstructured[pdf,ocr]>=0.15.0  # Document parsing with medical optimization
pytesseract>=0.3.10           # OCR for scanned documents  
pdf2image>=1.17.0             # PDF to image conversion
PyMuPDF>=1.24.0               # Precise PDF position tracking
langextract>=1.0.4            # Structured entity extraction
```

### Phase 3: Connect Existing Text Extraction Infrastructure
```python
# Use existing src/ingestion/unstructured_runner.py and langextract_runner.py
# These are already implemented with medical-optimized settings

from src.ingestion.unstructured_runner import UnstructuredRunner
from src.ingestion.langextract_runner import LangExtractRunner

class EnhancedDocumentProcessor:
    """Connects existing extraction infrastructure."""
    
    def __init__(self):
        self.unstructured_runner = UnstructuredRunner()  # Already implemented
        self.langextract_runner = LangExtractRunner()    # Already implemented
    
    async def process_document(self, file_path: Path) -> ParsedDocument:
        """Extract text and entities using existing runners."""
        # Use existing UnstructuredRunner for text extraction
        parsed_doc = await self.unstructured_runner.parse_document(str(file_path))
        
        # Use existing LangExtractRunner for entity extraction  
        entities = await self.langextract_runner.extract_entities(
            text=parsed_doc.content,
            document_id=parsed_doc.filename
        )
        
        # Attach extracted entities to document
        parsed_doc.entities = entities
        
        return parsed_doc
```

### Phase 4: Generate and Store Embeddings
```python
# Use existing src/cache/embedding_service.py infrastructure
from src.cache.embedding_service import EmbeddingService
from sentence_transformers import SentenceTransformer

class EnhancedSeeder:
    def __init__(self):
        # Use all-MiniLM-L6-v2 for 384-dim embeddings (matches pgvector columns)
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.embedding_service = EmbeddingService(self.model)
        self.document_processor = EnhancedDocumentProcessor()
    
    async def seed_with_embeddings(self, doc_path: Path):
        # Use existing extraction infrastructure
        parsed_doc = await self.document_processor.process_document(doc_path)
        
        # Generate embeddings for each chunk (chunks already created by UnstructuredRunner)
        for chunk_info in parsed_doc.chunks:
            chunk_text = chunk_info['text']
            embedding = await self.embedding_service.embed(chunk_text)
            
            # Store in database with embedding using existing schema
            chunk = DocumentChunk(
                chunk_text=chunk_text,
                embedding=embedding,  # pgvector column (384-dim)
                chunk_index=chunk_info['chunk_index'],
                medical_category=chunk_info.get('medical_category'),
                urgency_level=chunk_info.get('urgency_level', 'routine'),
                contains_contact=chunk_info.get('contains_contact', False),
                contains_dosage=chunk_info.get('contains_dosage', False),
                metadata=chunk_info.get('metadata', {})
            )
            session.add(chunk)
```

### Phase 5: Connect Vector Search to Retrieval
```python
# src/pipeline/enhanced_rag_retriever.py
from sqlalchemy import func
from pgvector.sqlalchemy import Vector

class EnhancedRAGRetriever:
    async def vector_search(self, query: str, k: int = 5):
        # Generate query embedding
        query_embedding = await self.embedding_service.embed(query)
        
        # Use pgvector similarity search
        results = session.query(DocumentChunk).order_by(
            DocumentChunk.embedding.cosine_distance(query_embedding)
        ).limit(k).all()
        
        return results
```

### Phase 6: Integrate LLM for Response Generation
```python
# src/pipeline/llm_query_processor.py
from src.ai.ollama_client import OllamaClient
from src.ai.medical_prompts import MEDICAL_RESPONSE_PROMPT

class LLMQueryProcessor:
    def __init__(self):
        self.llm_client = OllamaClient(model="llama3.1:8b")
        
    async def process_query(self, query: str, query_type: str):
        # 1. Classify query
        classification = self.classifier.classify(query)
        
        # 2. Retrieve relevant content
        retrieved_docs = await self.retriever.vector_search(query)
        
        # 3. Build context
        context = "\n".join([doc.chunk_text for doc in retrieved_docs])
        
        # 4. Generate response with LLM
        prompt = MEDICAL_RESPONSE_PROMPT.format(
            query=query,
            context=context,
            query_type=query_type
        )
        
        response = await self.llm_client.generate(prompt)
        
        # 5. Add sources and metadata
        return QueryResponse(
            response=response,
            query_type=query_type,
            sources=[doc.source_info for doc in retrieved_docs],
            confidence=classification.confidence
        )
```

## Validation Gates

### Pre-Implementation Checks
```bash
# Check current state
python3 emergency_api.py  # Should be working
curl http://localhost:8001/health  # Should return OK
```

### Phase 1 Validation - Import Fixes
```bash
# Test imports are fixed
python3 -c "from src.pipeline.query_processor import QueryProcessor; print('✅ Imports fixed')"

# Try running full stack
python3 -m uvicorn src.api.app:app --host 0.0.0.0 --port 8002
curl http://localhost:8002/health
```

### Phase 2-3 Validation - Text Extraction
```bash
# Libraries already installed in requirements.v8.txt - verify installation
python3 -c "
import unstructured
import langextract
print('✅ Libraries available')
"

# Test extraction with existing infrastructure
python3 -c "
from src.ingestion.unstructured_runner import UnstructuredRunner
from pathlib import Path
import asyncio

async def test():
    runner = UnstructuredRunner()
    pdf_path = Path('docs/STEMI_Activation.pdf')  
    parsed_doc = await runner.parse_document(str(pdf_path))
    print(f'Extracted {len(parsed_doc.content)} characters')
    print(f'Created {len(parsed_doc.chunks)} chunks')
    assert len(parsed_doc.content) > 100, 'Text extraction failed'
    print('✅ Unstructured text extraction working')

asyncio.run(test())
"
```

### Phase 4 Validation - Embeddings  
```bash
# First install sentence-transformers if not present
pip install sentence-transformers

# Test embedding generation with existing service
python3 -c "
from src.cache.embedding_service import EmbeddingService
from sentence_transformers import SentenceTransformer
import asyncio

async def test():
    model = SentenceTransformer('all-MiniLM-L6-v2')
    service = EmbeddingService(model)
    embedding = await service.embed('test medical text')
    assert embedding.shape == (384,), f'Wrong shape: {embedding.shape}'
    print('✅ Embeddings working with existing service')

asyncio.run(test())
"

# Check embeddings in database
python3 -c "
from src.models.database import get_db_session
from src.models.entities import DocumentChunk
with get_db_session() as session:
    chunk = session.query(DocumentChunk).filter(
        DocumentChunk.embedding.isnot(None)
    ).first()
    if chunk:
        print('✅ Embeddings stored in database')
    else:
        print('❌ No embeddings found')
"
```

### Phase 5 Validation - Vector Search
```bash
# Test vector search
python3 -c "
import asyncio
from src.pipeline.enhanced_rag_retriever import EnhancedRAGRetriever

async def test():
    retriever = EnhancedRAGRetriever()
    results = await retriever.vector_search('STEMI protocol', k=3)
    assert len(results) > 0, 'No results from vector search'
    print(f'✅ Vector search returned {len(results)} results')

asyncio.run(test())
"
```

### Phase 6 Validation - LLM Integration
```bash
# Test LLM response generation
curl -X POST http://localhost:8001/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "what is the STEMI protocol"}' | \
  python3 -c "
import json, sys
data = json.load(sys.stdin)
# Check response is not the canned template
assert 'Model Selection' not in data['response']
assert len(data['response']) > 500
print('✅ LLM generating dynamic responses')
"
```

### Final Integration Tests
```bash
# Run unit tests
python3 -m pytest tests/unit/test_classifier.py -v
python3 -m pytest tests/unit/test_query_processor.py -v

# Run integration tests
python3 -m pytest tests/integration/test_api_endpoints.py -v

# Test all 6 query types
python3 scripts/test_all_query_types.py
```

## Implementation Order

1. **Fix Import Errors** (30 min)
   - Update all incorrect imports with `src.` prefix
   - Test full API stack starts

2. **Install Text Extraction** (15 min)
   - Add libraries to requirements.txt
   - pip install new dependencies

3. **Implement Text Extraction** (1 hour)
   - Create DocumentExtractor class
   - Update seeders to use real text

4. **Re-seed Documents with Real Text** (1 hour)
   - Run enhanced seeder on all 337 documents
   - Verify text extraction quality

5. **Generate and Store Embeddings** (1 hour)
   - Install sentence-transformers
   - Generate embeddings during seeding
   - Store in pgvector columns

6. **Connect Vector Search** (1 hour)
   - Update RAGRetriever to use vector similarity
   - Test retrieval accuracy

7. **Integrate LLM** (2 hours)
   - Create LLMQueryProcessor
   - Connect to Ollama
   - Generate dynamic responses

8. **Test and Validate** (1 hour)
   - Run all validation gates
   - Fix any issues
   - Verify all query types work

## Risk Mitigation

1. **Keep emergency_api.py working** 
   - All changes in new files or behind feature flags
   - Test emergency API after each phase

2. **Database Migrations**
   - pgvector columns already exist
   - Only updating data, not schema

3. **Performance**
   - Embedding generation is one-time during seeding
   - Vector search is fast with proper indexing
   - Cache LLM responses in Redis

4. **Backwards Compatibility**
   - Keep both text and vector search
   - Fallback to text if vectors not available
   - Emergency API remains unchanged

## External Documentation

- **pgvector**: https://github.com/pgvector/pgvector
- **Sentence Transformers**: https://www.sbert.net/docs/pretrained_models.html
- **PyPDF2**: https://pypdf2.readthedocs.io/en/3.0.0/
- **python-docx**: https://python-docx.readthedocs.io/
- **Ollama API**: https://github.com/ollama/ollama/blob/main/docs/api.md

## Success Metrics

- Import errors: 0
- Text extraction success rate: >95%
- Vector search relevance: >80% accuracy
- LLM response quality: Coherent, medically accurate
- Query type accuracy: >90%
- API response time: <2 seconds
- All tests passing: 100%

## Confidence Score: 8/10

High confidence because:
- Infrastructure already exists (pgvector, embedding service, LLM clients)
- Clear root causes identified (import errors, missing libraries)
- Incremental approach with validation at each phase
- No schema changes required
- Emergency API preserved as fallback

Minor risks:
- PDF extraction quality varies by document
- LLM response quality depends on retrieval accuracy
- Some integration complexity between components