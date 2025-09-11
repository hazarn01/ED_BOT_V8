# PRP-47: Enhanced Retrieval Accuracy for Complex Queries

## Problem Statement

Current retrieval system works well for exact protocol matches (STEMI, sepsis) but fails on:

1. **Partial/Ambiguous Queries**: "L&D clearance", "pacs", "retu" return generic responses
2. **Count Queries**: "how many retu protocols" doesn't understand quantitative intent  
3. **Open-ended Queries**: "what can we talk about" fails completely
4. **Acronym Expansion**: Medical abbreviations not properly expanded for search

## Root Cause Analysis

From testing the current `SimpleDirectRetriever`:

1. **Poor Query Preprocessing**: No expansion of medical terms or acronyms
2. **Weak Search Strategy**: Simple ILIKE patterns miss semantic relationships
3. **No Query Type Handling**: All queries use same generic search logic
4. **Missing Context**: No understanding of medical domain relationships

## Proposed Solution

### Phase 1: Enhanced Query Preprocessing

```python
# src/pipeline/enhanced_query_processor.py
class MedicalQueryPreprocessor:
    def __init__(self):
        self.medical_abbreviations = {
            'L&D': ['Labor and Delivery', 'Obstetrics'],
            'PACS': ['Picture Archiving Communication System', 'Medical Imaging'],
            'RETU': ['Return to Emergency Department', 'Readmission'],
            'ED': ['Emergency Department'],
            'ICU': ['Intensive Care Unit'],
            'OR': ['Operating Room']
        }
    
    def expand_query(self, query: str) -> List[str]:
        """Expand abbreviations and add medical context"""
        expansions = []
        query_upper = query.upper()
        
        for abbrev, full_forms in self.medical_abbreviations.items():
            if abbrev in query_upper:
                expansions.extend(full_forms)
        
        return [query] + expansions
```

### Phase 2: Smart Search Strategy

```python
# Enhanced search with medical awareness
def _enhanced_medical_search(self, query: str, k: int = 5) -> List[Any]:
    """Multi-tier search strategy"""
    
    # Tier 1: Exact filename match
    filename_results = self._search_by_filename(query)
    if filename_results:
        return filename_results[:k]
    
    # Tier 2: Content with medical boosting
    content_results = self._search_with_medical_boosting(query, k)
    if content_results:
        return content_results
    
    # Tier 3: Fuzzy/semantic search fallback
    return self._fuzzy_search_fallback(query, k)
```

### Phase 3: Query Type-Specific Handlers

```python
def _handle_count_query(self, query: str) -> Dict[str, Any]:
    """Handle 'how many' type queries"""
    search_term = self._extract_count_target(query)  # "retu protocols" -> "retu"
    
    # Count matching documents
    count_query = text("""
        SELECT COUNT(DISTINCT d.filename) as doc_count,
               string_agg(DISTINCT d.filename, '; ') as filenames
        FROM documents d
        JOIN document_chunks dc ON d.id = dc.document_id  
        WHERE d.filename ILIKE :term OR dc.chunk_text ILIKE :term
    """)
    
    result = self.db.execute(count_query, {"term": f"%{search_term}%"}).fetchone()
    count, filenames = result
    
    return {
        "response": f"Found {count} documents related to '{search_term}':\n{filenames}",
        "query_type": "summary",
        "confidence": 0.9 if count > 0 else 0.1
    }
```

### Phase 4: Medical Context Integration

```python
def _search_with_medical_boosting(self, query: str, k: int) -> List[Any]:
    """Search with medical relevance scoring"""
    
    expanded_terms = self.preprocessor.expand_query(query)
    search_conditions = []
    params = {}
    
    for i, term in enumerate(expanded_terms):
        search_conditions.extend([
            f"d.filename ILIKE :term_{i}_file",
            f"dc.chunk_text ILIKE :term_{i}_content"
        ])
        params[f"term_{i}_file"] = f"%{term}%"
        params[f"term_{i}_content"] = f"%{term}%"
    
    # Medical relevance scoring
    search_query = f"""
        SELECT dc.chunk_text, d.filename,
               -- Boost score calculation
               (CASE 
                 WHEN d.filename ILIKE ANY(ARRAY[{','.join([f":term_{i}_file" for i in range(len(expanded_terms))])}]) THEN 100
                 WHEN d.content_type IN ('protocol', 'guideline') THEN 80
                 WHEN LENGTH(dc.chunk_text) > 200 THEN 60
                 ELSE 40
               END) as relevance_score
        FROM document_chunks dc
        JOIN documents d ON dc.document_id = d.id
        WHERE ({' OR '.join(search_conditions)})
        ORDER BY relevance_score DESC, LENGTH(dc.chunk_text) DESC
        LIMIT :k
    """
    
    return self.db.execute(text(search_query), {**params, "k": k}).fetchall()
```

## Implementation Plan

### Step 1: Core Infrastructure (30 min)
- Create `MedicalQueryPreprocessor` class
- Add medical abbreviation dictionary  
- Implement query expansion logic

### Step 2: Enhanced Search Logic (45 min)
- Update `SimpleDirectRetriever._search_all_content()` 
- Add multi-tier search strategy
- Implement medical relevance boosting

### Step 3: Query Type Handlers (30 min)
- Add count query detection and handling
- Implement open-ended query responses
- Add "what can we talk about" capability handler

### Step 4: Testing & Validation (15 min)
- Test problematic queries from user feedback
- Verify accuracy improvements
- Ensure no regression on working queries

## Success Metrics

**Before (Current State):**
- "L&D clearance" → Generic response about Psych Clearance
- "pacs" → Generic PACS loading instructions  
- "how many retu protocols" → Unrelated transfer documentation
- "what can we talk about" → Complete failure

**After (Target State):**
- "L&D clearance" → Specific Labor & Delivery clearance protocols
- "pacs" → Comprehensive PACS system information and procedures
- "how many retu protocols" → "Found 3 RETU protocols: [list]"
- "what can we talk about" → Medical domain overview with available topics

## Risk Assessment

**LOW RISK**: Changes are additive to existing working functionality
- Enhanced search logic with fallbacks
- Existing exact matches (STEMI, sepsis) remain unchanged
- Can be implemented incrementally with rollback capability

## Timeline: 2 hours total
- Immediate improvement for user-reported issues
- Foundation for future semantic search enhancements
- No breaking changes to existing API