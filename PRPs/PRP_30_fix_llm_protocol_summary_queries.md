name: "Fix LLM Generation for PROTOCOL and SUMMARY Queries"
description: |

## Goal
Fix critical issues preventing PROTOCOL and SUMMARY queries from returning medical content. Currently these query types are classified correctly but fail during database retrieval and LLM generation, returning "I'm unable to process that request right now" instead of detailed medical protocols and summaries.

## Why
- **Critical Gap**: 2/6 query types (33%) are non-functional after infrastructure fixes
- **High-Value Content**: PROTOCOL and SUMMARY queries provide the most complex, detailed medical information
- **Gold Standard Available**: 100+ ground truth examples in `/ground_truth_qa/` for validation
- **Database Errors**: SQL syntax errors in embedding vector queries preventing retrieval
- **LLM Generation Failures**: Response generation returning generic fallback messages

## What
Fix all components blocking PROTOCOL and SUMMARY query processing:
1. Database vector embedding query syntax errors (psycopg2.errors.SyntaxError)
2. SQL transaction rollback issues preventing entity extraction
3. LLM response generation returning fallback messages instead of medical content
4. Integration with ground truth QA data for validation and testing

### Success Criteria
- [ ] PROTOCOL queries return detailed medical protocol steps with timing and contacts
- [ ] SUMMARY queries return comprehensive medical information summaries
- [ ] Database vector searches execute without SQL syntax errors
- [ ] LLM generation produces medical content instead of generic fallback messages
- [ ] Manual testing matches gold standard answers from ground_truth_qa/
- [ ] All 6 query types (100%) return substantive medical content

## All Needed Context

### Documentation & References
```yaml
- file: ground_truth_qa/protocols/STEMI_qa.json
  why: Gold standard STEMI protocol answers for validation
  critical: Shows expected protocol content structure and medical details
  
- file: ground_truth_qa/protocols/ED_sepsis_pathway_qa.json
  why: Complex multi-step protocol example with timing requirements
  critical: Demonstrates expected workflow and assessment details

- file: ground_truth_qa/guidelines/Hypoglycemia_EBP_Final_qa.json  
  why: Summary-style medical guideline responses
  critical: Shows expected summary format with symptoms, treatments, dosages

- file: src/pipeline/rag_retriever.py
  why: Vector embedding search implementation
  critical: Contains SQL syntax error in vector similarity search

- file: src/pipeline/router.py
  why: Query routing and response generation logic
  critical: Protocol query handling and LLM response generation
```

### Current Error Analysis
```bash
# Database Vector Search Error
ERROR: syntax error at or near ":"
LINE 14: 1 - (dc.embedding <=> :query_embedding::vector) as similarity
CAUSE: Incorrect parameter binding in psycopg2 query with vector operations
LOCATION: src/pipeline/rag_retriever.py:114

# SQL Transaction Rollback Error  
ERROR: current transaction is aborted, commands ignored until end of transaction block
CAUSE: Failed vector search causes transaction rollback, preventing subsequent queries
LOCATION: src/pipeline/router.py:413

# LLM Generation Fallback
RESPONSE: "I'm unable to process that request right now"
CAUSE: Database errors prevent content retrieval, triggering generic fallback response
LOCATION: src/pipeline/router.py LLM generation logic
```

### Ground Truth Analysis
```yaml
Expected PROTOCOL Response Structure:
  - Timing Requirements: "Door-to-balloon time: 90 minutes", "Rapid EKG: <10 minutes"
  - Contact Information: "STEMI pager: 917-827-9725", "Cath Lab: x40935"  
  - Step-by-Step Workflow: "EKG at triage → MD review → Cath lab activation"
  - Medications: "STEMI pack: ASA 324mg, Brillanta 180mg, Crestor 80mg, Heparin 4000 units"
  - Resource Requirements: "Upgrade to RESUS", "Cardiac Fellow transport"

Expected SUMMARY Response Structure:  
  - Clinical Criteria: "Hypoglycemia: <70 mg/dL", "Symptomatic: 70-100 mg/dL with symptoms"
  - Treatment Options: "Conscious: D50 50mL IV", "Unconscious: Glucagon 1mg IM"
  - Symptom Descriptions: "Shaking, sweating, confusion, seizures"
  - Dosage Specifications: "15-20g carbs, repeat q15min", "D10 200mL over 15 minutes"
```

### Database Schema Analysis
```sql
-- Current vector search query (BROKEN)
SELECT 1 - (dc.embedding <=> :query_embedding::vector) as similarity
-- Problem: Parameter binding with vector type casting fails in psycopg2

-- Expected working query pattern  
SELECT 1 - (dc.embedding <=> %(query_embedding)s) as similarity
-- Solution: Use %(param)s format for psycopg2 parameter binding
```

### LLM Generation Analysis
```python
# Current generation pattern (produces fallback responses)
response = await llm_client.generate(prompt=protocol_prompt)
# Problem: May be hitting token limits, context issues, or prompt problems

# Expected generation pattern (from working query types)
response = self._generate_llm_response(context=retrieved_docs, query=query)
# Solution: Ensure proper context passing and prompt engineering for complex queries
```

## Implementation Blueprint

### Vector Search SQL Fix Pattern
```python
# BROKEN (current implementation)
def _build_similarity_query_broken(self):
    return text("""
        SELECT 1 - (dc.embedding <=> :query_embedding::vector) as similarity
        FROM document_chunks dc 
        WHERE 1 - (dc.embedding <=> :query_embedding::vector) >= :threshold
    """)

# FIXED (corrected parameter binding)
def _build_similarity_query_fixed(self):
    return text("""
        SELECT 1 - (dc.embedding <=> %(query_embedding)s::vector) as similarity
        FROM document_chunks dc 
        WHERE 1 - (dc.embedding <=> %(query_embedding)s::vector) >= %(threshold)s
    """)
```

### List of Tasks (In Order)

```yaml
Task 1 - Fix Vector Embedding SQL Syntax:
  LOCATE broken vector similarity queries in src/pipeline/rag_retriever.py
  IDENTIFY parameter binding syntax errors with :param vs %(param)s
  REPLACE all :query_embedding with %(query_embedding)s format
  TEST vector search queries execute without SQL syntax errors

Task 2 - Fix SQL Transaction Management:
  ADD proper transaction rollback handling after failed vector searches
  IMPLEMENT transaction isolation for vector operations
  ENSURE subsequent queries can execute after vector search failures
  VERIFY entity extraction queries work after embedding operations

Task 3 - Analyze LLM Generation Failures:
  EXAMINE why router._generate_llm_response() returns fallback messages
  CHECK if retrieved documents are empty due to database errors
  VERIFY LLM prompts are appropriate for complex protocol/summary content
  TEST LLM generation with manually provided context documents

Task 4 - Enhance Protocol Response Generation:
  IMPLEMENT structured protocol response formatting
  INCLUDE timing requirements, contacts, medications, and workflow steps
  USE ground truth STEMI and sepsis examples as response templates
  ENSURE medical accuracy and completeness in protocol responses

Task 5 - Enhance Summary Response Generation:
  IMPLEMENT comprehensive summary response formatting  
  INCLUDE symptoms, treatments, criteria, and dosage information
  USE ground truth hypoglycemia and other guideline examples as templates
  ENSURE summary responses cover all key medical aspects

Task 6 - Integrate Ground Truth Validation:
  CREATE validation tests using ground_truth_qa/ examples
  IMPLEMENT automated comparison of actual vs expected responses
  MEASURE response quality and medical accuracy against gold standards
  ESTABLISH minimum quality thresholds for protocol/summary responses
```

### Database Transaction Recovery Pattern
```python
# PATTERN: Robust transaction handling for vector operations
async def safe_vector_search(self, query_embedding, content_type):
    """Execute vector search with proper transaction recovery."""
    try:
        # Attempt vector similarity search
        results = await self.db.execute(vector_search_query, params)
        await self.db.commit()
        return results
    except Exception as e:
        # Rollback failed transaction
        await self.db.rollback()
        logger.warning(f"Vector search failed, falling back to text search: {e}")
        
        # Continue with alternative search strategy
        return await self.fallback_text_search(query, content_type)

# Apply to all database operations in rag_retriever.py and router.py
```

### Medical Content Generation Pattern  
```python
# PATTERN: Structured medical response generation
def generate_protocol_response(self, retrieved_docs, query):
    """Generate structured protocol response with medical accuracy."""
    
    # Extract key protocol components
    timing_info = self._extract_timing_requirements(retrieved_docs)
    contact_info = self._extract_contact_information(retrieved_docs)  
    workflow_steps = self._extract_workflow_steps(retrieved_docs)
    medications = self._extract_medication_information(retrieved_docs)
    
    # Structure response with medical formatting
    response = self._format_protocol_response(
        timing=timing_info,
        contacts=contact_info,
        workflow=workflow_steps,
        medications=medications,
        query=query
    )
    
    return response

# Apply medical structuring to both protocol and summary generation
```

## Validation Loop

### Level 1: Database Query Validation
```bash
# Test vector embedding queries execute successfully
python3 -c "
from src.pipeline.rag_retriever import RAGRetriever
from src.models.database import get_db_session
retriever = RAGRetriever(get_db_session())
results = retriever.semantic_search('STEMI protocol', 'protocol')
print(f'Retrieved {len(results)} documents')
"

# Expected: No SQL syntax errors, returns document chunks
```

### Level 2: End-to-End Protocol Testing
```bash
# Test STEMI protocol returns detailed medical content
curl -X POST http://localhost:8002/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "what is the STEMI protocol"}'

# Expected: Door-to-balloon timing, STEMI pager, Cath lab hours, medication pack details
```

### Level 3: End-to-End Summary Testing  
```bash
# Test hypoglycemia summary returns comprehensive information
curl -X POST http://localhost:8002/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "summarize hypoglycemia treatment"}'

# Expected: Blood glucose thresholds, treatment options, symptom descriptions, dosages
```

### Level 4: Ground Truth Validation
```python
# Automated validation against gold standard answers
def validate_against_ground_truth():
    test_cases = [
        ("What is the door-to-balloon time goal for STEMI?", "90 minutes"),
        ("What lactate level indicates severe sepsis?", "Lactate > 2"),  
        ("What is the standard IV glucose treatment?", "50mL (25g) D50 IV")
    ]
    
    for query, expected in test_cases:
        response = query_api(query)
        accuracy = measure_medical_accuracy(response, expected)
        assert accuracy > 0.8, f"Response accuracy {accuracy} below threshold"

# Expected: >80% accuracy match with ground truth answers
```

## Final Validation Checklist
- [ ] Vector embedding SQL queries execute without syntax errors
- [ ] SQL transactions recover properly after vector search failures  
- [ ] PROTOCOL queries return timing, contacts, workflow, and medications
- [ ] SUMMARY queries return symptoms, treatments, criteria, and dosages
- [ ] Responses match medical accuracy of ground truth examples
- [ ] All 6 query types return substantive medical content (100% functional)
- [ ] No generic "unable to process" fallback responses for valid medical queries

## Quality Score: 9/10
This PRP addresses both the technical database issues and medical content generation problems with specific SQL fixes and ground truth validation. The complexity lies in vector database operations and medical response structuring, but clear patterns and validation examples are provided from the extensive ground truth dataset.

## Anti-Patterns to Avoid
- ❌ Don't ignore SQL syntax errors - fix parameter binding issues properly
- ❌ Don't accept generic fallback responses - generate real medical content  
- ❌ Don't skip transaction recovery - implement proper rollback handling
- ❌ Don't ignore ground truth data - use it for validation and accuracy measurement
- ❌ Don't oversimplify medical responses - include timing, contacts, dosages as appropriate
- ❌ Don't mix parameter binding formats - use consistent %(param)s throughout