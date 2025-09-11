# PRP-36: Ground Truth QA Quality Alignment

**Status**: DRAFT  
**Priority**: CRITICAL  
**Complexity**: HIGH  
**Estimated Effort**: 8-12 hours  

## Problem Statement

The current EDBotv8 system produces extremely poor answer quality compared to ground truth QA benchmarks. Testing reveals:

### Critical Quality Gaps Identified

1. **Minimal Response Content**: Queries return skeleton responses like "**Clinical Criteria**\n\n" instead of detailed medical information
2. **Low Confidence Scores**: System confidence averaging 0.28 vs expected >0.8
3. **Missing Medical Facts**: Ground truth expects "blood glucose <70 mg/dL" but system returns empty content
4. **Source Citation Failures**: Hundreds of incorrect source citations, compliance warnings
5. **Knowledge Base Disconnection**: System unable to access properly seeded medical content

### Ground Truth vs Current System Comparison

**Ground Truth Expected** (Hypoglycemia Question):
```
"Hypoglycemia is defined as blood glucose <70 mg/dL. Symptomatic hypoglycemia includes patients with hypoglycemia symptoms even with blood glucose 70-100 mg/dL."
```

**Current System Response**:
```json
{
  "response": "**Clinical Criteria**\n\n",
  "confidence": 0.28,
  "warnings": ["Missing or incorrect source citations"]
}
```

## Root Cause Analysis

### 1. RAG Retrieval Failure
- Document chunks not properly indexed or retrieved
- Search terms not matching medical content
- Vector embeddings misaligned with query intent

### 2. LLM Response Generation Issues  
- Ollama model unable to synthesize retrieved context
- Temperature/generation parameters suboptimal
- Medical prompt engineering insufficient

### 3. Source Attribution System Broken
- Document registry entries malformed
- Citation mapping failing between chunks and sources
- PDF links not properly generated

### 4. Query Classification Mismatch
- Classified as "criteria" but retrieving wrong content type
- Query routing to inappropriate retrieval strategies
- Context filtering too aggressive

## Proposed Solution

### Phase 1: RAG System Overhaul (4 hours)

#### A. Fix Document Retrieval Pipeline
```python
# Enhanced medical-aware retrieval
class MedicalRAGRetriever:
    def retrieve_for_medical_query(self, query: str, query_type: str) -> List[Document]:
        # Multi-stage retrieval
        results = []
        
        # 1. Exact phrase matching
        exact_matches = self._exact_phrase_search(query)
        results.extend(exact_matches[:3])
        
        # 2. Medical term expansion  
        expanded_terms = self._expand_medical_terms(query)
        semantic_matches = self._semantic_search(expanded_terms)
        results.extend(semantic_matches[:5])
        
        # 3. Fallback text search
        if len(results) < 3:
            text_matches = self._fallback_text_search(query)
            results.extend(text_matches[:3])
            
        return self._deduplicate_and_rank(results)
```

#### B. Medical Term Processing
- Load medical abbreviation dictionary (414 terms)
- Expand queries with synonyms: "hypoglycemia" → ["low blood sugar", "glucose <70"]
- Context-aware search term weighting

#### C. Confidence Scoring Overhaul
```python
def calculate_medical_confidence(self, query: str, retrieved_docs: List[Document], response: str) -> float:
    confidence = 0.0
    
    # Keyword presence in response (40%)
    keyword_score = self._calculate_keyword_coverage(query, response)
    confidence += keyword_score * 0.4
    
    # Medical fact accuracy (30%)
    fact_score = self._validate_medical_facts(response)
    confidence += fact_score * 0.3
    
    # Source citation quality (20%)  
    citation_score = self._evaluate_citations(retrieved_docs, response)
    confidence += citation_score * 0.2
    
    # Response completeness (10%)
    completeness_score = len(response) / 500  # Target ~500 char responses
    confidence += min(completeness_score, 1.0) * 0.1
    
    return confidence
```

### Phase 2: LLM Response Enhancement (3 hours)

#### A. Medical-Specific Prompts
```python
MEDICAL_RESPONSE_PROMPT = """
You are a medical AI assistant for emergency department staff. Provide accurate, detailed responses based ONLY on the provided medical documents.

CRITICAL REQUIREMENTS:
1. Include specific numerical values (e.g., "glucose <70 mg/dL")
2. Provide complete treatment protocols with dosages and timing
3. Cite sources using exact document names
4. Use bullet points for step-by-step procedures
5. Include relevant phone numbers and contacts when available

Context: {retrieved_context}
Question: {query}

Response Format:
**Clinical Definition**: [specific medical criteria with numbers]
**Treatment Protocol**: 
- Step 1: [specific action with dosage/timing]
- Step 2: [specific action with dosage/timing]

**Sources**: {source_citations}
"""
```

#### B. Response Validation Pipeline
```python
class MedicalResponseValidator:
    def validate_medical_response(self, response: str, query_type: str) -> ValidationResult:
        issues = []
        
        # Check for specific medical facts
        if query_type == "criteria" and not re.search(r'\d+\s*(mg/dL|mmol/L)', response):
            issues.append("Missing quantitative criteria")
            
        # Verify dosage information
        if query_type == "dosage" and not re.search(r'\d+\s*(mg|mL|units)', response):
            issues.append("Missing dosage information")
            
        # Contact information validation
        if query_type == "contact" and not re.search(r'\(\d{3}\)\s*\d{3}-\d{4}', response):
            issues.append("Missing or malformed contact information")
            
        return ValidationResult(is_valid=len(issues) == 0, issues=issues)
```

### Phase 3: Source Attribution Fix (2 hours)

#### A. Document Registry Enhancement
```sql
-- Enhanced document registry with better metadata
ALTER TABLE document_registry ADD COLUMN ground_truth_mappings JSONB;
ALTER TABLE document_registry ADD COLUMN key_medical_facts TEXT[];
ALTER TABLE document_registry ADD COLUMN primary_use_cases TEXT[];

-- Example data
UPDATE document_registry 
SET ground_truth_mappings = '{"hypoglycemia_definition": "glucose <70 mg/dL"}',
    key_medical_facts = ARRAY['hypoglycemia definition', 'glucose thresholds', 'D50 dosing'],
    primary_use_cases = ARRAY['criteria check', 'dosage lookup']
WHERE filename LIKE '%Hypoglycemia%';
```

#### B. Citation Generation Fix
```python
def generate_source_citations(self, retrieved_docs: List[Document]) -> List[str]:
    citations = []
    for doc in retrieved_docs:
        # Use display name from registry, not filename
        display_name = doc.registry.display_name or doc.filename
        citations.append(display_name.replace('.pdf', '').replace('_', ' ').title())
    
    return list(set(citations))  # Remove duplicates
```

### Phase 4: Ground Truth Validation Framework (3 hours)

#### A. Automated Quality Assessment
```python
class GroundTruthValidator:
    def __init__(self, ground_truth_dir: str):
        self.ground_truth = self._load_all_qa_pairs(ground_truth_dir)
    
    def evaluate_system_quality(self) -> QualityReport:
        results = []
        
        for qa_pair in self.ground_truth:
            # Get system response
            response = self.query_system(qa_pair.question)
            
            # Calculate quality metrics
            keyword_match = self._keyword_similarity(qa_pair.answer, response.content)
            semantic_similarity = self._semantic_similarity(qa_pair.answer, response.content)
            factual_accuracy = self._validate_medical_facts(response.content)
            
            results.append(QualityMetric(
                question=qa_pair.question,
                expected=qa_pair.answer,
                actual=response.content,
                keyword_match=keyword_match,
                semantic_similarity=semantic_similarity,
                factual_accuracy=factual_accuracy,
                confidence=response.confidence
            ))
        
        return QualityReport(
            metrics=results,
            overall_score=np.mean([r.overall_score() for r in results]),
            passing_threshold=0.8
        )
```

#### B. Quality Benchmarks  
- **Keyword Coverage**: >80% of ground truth keywords present
- **Semantic Similarity**: >0.7 cosine similarity with expected answer
- **Factual Accuracy**: 100% for numerical medical facts
- **Confidence Threshold**: >0.8 for high-quality responses
- **Response Completeness**: 200-800 character responses for complex queries

## Implementation Plan

### Immediate Actions (Day 1)
1. **Fix RAG Retrieval**: Implement exact phrase matching for medical terms
2. **Medical Prompt Tuning**: Deploy medical-specific response templates
3. **Basic Validation**: Add numerical fact checking for dosages/thresholds

### Phase 1 Completion (Day 2-3)  
1. **Multi-stage Retrieval**: Exact → Semantic → Fallback search pipeline
2. **Confidence Recalibration**: New scoring system based on medical accuracy
3. **Source Citation Repair**: Fix document registry display names

### Phase 2 Validation (Day 4)
1. **Ground Truth Testing**: Run full qa_pairs against improved system  
2. **Quality Benchmarking**: Achieve >0.8 average confidence scores
3. **Edge Case Testing**: Verify complex medical scenarios

## Success Criteria

### Quality Metrics (Must Pass All)
- [ ] **Response Completeness**: Average response length >200 characters
- [ ] **Medical Accuracy**: 100% of numerical facts correct
- [ ] **Confidence Scores**: Average >0.8 across all query types
- [ ] **Ground Truth Alignment**: >80% semantic similarity with expected answers
- [ ] **Source Citations**: Clean, properly formatted document names

### Functional Requirements (Must Pass All)
- [ ] **Hypoglycemia Definition**: Must return "glucose <70 mg/dL"
- [ ] **STEMI Contacts**: Must return "(917) 827-9725" for after-hours
- [ ] **D50 Dosage**: Must return "50mL (25g) D50 IV over 2-5 minutes"
- [ ] **Sepsis Criteria**: Must return "Lactate >2" for severe sepsis
- [ ] **Response Time**: <10 seconds for all queries

## Validation Commands

```bash
# Test against ground truth after implementation
make test-ground-truth

# Run quality benchmarking
make validate-quality-metrics  

# Specific critical queries
curl -X POST http://localhost:8001/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What blood glucose level defines hypoglycemia?"}'

curl -X POST http://localhost:8001/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the after-hours contact for STEMI activation?"}'
```

## Risk Assessment

### High Risks
- **LLM Model Limitations**: Ollama might be insufficient for medical reasoning
- **Data Quality Issues**: Ground truth misalignment with actual document content
- **Performance Impact**: Multi-stage retrieval could slow response times

### Mitigation Strategies
- **LLM Backup**: Prepare GPT-OSS/vLLM fallback for better medical reasoning
- **Content Validation**: Cross-verify ground truth against actual PDF content  
- **Performance Monitoring**: Add response time tracking and optimization

## Dependencies

- ✅ Document seeding completed (338 documents)
- ✅ Database schema ready
- ✅ Ground truth QA files available
- ⚠️ LLM model performance (Ollama vs alternatives)
- ⚠️ Vector embedding quality

## Conclusion

This PRP addresses the critical gap between ground truth medical QA expectations and current system performance. The implementation focuses on fixing the core RAG retrieval pipeline, enhancing medical-specific response generation, and establishing automated quality validation.

**Expected Outcome**: Transform system from producing skeleton responses (0.28 confidence) to detailed medical answers (>0.8 confidence) that match ground truth benchmarks.

**Timeline**: 4 days full implementation, immediate improvement after Phase 1 fixes.