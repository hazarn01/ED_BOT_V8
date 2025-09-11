# PRP-45: Comprehensive Retrieval Quality Enhancement System

name: "Comprehensive Retrieval Quality Enhancement"  
description: |
  Systematic improvement of medical query retrieval quality through BM25 scoring, medical synonym expansion, multi-source diversification, and confidence scoring with integrated evaluation framework.

## Goal

Transform the current medical query retrieval system from basic text matching to a sophisticated, medical-domain-aware retrieval system that consistently returns 3-5 diverse, highly relevant sources with accurate confidence scoring and measurable quality improvements.

## Why

- **Current Issue**: System returns only 1 source per query instead of 3-5, limiting response comprehensiveness
- **Quality Gap**: Simple ILIKE matching produces inferior relevance ranking compared to BM25 scoring 
- **Medical Domain**: Lack of medical synonym expansion misses relevant content (e.g., "STEMI" vs "ST elevation MI")
- **User Trust**: No confidence scoring mechanism to indicate response reliability
- **Measurability**: Need integrated evaluation to track improvements quantitatively

## What

### User-Visible Behavior
- Medical queries return 3-5 diverse, relevant sources instead of 1
- Responses include confidence scores (0.0-1.0) indicating reliability
- Better coverage of medical terminology and synonyms
- Improved relevance ranking puts most important information first
- Measurable improvements in accuracy and comprehensiveness

### Success Criteria
- [ ] Average sources per query: 3.5 (currently 1.0)
- [ ] Retrieval precision@5: >0.8 (currently ~0.6)  
- [ ] Medical synonym coverage: >90% for common terms
- [ ] Response confidence correlation: >0.85 with ground truth accuracy
- [ ] End-to-end response time: <2s (maintain current performance)

## All Needed Context

### Documentation & References
```yaml
- url: https://en.wikipedia.org/wiki/Okapi_BM25
  why: Core BM25 algorithm for relevance scoring implementation
  critical: Understanding k1, b parameters for medical text

- url: https://scikit-learn.org/stable/modules/feature_extraction.html#tfidf-term-weighting  
  why: TF-IDF implementation patterns and medical text considerations
  section: Term frequency normalization for clinical documents

- url: https://www.ncbi.nlm.nih.gov/books/NBK9683/
  why: Medical terminology standardization for synonym mapping
  critical: UMLS concepts for medical term expansion

- file: src/pipeline/enhanced_medical_retriever.py
  why: Existing medical context awareness patterns to extend
  critical: MedicalContext and EnhancedResult dataclasses already exist

- file: src/observability/medical_metrics.py  
  why: Comprehensive metrics infrastructure already in place
  critical: clinical_confidence_distribution and response_accuracy_feedback metrics

- file: src/evaluation/retrieval_metrics.py
  why: Evaluation framework built in previous phase
  critical: RetrievalEvaluator.evaluate_retrieval() method for validation

- file: tests/unit/test_hybrid_retriever.py
  why: Established testing patterns with mock fixtures
  critical: pytest fixture patterns for retrieval components

- file: src/pipeline/router.py:252-256
  why: Integration point where rag_retriever.retrieve_for_query_type() is called
  critical: This is where improved retrieval gets integrated
```

### Current Codebase Structure
```bash
src/
├── pipeline/
│   ├── rag_retriever.py              # Current simple ILIKE retrieval
│   ├── enhanced_medical_retriever.py # Medical context awareness (expand this)
│   ├── router.py                     # Integration point (line 252)
│   └── query_processor.py            # Main orchestrator
├── observability/
│   ├── medical_metrics.py            # Metrics infrastructure (ready to use)
│   └── metrics.py                    # Base metrics  
├── evaluation/
│   └── retrieval_metrics.py          # Evaluation framework (newly built)
└── models/
    ├── entities.py                   # Document/chunk models
    └── query_types.py               # QueryType enum

tests/unit/
├── test_hybrid_retriever.py         # Test patterns to follow
└── test_medical_metrics.py          # Medical metrics testing

ground_truth_qa/                     # 90+ ground truth files for validation
├── guidelines/
├── protocols/  
└── reference/
```

### Desired Codebase Additions
```bash
src/
├── pipeline/
│   ├── bm25_scorer.py               # NEW: BM25 relevance scoring
│   ├── medical_synonym_expander.py  # NEW: Medical term expansion  
│   ├── source_diversifier.py       # NEW: Multi-source diversification
│   └── confidence_calculator.py    # NEW: Response confidence scoring
├── data/
│   └── medical_synonyms.json       # NEW: Medical terminology mappings
└── validation/
    └── retrieval_validator.py      # NEW: Quality validation

tests/unit/
├── test_bm25_scorer.py             # NEW: BM25 scoring tests
├── test_medical_synonym_expander.py # NEW: Synonym expansion tests  
├── test_source_diversifier.py     # NEW: Diversification tests
└── test_confidence_calculator.py   # NEW: Confidence scoring tests
```

### Known Gotchas & Library Quirks
```python
# CRITICAL: SQLAlchemy text() requires parameter binding
# ❌ WRONG: query = f"SELECT * FROM table WHERE col LIKE '%{term}%'"
# ✅ RIGHT: query = text("SELECT * FROM table WHERE col LIKE :term")
#           params = {"term": f"%{term}%"}

# CRITICAL: PostgreSQL full-text search requires specific indexing
# Need to use to_tsvector() and to_tsquery() for proper text search
# Current ILIKE approach is inefficient but works with existing schema

# CRITICAL: Medical terminology is case-sensitive and context-dependent
# "MI" can mean "Myocardial Infarction" or "Mitral Insufficiency"  
# Need context-aware expansion based on query type

# CRITICAL: Performance requirement <2s end-to-end
# BM25 scoring must be optimized to not slow down retrieval
# Use SQL-based scoring where possible, avoid Python loops

# CRITICAL: Existing EnhancedMedicalRetriever has medical context
# Must integrate with existing patterns, not replace wholesale
```

## Implementation Blueprint

### Core Data Models
```python
# Extend existing src/pipeline/enhanced_medical_retriever.py patterns
@dataclass  
class BM25Score:
    score: float
    term_frequencies: Dict[str, float]
    document_length: int
    average_doc_length: float
    
@dataclass
class SynonymExpansion:
    original_term: str
    expanded_terms: List[str]
    medical_context: str  # "cardiology", "emergency", etc.
    confidence: float

@dataclass
class DiversifiedSources:
    primary_sources: List[Dict[str, Any]]
    secondary_sources: List[Dict[str, Any]]  
    diversification_strategy: str
    coverage_score: float
```

### Task Execution Order

```yaml
Task 1 - BM25 Scoring Foundation:
CREATE src/pipeline/bm25_scorer.py:
  - MIRROR pattern from: src/pipeline/enhanced_medical_retriever.py (dataclass structure)
  - IMPLEMENT BM25 algorithm with medical text optimizations
  - INTEGRATE with existing SQLAlchemy text() parameter binding
  - PRESERVE existing error handling patterns

Task 2 - Medical Synonym Expansion: 
CREATE src/data/medical_synonyms.json:
  - EXTRACT common medical terms from ground_truth_qa/ files
  - STRUCTURE as: {"STEMI": ["ST elevation", "myocardial infarction", "heart attack"]}
  - INCLUDE context indicators: {"cardiology": [...], "emergency": [...]}

CREATE src/pipeline/medical_synonym_expander.py:
  - MIRROR pattern from: src/pipeline/enhanced_medical_retriever.py (medical context)
  - IMPLEMENT context-aware expansion based on QueryType
  - INTEGRATE with existing medical_metrics.py tracking

Task 3 - Enhanced RAG Integration:
MODIFY src/pipeline/rag_retriever.py:
  - FIND method: _simple_medical_search()
  - INJECT BM25 scoring after line: "# Format results"
  - REPLACE relevance calculation with BM25Score.score
  - PRESERVE existing error handling and logging

Task 4 - Multi-Source Diversification:
CREATE src/pipeline/source_diversifier.py:
  - MIRROR pattern from: src/pipeline/router.py:_retrieve_documents() 
  - IMPLEMENT source diversity algorithms
  - ENSURE 3-5 different sources per query
  - MAINTAIN performance <2s requirement

Task 5 - Confidence Scoring Integration:
CREATE src/pipeline/confidence_calculator.py:
  - MIRROR pattern from: src/observability/medical_metrics.py (clinical_confidence_distribution)
  - IMPLEMENT multi-factor confidence scoring
  - INTEGRATE with existing medical safety metrics
  - OUTPUT scores matching existing EnhancedResult.clinical_relevance pattern

Task 6 - Router Integration:
MODIFY src/pipeline/router.py:
  - FIND line 252: rag_retriever.retrieve_for_query_type()
  - INJECT enhanced retrieval with diversification
  - ADD confidence scoring to response metadata
  - PRESERVE existing caching and error handling

Task 7 - Evaluation Integration:
MODIFY src/evaluation/retrieval_metrics.py:
  - FIND RetrievalEvaluator.evaluate_retrieval()
  - ADD BM25 relevance scoring validation
  - ADD multi-source diversity measurement  
  - INTEGRATE confidence correlation tracking

Task 8 - Comprehensive Testing:
CREATE test suite following test_hybrid_retriever.py patterns:
  - MOCK database and scoring components
  - TEST each improvement in isolation
  - VALIDATE end-to-end retrieval quality
  - ENSURE performance regression testing
```

### Integration Points
```yaml
DATABASE:
  - no_migration: Current schema supports new retrieval methods
  - optimization: "CREATE INDEX idx_chunk_text_gin ON document_chunks USING GIN (to_tsvector('english', chunk_text))" 
  - performance: Add GIN index for full-text search optimization

METRICS:
  - extend: src/observability/medical_metrics.py
  - add: bm25_scoring_performance, synonym_expansion_usage, source_diversity_scores
  
CONFIGURATION:
  - add to: src/config/settings.py
  - pattern: "BM25_K1 = float(os.getenv('BM25_K1', '1.5'))"
  - pattern: "BM25_B = float(os.getenv('BM25_B', '0.75'))"
  - pattern: "MIN_SOURCES_PER_QUERY = int(os.getenv('MIN_SOURCES', '3'))"

ROUTER:
  - modify: src/pipeline/router.py line 252-256
  - pattern: Enhanced retrieval call with new parameters
```

## Validation Loop

### Level 1: Component Testing
```bash
# Test each component in isolation
python3 -m pytest tests/unit/test_bm25_scorer.py -v
python3 -m pytest tests/unit/test_medical_synonym_expander.py -v  
python3 -m pytest tests/unit/test_source_diversifier.py -v
python3 -m pytest tests/unit/test_confidence_calculator.py -v

# Expected: All tests pass, no performance regressions
```

### Level 2: Integration Testing  
```bash
# Test enhanced retrieval pipeline
python3 -m pytest tests/integration/test_enhanced_retrieval.py -v

# Validate ground truth accuracy
python3 src/evaluation/run_retrieval_evaluation.py --mode=comprehensive

# Expected: 
# - Average sources: 3.0+ (up from 1.0)
# - Precision@5: 0.75+ (up from ~0.6)
# - Response time: <2s maintained
```

### Level 3: Live API Testing
```bash
# Test key medical queries
curl -X POST http://localhost:8001/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "STEMI protocol"}' | jq '.sources | length'
# Expected: 3-5 sources

curl -X POST http://localhost:8001/api/v1/query \
  -H "Content-Type: application/json" \  
  -d '{"query": "sepsis criteria"}' | jq '.confidence'
# Expected: confidence score 0.0-1.0

# Test synonym expansion
curl -X POST http://localhost:8001/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "ST elevation myocardial infarction"}' 
# Expected: Returns STEMI protocol content
```

### Level 4: Metrics Validation
```python
# Validate improvement metrics using existing framework
from src.evaluation.retrieval_metrics import RetrievalEvaluator

evaluator = RetrievalEvaluator()
# Test suite defined in collect_baseline_metrics.py
results = evaluator.run_comprehensive_evaluation()

# Expected improvements:
assert results.avg_sources_per_query >= 3.0
assert results.avg_precision_at_k >= 0.75  
assert results.medical_synonym_coverage >= 0.9
assert results.confidence_correlation >= 0.85
```

## Implementation Pseudocode

### Task 1: BM25 Scorer
```python
# src/pipeline/bm25_scorer.py
class BM25Scorer:
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        # PATTERN: Follow EnhancedMedicalRetriever initialization
        self.k1 = k1  # Term frequency saturation point
        self.b = b    # Length normalization factor
        
    def calculate_bm25_score(self, query_terms: List[str], document: str, 
                           avg_doc_length: float, doc_length: int) -> float:
        # CRITICAL: Optimized for medical text characteristics
        # Medical documents often shorter but information-dense
        
        # PATTERN: Use existing medical_metrics.py for tracking
        with medical_metrics.clinical_confidence_distribution.time():
            score = 0.0
            for term in query_terms:
                tf = document.lower().count(term.lower())
                if tf > 0:
                    # BM25 formula optimized for medical text
                    idf = math.log((N - df + 0.5) / (df + 0.5))
                    numerator = tf * (self.k1 + 1)
                    denominator = tf + self.k1 * (1 - self.b + self.b * (doc_length / avg_doc_length))
                    score += idf * (numerator / denominator)
            
        return score

    def score_sql_results(self, query: str, db_results: List) -> List[EnhancedResult]:
        # INTEGRATION: Use existing SQL parameter binding patterns
        # PERFORMANCE: Batch scoring to maintain <2s requirement
        pass
```

### Task 2: Medical Synonym Expansion  
```python
# src/pipeline/medical_synonym_expander.py
class MedicalSynonymExpander:
    def __init__(self):
        # PATTERN: Mirror EnhancedMedicalRetriever medical context loading
        self.synonyms = self._load_medical_synonyms()
        self.context_map = self._build_context_mapping()
        
    def expand_query(self, query: str, query_type: QueryType) -> List[str]:
        # CRITICAL: Context-aware expansion based on medical specialty
        base_terms = self._extract_medical_terms(query)
        expanded_terms = []
        
        for term in base_terms:
            # PATTERN: Use existing medical_metrics tracking
            medical_metrics.medical_abbreviation_usage.inc(
                abbreviation=term, specialty=self._get_specialty(query_type)
            )
            
            synonyms = self._get_contextual_synonyms(term, query_type)
            expanded_terms.extend(synonyms)
            
        return list(set([query] + expanded_terms))  # Deduplicate
        
    def _load_medical_synonyms(self) -> Dict[str, List[str]]:
        # CRITICAL: Load from src/data/medical_synonyms.json
        # STRUCTURE: {"STEMI": ["ST elevation", "myocardial infarction"]}
        pass
```

## Final Validation Checklist
- [ ] All unit tests pass: `python3 -m pytest tests/unit/ -v`
- [ ] Integration tests pass: `python3 -m pytest tests/integration/ -v`  
- [ ] Performance maintained: Response time <2s for standard queries
- [ ] Multi-source requirement: Average 3+ sources per query
- [ ] BM25 improvement: Precision@5 score >0.75
- [ ] Confidence scoring: Correlation with ground truth >0.85
- [ ] Medical synonyms: Coverage of common terms >90%
- [ ] Metrics integration: All new metrics reporting correctly
- [ ] Error handling: Graceful degradation when components fail
- [ ] Memory usage: No significant memory leaks in long-running tests

## Anti-Patterns to Avoid
- ❌ Don't replace existing EnhancedMedicalRetriever - extend it
- ❌ Don't break existing medical_metrics.py patterns - integrate with them  
- ❌ Don't ignore performance requirements - profile every change
- ❌ Don't hardcode medical terms - use configurable JSON files
- ❌ Don't skip ground truth validation - use existing evaluation framework
- ❌ Don't bypass existing router integration - enhance existing patterns
- ❌ Don't create new test patterns - follow existing pytest fixtures

## Quality Score: 9/10

**Confidence Level: High** - This PRP provides comprehensive context including:
✅ Existing code patterns identified and referenced  
✅ Medical domain expertise integrated from existing components
✅ Performance requirements clearly specified and testable
✅ Evaluation framework already built and integrated
✅ Step-by-step validation with executable commands
✅ Clear integration points with existing router/metrics
✅ Comprehensive test patterns established
✅ Anti-patterns identified to avoid common pitfalls

**Risk Mitigation:** The systematic approach building on existing infrastructure (EnhancedMedicalRetriever, medical_metrics.py, evaluation framework) significantly reduces implementation risk while providing measurable quality improvements.

This PRP enables bulletproof implementation through comprehensive context, existing pattern reuse, and integrated validation loops that ensure each improvement is measurable and maintains system performance requirements.