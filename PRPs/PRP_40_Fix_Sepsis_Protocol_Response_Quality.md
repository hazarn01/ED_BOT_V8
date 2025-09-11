# PRP-40: Fix Sepsis Protocol Response Quality

## Problem Statement

The sepsis protocol queries ("what is the ED sepsis protocol", "sepsis criteria") are returning completely irrelevant content instead of proper sepsis protocol information. Unlike the excellent STEMI protocol response which returns structured, detailed medical content with timing and contacts, sepsis queries return:

- CHF pathway content: "Admission criteria include: symptoms failed to significantly improve..."
- ED referral phone numbers: "The ED Referral Line phone number is 212-241-3611"
- Low confidence scores (0.28) with multiple warnings
- Wrong source citations (RETU_CHF_Pathway_qa.json, ordering_consult_qa_388-400.json)

This is a critical medical safety issue that needs bulletproof fixing to match the quality of the STEMI response.

## Root Cause Analysis

### Issue Identification
1. **Query classification is working correctly** - sepsis queries are properly classified as `PROTOCOL_STEPS`
2. **RAG retrieval system is failing** - returning irrelevant content from incorrect documents
3. **No quality filtering** - system returns low-confidence, irrelevant responses instead of admitting lack of good content
4. **Missing or inaccessible sepsis content** - proper sepsis protocol documents may not be indexed correctly
5. **Inadequate fallback mechanism** - no curated sepsis responses like the excellent STEMI example

### Technical Flow Analysis
- `QueryProcessor.process_query()` → `QueryRouter._handle_protocol_query()` → `_retrieve_documents()` → `RAGRetriever.retrieve_for_query_type()`
- The RAG retrieval uses `_simple_medical_search()` with medical-aware ranking
- Quality validation in `ResponseValidator.validate_response()` is not blocking poor responses
- No sepsis-specific curated content in the curated response database

## Solution Design

### 1. Bulletproof Sepsis Protocol Response (Priority 1)
Create a high-quality, structured sepsis protocol response matching STEMI quality:

```markdown
🚨 **ED Sepsis Protocol**

📊 **Severity Criteria:**
• Severe Sepsis: Lactate > 2.0
• Septic Shock: Lactate > 4.0

⏱️ **Critical Timing:**
• Initial evaluation: 0-1 hour
• Reassessment: 3 hours
• RN + PA/MD huddle at arrival and 3 hours

💉 **Immediate Actions (0:00-1:00):**
• Draw lactate level
• Start IVF based on verbal orders
• Initiate antibiotics
• Use Adult Sepsis Order Set
• Document with Initial Sepsis Note template

🔄 **3-Hour Reassessment:**
• Repeat lactate measurement
• Post-fluid blood pressure
• Cardiovascular assessment
• Skin and capillary refill evaluation
• Use Sepsis Reassessment Note template

📋 **Documentation:**
• If likely NOT sepsis: choose SIRS/Other + alternate diagnosis
• Outstanding tasks → note in .edadmit for handoff
```

### 2. Enhanced Content Validation System
Implement strict quality thresholds to prevent irrelevant responses:

```python
class ProtocolResponseValidator:
    def validate_sepsis_response(self, query: str, results: List[Dict]) -> bool:
        """Validate sepsis protocol search results for relevance."""
        
        # Required sepsis keywords that should appear in relevant content
        sepsis_keywords = ['sepsis', 'lactate', 'sirs', 'shock', 'infection', 'antibiotics']
        
        for result in results:
            content = result.get('content', '').lower()
            
            # Count sepsis-related keywords
            keyword_matches = sum(1 for keyword in sepsis_keywords if keyword in content)
            
            # Reject if content has < 2 sepsis keywords
            if keyword_matches < 2:
                continue
                
            # Reject obvious non-sepsis content
            irrelevant_indicators = ['chf', 'heart failure', 'referral line', 'photography', 'context_enhancement']
            if any(indicator in content for indicator in irrelevant_indicators):
                continue
                
            # This result is relevant
            return True
            
        return False  # No relevant results found
```

### 3. Curated Sepsis Responses Integration
Add sepsis protocol to the curated response database:

```python
# In src/pipeline/curated_responses.py
sepsis_responses = [
    CuratedResponse(
        query_patterns=[
            "sepsis protocol", "ed sepsis", "sepsis pathway", 
            "sepsis criteria", "sepsis management", "severe sepsis"
        ],
        response="""🚨 **ED Sepsis Protocol**

📊 **Severity Criteria:**
• Severe Sepsis: Lactate > 2.0  
• Septic Shock: Lactate > 4.0

⏱️ **Critical Timing:**
• Initial evaluation: 0-1 hour
• Reassessment: 3 hours

💉 **Immediate Actions (0:00-1:00):**
• Draw lactate level
• Start IVF based on verbal orders  
• Initiate antibiotics per protocol
• Use Adult Sepsis Order Set
• Document with Initial Sepsis Note template

🔄 **3-Hour Reassessment:**  
• Repeat lactate measurement
• Post-fluid blood pressure assessment
• Cardiovascular assessment
• Skin and capillary refill evaluation
• Use Sepsis Reassessment Note template
• RN + PA/MD huddle

📋 **Workflow Notes:**
• If likely NOT sepsis: choose SIRS/Other + alternate diagnosis to dismiss alert
• Outstanding sepsis tasks → note in .edadmit for team handoff
• Continuous monitoring essential for optimal outcomes""",
        query_type="protocol",
        confidence=0.95,
        sources=["ED Sepsis Pathway Protocol", "Adult Sepsis Management Guidelines"]
    )
]
```

### 4. Enhanced RAG Retrieval for Medical Protocols
Improve the search relevance scoring specifically for protocol queries:

```python
# In src/pipeline/rag_retriever.py - enhance _medical_aware_search
def _enhance_protocol_search(self, query: str, results: List[Dict]) -> List[Dict]:
    """Enhanced filtering for protocol queries to prevent irrelevant content."""
    
    if 'sepsis' in query.lower():
        # Filter out clearly non-sepsis content
        filtered_results = []
        for result in results:
            content = result.get('content', '').lower()
            
            # Skip CHF, photography, referral, and other irrelevant content
            if any(term in content for term in ['chf pathway', 'heart failure', 'referral line', 'photography']):
                continue
                
            # Boost sepsis-specific content
            sepsis_terms = ['sepsis', 'lactate', 'sirs', 'infection', 'antibiotics', 'shock']
            term_matches = sum(1 for term in sepsis_terms if term in content)
            
            if term_matches >= 2:  # Require at least 2 sepsis terms
                result['similarity'] += term_matches * 10  # Boost relevance
                filtered_results.append(result)
                
        return filtered_results[:5]  # Return top 5 relevant results
        
    return results
```

### 5. Quality-Aware Response Generation
Update router to prevent low-quality responses from being returned:

```python
# In src/pipeline/router.py - enhance _handle_protocol_query
async def _handle_protocol_query(self, query: str, context: Optional[str], user_id: Optional[str]) -> Dict[str, Any]:
    """Handle PROTOCOL queries with quality validation."""
    
    # Check curated responses first (highest quality)
    curated_match = curated_db.find_curated_response(query, threshold=0.6)
    if curated_match:
        curated_response, match_score = curated_match
        return {
            "response": curated_response.response,
            "query_type": curated_response.query_type,
            "confidence": curated_response.confidence,
            "sources": curated_response.sources,
            "warnings": [f"✅ Curated medical protocol (match: {match_score:.1%})"]
        }
    
    # Enhanced retrieval with validation
    search_results, source_citations = await self._retrieve_documents(
        query=query, query_type=QueryType.PROTOCOL_STEPS, k=5
    )
    
    # Validate result quality
    validator = ProtocolResponseValidator()
    if not validator.validate_protocol_response(query, search_results):
        # Return quality-controlled "no information" response
        return {
            "response": "I don't have specific sepsis protocol information available in my current medical documents. For ED sepsis management, please consult your institution's clinical protocols, UpToDate, or contact the attending physician.",
            "sources": [],
            "confidence": 0.1,
            "warnings": ["No high-quality protocol content found for this query"]
        }
    
    # Continue with LLM generation only if we have quality content...
```

## Implementation Plan

### Phase 1: Immediate Fix (High Priority)
1. **Add curated sepsis response** to `curated_responses.py`
2. **Implement quality validation** in `ProtocolResponseValidator`  
3. **Update router** to use validation and prevent low-quality responses
4. **Test sepsis queries** to ensure high-quality responses

### Phase 2: Enhanced Retrieval (Medium Priority)
1. **Improve RAG relevance scoring** for medical protocols
2. **Add sepsis-specific content filtering**
3. **Verify sepsis content** is properly indexed in database
4. **Add more protocol patterns** to curated responses

### Phase 3: System-Wide Improvements (Lower Priority)
1. **Implement quality validation** for all query types
2. **Add more curated medical responses**
3. **Enhance medical terminology recognition**
4. **Add response quality metrics**

## Quality Assurance

### Test Cases
```bash
# Test queries that must return high-quality responses
curl -X POST "http://localhost:8001/api/v1/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "what is the ED sepsis protocol"}'

curl -X POST "http://localhost:8001/api/v1/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "sepsis criteria"}'

# Expected response structure:
# - Confidence > 0.9
# - Structured format with emojis
# - Specific timing, medications, criteria
# - No warnings about low quality
# - Source citations to sepsis protocols
```

### Success Criteria
- ✅ Sepsis protocol queries return structured, detailed responses
- ✅ Confidence scores > 0.9 for sepsis queries
- ✅ No irrelevant content (CHF, referral numbers) in responses
- ✅ Response quality matches STEMI protocol standard
- ✅ Clear source citations to actual sepsis protocols
- ✅ Medical safety: no hallucinated or incorrect medical information

### Validation Commands
```bash
# Unit tests
pytest tests/unit/test_sepsis_protocol.py -v

# Integration tests  
pytest tests/integration/test_protocol_quality.py -v

# Manual validation
make test-protocols
```

## Risk Assessment

**Risk Level: Medium** 
- Medical safety impact from poor sepsis protocol information
- User trust degradation from irrelevant responses

**Mitigation:**
- Curated responses provide guaranteed quality
- Quality validation prevents bad responses
- Clear fallback messages when no quality content available

## Dependencies

### Files to Modify:
- `src/pipeline/curated_responses.py` - Add sepsis curated responses
- `src/pipeline/router.py` - Add quality validation to protocol handler  
- `src/pipeline/rag_retriever.py` - Enhance medical protocol search
- `tests/unit/test_sepsis_protocol.py` - Add comprehensive tests

### External Dependencies:
- None - uses existing LLM and database systems

## Confidence Score: 9/10

This PRP provides a bulletproof fix through multiple layers:
1. **Curated responses** guarantee quality for common sepsis queries
2. **Quality validation** prevents irrelevant content from being returned  
3. **Enhanced retrieval** improves search relevance for medical protocols
4. **Clear fallback** responses maintain user trust when content is unavailable

The solution follows the proven STEMI protocol pattern and addresses all identified root causes while maintaining medical safety standards.