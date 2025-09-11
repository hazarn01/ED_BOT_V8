# PRP-32: Fix Unstructured Document Seeding Pipeline with 6-Category Schema

## Goal
Fix the broken unstructured document seeding pipeline to properly process real medical documents from `/docs` folder through the complete ingestion workflow (Unstructured → LangExtract → PostgreSQL with registry) and map them to the 6-category query type schema.

## Why
- Current seeding only creates fake hardcoded documents, not real processed content
- GPT-OSS backend is now working but lacks real medical document content
- Unstructured pipeline worked previously but is now broken due to missing system dependencies
- Document registry exists but isn't being populated with proper categorization
- Need real medical content mapped to 6 query types: CONTACT, FORM, PROTOCOL, CRITERIA, DOSAGE, SUMMARY

## What
Restore and enhance the document processing pipeline to:
1. **Fix system dependencies** causing unstructured parsing failures
2. **Process real documents** from `/docs` through unstructured pipeline  
3. **Auto-categorize documents** into the 6 query types based on content analysis
4. **Populate document registry** with proper metadata and keywords
5. **Validate end-to-end** that documents are accessible by query processor

### Success Criteria
- [ ] Unstructured pipeline processes PDFs without "poppler" errors
- [ ] All 338 documents in `/docs` are successfully ingested
- [ ] Documents are automatically categorized into 6 query types
- [ ] Document registry is populated with searchable keywords
- [ ] Query processor can retrieve documents for all 6 query types
- [ ] Medical content quality matches or exceeds current hardcoded examples

## All Needed Context

### Core Issue Identified
```bash
# Current error from unstructured pipeline:
ERROR: "Document parsing failed: Unable to get page count. Is poppler installed and in PATH?"

# Root cause: Missing system dependencies in local dev environment
# Dockerfile.v8 has them but local env doesn't:
RUN apt-get install -y \
    tesseract-ocr \
    poppler-utils \  # <-- This is missing locally
    libmagic1
```

### Documentation & References
```yaml
- file: src/ingestion/tasks.py
  why: Main processing pipeline - DocumentProcessor class handles full workflow
  critical: Uses UnstructuredRunner → LangExtractRunner → PostgreSQL storage
  
- file: src/ingestion/unstructured_runner.py  
  why: Handles PDF parsing with medical-optimized settings
  critical: Requires poppler-utils for PDF page counting
  
- file: src/models/entities.py
  why: Document, DocumentChunk, DocumentRegistry models
  lines: 29-50, 113-130
  
- file: src/models/query_types.py
  why: 6 query type enum (contact|form|protocol|criteria|dosage|summary)
  critical: Documents must map to these categories
  
- file: scripts/seed_documents.py
  why: Current fake seeding approach to be replaced
  critical: Shows expected document structure and metadata patterns
  
- file: Dockerfile.v8  
  why: Shows required system dependencies
  lines: 6-11
  critical: poppler-utils, tesseract-ocr, libmagic1 needed
  
- file: requirements.v8.txt
  why: Python packages for document processing
  lines: 16-22
  critical: unstructured[pdf,ocr], pytesseract, pdf2image, PyMuPDF

- file: src/pipeline/classifier.py
  why: Query classification patterns for 6 types
  critical: Understanding how content maps to query types
```

### Current Codebase Structure
```bash
src/
├── ingestion/
│   ├── tasks.py              # DocumentProcessor - main pipeline orchestrator
│   ├── unstructured_runner.py # PDF parsing (BROKEN - needs poppler)
│   ├── langextract_runner.py  # Entity extraction
│   └── table_extractor.py     # Table processing (PRP 19)
├── models/
│   ├── entities.py           # Document, DocumentRegistry ORM models  
│   ├── query_types.py        # 6-category enum
│   └── document_models.py    # Pydantic models for parsing
└── pipeline/
    ├── classifier.py         # Maps queries to 6 types
    └── router.py            # Routes to appropriate handlers

scripts/
└── seed_documents.py        # OLD fake seeding (to be enhanced)

docs/                         # 338 real medical documents to process
├── STEMI Activation.pdf
├── ED Sepsis Pathway.pdf  
├── Hypoglycemia_EBP_Final_10_2024.pdf
└── ... (335 more files)
```

### Desired Enhancement
```bash
# NEW files to add:
scripts/
├── seed_real_documents.py   # Enhanced seeding with unstructured pipeline
└── classify_document_types.py # Auto-categorization logic

src/ingestion/
└── content_classifier.py    # Document → query type mapping logic

# ENHANCED existing files:
scripts/seed_documents.py    # Switch to real document processing
src/ingestion/tasks.py       # Enhanced registry integration  
```

### Known Gotchas & Library Quirks
```python
# CRITICAL: Unstructured requires system dependencies
# - poppler-utils: For PDF page counting and conversion
# - tesseract-ocr: For OCR on scanned PDFs  
# - libmagic1: For file type detection
# Missing these causes runtime failures, not import errors

# GOTCHA: Document processing is SLOW
# - 338 documents × ~2-3 seconds each = ~15-20 minutes total
# - Use async processing but don't overwhelm the system
# - Add progress tracking and resumable processing

# CRITICAL: Content type inference logic
# From tasks.py:408, current logic is basic filename pattern matching
# Need sophisticated classification based on actual content + metadata

# GOTCHA: PostgreSQL connection management  
# tasks.py uses sessionmaker - ensure proper session cleanup
# Bulk operations may hit connection limits with 338 files

# MEDICAL DOMAIN: Document categorization patterns
# FORM: consent, checklist, template, agreement
# PROTOCOL: procedure, algorithm, pathway, guideline  
# CONTACT: directory, phone, pager, on-call
# CRITERIA: rules, score, threshold, indication
# DOSAGE: medication, drug, dose, administration
# SUMMARY: overview, guide, manual, handbook
```

## Implementation Blueprint

### Data Models Enhancement
```python
# Enhance DocumentRegistry for better categorization
class DocumentRegistry(Base):
    # Existing fields...
    category = Column(String)  # Maps to QueryType values
    
    # ADD enhanced categorization fields:
    query_type = Column(String)  # Direct QueryType enum value
    confidence = Column(Float, default=0.0)  # Classification confidence  
    classification_method = Column(String)  # 'filename'|'content'|'hybrid'
    medical_specialty = Column(String)  # cardiology|emergency|etc
    urgency_level = Column(String)  # stat|urgent|routine
    
    # Enhanced keyword extraction
    primary_keywords = Column(JSON, default=[])  # High-confidence terms
    medical_terms = Column(JSON, default=[])     # Medical terminology
    abbreviations = Column(JSON, default=[])     # Common ED abbreviations
```

### Task List (Implementation Order)

```yaml
Task 1: Install Missing System Dependencies
ACTION: Install poppler-utils and tesseract-ocr locally
COMMANDS:
  - sudo apt-get update
  - sudo apt-get install -y poppler-utils tesseract-ocr libmagic1
VALIDATION: pdftoppm --help (should not error)
WHY: Fixes core unstructured parsing failures

Task 2: Create Enhanced Content Classification Logic  
CREATE: src/ingestion/content_classifier.py
PATTERN: Mirror from src/pipeline/classifier.py query patterns
PURPOSE: Auto-map documents to 6 query types based on comprehensive analysis
METHODS:
  - classify_by_filename()  # Pattern matching on titles
  - classify_by_content()   # Medical terminology analysis  
  - classify_hybrid()       # Combine multiple signals
  - extract_medical_metadata()  # Specialty, urgency, etc

Task 3: Enhance DocumentProcessor Registry Integration
MODIFY: src/ingestion/tasks.py
TARGET: DocumentProcessor._update_registry() method (lines 365-406)
CHANGES:
  - Integrate ContentClassifier for query type mapping
  - Extract medical terminology and abbreviations
  - Set confidence scores and classification method
  - Map to medical specialties (cardiology, emergency, etc)
PRESERVE: Existing registry creation pattern

Task 4: Create Enhanced Real Document Seeding Script
CREATE: scripts/seed_real_documents.py  
PURPOSE: Replace fake document creation with real document processing
FEATURES:
  - Progress tracking with resumable processing
  - Bulk processing with connection pooling
  - Comprehensive categorization validation
  - Error handling and retry logic
PATTERN: Use async processing from src/ingestion/tasks.py

Task 5: Add Document Registry Migration
CREATE: alembic/versions/xxx_enhance_document_registry.py
PURPOSE: Add new categorization fields to document_registry table
FIELDS: query_type, confidence, classification_method, medical_specialty, etc
PATTERN: Follow existing migration structure

Task 6: Validation Scripts
CREATE: scripts/validate_document_seeding.py
PURPOSE: Comprehensive testing of seeded documents
TESTS:
  - All 6 query types have representative documents
  - Document content quality meets medical standards  
  - Registry keywords enable proper search
  - End-to-end query processing works
```

### Task 2 Pseudocode: Content Classification Logic
```python
# src/ingestion/content_classifier.py

class ContentClassifier:
    """Maps medical documents to 6 query types with confidence scoring."""
    
    # Medical terminology patterns for each query type
    FORM_PATTERNS = [
        "consent", "form", "checklist", "template", "agreement",
        "admission", "discharge", "transfusion", "procedure consent"
    ]
    
    PROTOCOL_PATTERNS = [
        "protocol", "pathway", "algorithm", "guideline", "procedure",
        "stemi", "sepsis", "stroke", "trauma", "activation"  
    ]
    
    CONTACT_PATTERNS = [
        "on-call", "directory", "contact", "pager", "phone",
        "cardiology", "who is on call", "coverage"
    ]
    
    # ... similar for CRITERIA, DOSAGE, SUMMARY
    
    def classify_document(self, parsed_doc: ParsedDocument) -> DocumentClassification:
        """Primary classification method combining multiple signals."""
        
        # Multi-signal classification
        filename_result = self._classify_by_filename(parsed_doc.filename)
        content_result = self._classify_by_content(parsed_doc.content)
        metadata_result = self._classify_by_metadata(parsed_doc.metadata)
        
        # Weighted scoring (content > filename > metadata)
        final_classification = self._combine_classifications([
            (content_result, 0.6),
            (filename_result, 0.3), 
            (metadata_result, 0.1)
        ])
        
        return final_classification
    
    def _classify_by_content(self, content: str) -> Classification:
        """Content-based classification using medical terminology."""
        content_lower = content.lower()
        scores = {}
        
        # Score each query type based on keyword presence
        for query_type in QueryType:
            patterns = self._get_patterns_for_type(query_type)
            score = sum(content_lower.count(pattern) for pattern in patterns)
            scores[query_type] = score
            
        # Get highest scoring type with confidence
        best_type = max(scores, key=scores.get)
        total_signals = sum(scores.values())
        confidence = scores[best_type] / total_signals if total_signals > 0 else 0.0
        
        return Classification(
            query_type=best_type,
            confidence=confidence, 
            method="content",
            evidence=self._extract_evidence(content, best_type)
        )
```

### Task 4 Pseudocode: Enhanced Seeding Script
```python
# scripts/seed_real_documents.py

async def main():
    """Process all real medical documents with categorization."""
    
    # Progress tracking
    progress_file = Path("seeding_progress.json")
    processed_files = load_progress(progress_file)
    
    # Find all documents to process
    docs_path = Path("/mnt/d/Dev/EDbotv8/docs")  
    all_files = list(docs_path.glob("*.pdf"))
    remaining_files = [f for f in all_files if str(f) not in processed_files]
    
    print(f"Found {len(all_files)} total documents")
    print(f"Processing {len(remaining_files)} remaining documents")
    
    # Process in batches to avoid overwhelming system
    batch_size = 10
    processor = DocumentProcessor()
    
    for i in range(0, len(remaining_files), batch_size):
        batch = remaining_files[i:i + batch_size]
        print(f"Processing batch {i//batch_size + 1}: {len(batch)} files")
        
        # Process batch with error handling
        batch_results = await process_batch(processor, batch)
        
        # Update progress and save
        for file_path, success in batch_results:
            processed_files[str(file_path)] = success
            save_progress(progress_file, processed_files)
            
        # Brief pause between batches
        await asyncio.sleep(1)
    
    # Final validation
    await validate_seeded_documents()
    print("✅ Real document seeding completed!")

async def process_batch(processor, file_batch):
    """Process batch of files with proper error handling."""
    results = []
    for file_path in file_batch:
        try:
            # Infer content type from filename/content
            content_type = infer_content_type(file_path)
            success = await processor.process_document(str(file_path), content_type)
            results.append((file_path, success))
            
            if success:
                print(f"✅ {file_path.name} -> {content_type}")
            else:
                print(f"❌ {file_path.name} -> FAILED")
                
        except Exception as e:
            print(f"❌ {file_path.name} -> ERROR: {e}")
            results.append((file_path, False))
            
    return results

def infer_content_type(file_path: Path) -> Optional[str]:
    """Smart content type inference based on filename patterns."""
    filename_lower = file_path.name.lower()
    
    # FORM indicators (highest priority for exact matches)
    if any(term in filename_lower for term in [
        "consent", "form", "checklist", "template", "admission orders"
    ]):
        return "form"
    
    # PROTOCOL indicators  
    if any(term in filename_lower for term in [
        "protocol", "pathway", "guideline", "stemi", "sepsis", "stroke"
    ]):
        return "protocol"
        
    # CONTACT indicators
    if any(term in filename_lower for term in [
        "on-call", "directory", "contact", "coverage", "who"
    ]):
        return "contact"
        
    # Additional logic for CRITERIA, DOSAGE, SUMMARY...
    return None  # Let content-based classification handle it
```

### Integration Points
```yaml
DATABASE:
  - migration: "Add enhanced categorization fields to document_registry"
  - indexes: "CREATE INDEX idx_query_type ON document_registry(query_type)"
  
CONFIG:
  - No changes needed - uses existing settings
  
DEPENDENCIES:
  - system: "sudo apt-get install poppler-utils tesseract-ocr libmagic1"  
  - python: "Already in requirements.v8.txt"
```

## Validation Loop

### Level 1: System Dependencies & Syntax
```bash
# FIRST: Install system dependencies
sudo apt-get update && sudo apt-get install -y poppler-utils tesseract-ocr libmagic1

# Verify poppler installation
pdftoppm -h  # Should show help, not "command not found"
tesseract --version  # Should show version info

# Apply registry migration  
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/edbotv8 PYTHONPATH=/mnt/d/Dev/EDbotv8 alembic upgrade head

# Syntax checking
ruff check scripts/seed_real_documents.py --fix
mypy scripts/seed_real_documents.py
```

### Level 2: Unstructured Pipeline Testing  
```bash
# Test single document processing (should not fail with poppler error)
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/edbotv8 PYTHONPATH=/mnt/d/Dev/EDbotv8 python3 -c "
import asyncio
from src.ingestion.tasks import process_document
result = asyncio.run(process_document('/mnt/d/Dev/EDbotv8/docs/STEMI Activation.pdf', 'protocol'))
print(f'Single document test: {result}')
"

# Expected: True (success), not poppler error
```

### Level 3: Full Seeding Pipeline
```bash  
# Run enhanced seeding script
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/edbotv8 PYTHONPATH=/mnt/d/Dev/EDbotv8 python3 scripts/seed_real_documents.py

# Expected output:
# Found 338 total documents  
# Processing 338 remaining documents
# ✅ STEMI Activation.pdf -> protocol
# ✅ ED Sepsis Pathway.pdf -> protocol
# ✅ blood_transfusion_consent.pdf -> form
# ... (lots of success messages)
# ✅ Real document seeding completed!
```

### Level 4: Document Categorization Validation
```bash
# Verify documents are properly categorized across all 6 types
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/edbotv8 PYTHONPATH=/mnt/d/Dev/EDbotv8 python3 -c "
from src.models.database import get_db_session
from src.models.entities import DocumentRegistry
from sqlalchemy import func

with get_db_session() as session:
    # Count documents by query type
    counts = session.query(
        DocumentRegistry.query_type,
        func.count(DocumentRegistry.id)
    ).group_by(DocumentRegistry.query_type).all()
    
    print('Document distribution by query type:')
    for query_type, count in counts:
        print(f'  {query_type}: {count} documents')
    
    # Verify all 6 types are represented
    query_types = [qt for qt, _ in counts]
    expected = ['contact', 'form', 'protocol', 'criteria', 'dosage', 'summary']
    missing = [qt for qt in expected if qt not in query_types]
    
    if missing:
        print(f'❌ Missing query types: {missing}')
    else:
        print('✅ All 6 query types have documents')
"

# Expected: All 6 query types represented with reasonable distribution
```

### Level 5: End-to-End Query Processing
```bash
# Test that seeded documents work with query processor
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/edbotv8 PYTHONPATH=/mnt/d/Dev/EDbotv8 python3 -c "
import json
import requests

# Test all 6 query types with real medical questions
test_queries = [
    ('PROTOCOL', 'what is the STEMI protocol'),
    ('FORM', 'show me the blood transfusion consent form'), 
    ('DOSAGE', 'what is the epinephrine dosage for cardiac arrest'),
    ('CRITERIA', 'what are the Ottawa ankle rules'),
    ('CONTACT', 'who is on call for cardiology'),
    ('SUMMARY', 'summarize the sepsis management approach')
]

api_url = 'http://localhost:8002/api/v1/query'
headers = {'Content-Type': 'application/json'}

success_count = 0
for expected_type, query in test_queries:
    try:
        response = requests.post(api_url, headers=headers, json={'query': query}, timeout=15)
        data = response.json()
        
        has_content = len(data.get('response', '')) > 50  # Substantial response
        actual_type = data.get('query_type', '').upper()
        
        if has_content and actual_type == expected_type:
            print(f'✅ {expected_type}: {query[:40]}... -> SUCCESS')
            success_count += 1
        else:
            print(f'❌ {expected_type}: {query[:40]}... -> {actual_type} | Content: {has_content}')
            
    except Exception as e:
        print(f'❌ {expected_type}: ERROR - {e}')

print(f'\nEnd-to-end success rate: {success_count}/{len(test_queries)} ({100*success_count/len(test_queries):.0f}%)')
"

# Expected: 6/6 (100%) success rate with substantial medical responses
```

## Final Validation Checklist
- [ ] System dependencies installed: `pdftoppm -h` works
- [ ] Database migration applied successfully
- [ ] All 338 documents processed without poppler errors  
- [ ] Document registry populated with 6 query type categories
- [ ] Each query type has representative documents (>5 each)
- [ ] End-to-end query processing: 6/6 query types return medical content
- [ ] Manual spot check: STEMI protocol, blood transfusion form, sepsis pathway accessible
- [ ] Processing time reasonable: <30 minutes total
- [ ] Error handling graceful: failed documents don't block others
- [ ] Progress tracking: resumable if interrupted

---

## Anti-Patterns to Avoid
- ❌ Don't skip system dependency installation - runtime failures are cryptic
- ❌ Don't process all 338 files synchronously - will overwhelm system  
- ❌ Don't ignore classification confidence - low scores indicate poor categorization
- ❌ Don't hardcode file paths - use relative paths from project root
- ❌ Don't assume perfect success rate - some PDFs may be corrupted/unsupported
- ❌ Don't skip progress tracking - 20-minute process needs resumability
- ❌ Don't overwrite existing good data - check if documents already processed

**Confidence Score: 9/10** - This PRP provides comprehensive context, identifies the exact technical issue (missing poppler), provides complete implementation strategy with working code patterns, and includes thorough validation loops. The only unknown is document content quality, but the framework ensures systematic verification.