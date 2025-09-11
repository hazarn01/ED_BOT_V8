# PRP-36: Fix Response Quality and Performance Issues

## Problem Statement

The current ED Bot v8 system has several critical issues that prevent it from being useful for medical professionals:

1. **Query Timeouts**: STEMI protocol queries are timing out, indicating performance issues in the retrieval pipeline
2. **Poor Source Attribution**: Sources are not being displayed properly, no hover functionality, counts don't match actual sources
3. **Generic Responses**: System is falling back to general knowledge instead of strictly using ingested medical documents
4. **Meta Query Handling**: System can't handle meta questions about its own capabilities appropriately
5. **Response Quality Degradation**: Despite having 338 documents ingested, responses are lower quality than expected

## Root Cause Analysis

### 1. Query Performance Issues
- Complex queries like "STEMI protocol" are timing out
- Likely caused by inefficient vector search or LLM processing
- Need to investigate retrieval pipeline bottlenecks

### 2. Source Attribution Breakdown
- Frontend not displaying actual source document names
- Hover functionality missing for source details
- Source counting inaccurate (showing 431 sources when impossible)

### 3. Response Quality Problems  
- LLM falling back to general medical knowledge instead of RAG context
- Responses not strictly constrained to ingested documents
- Low confidence scores on responses that should have high confidence

### 4. Meta Query Confusion
- System treating "what can we talk about" as medical query instead of capability question
- Need proper meta query detection and handling

## Solution Strategy

### Phase 1: Performance Optimization
- [ ] Profile and optimize vector search queries
- [ ] Implement query timeout handling with graceful degradation
- [ ] Add query complexity analysis and routing
- [ ] Optimize LLM inference pipeline

### Phase 2: Source Attribution Fix
- [ ] Fix frontend source display to show actual document names
- [ ] Implement proper source hover functionality with document details
- [ ] Correct source counting logic
- [ ] Add source confidence scoring

### Phase 3: Response Quality Enhancement
- [ ] Implement strict document-only response mode
- [ ] Add "no relevant information found" responses when appropriate
- [ ] Improve RAG context filtering and ranking
- [ ] Enhance prompt engineering for document-constrained responses

### Phase 4: Meta Query Handling
- [ ] Add meta query detection patterns
- [ ] Implement capability-specific response templates
- [ ] Route meta queries to appropriate handlers

## Implementation Plan

### Technical Changes Required

1. **Query Performance (`src/pipeline/query_processor.py`)**
   ```python
   # Add timeout handling and query optimization
   async def process_with_timeout(query: str, timeout: int = 30):
       # Implement graceful timeout with partial results
   ```

2. **Source Attribution (`src/api/endpoints/query.py`)**
   ```python
   # Fix source response format
   sources = [
       {
           "document_name": chunk.document.filename,
           "page": chunk.metadata.get("page"),
           "confidence": chunk.score,
           "preview": chunk.chunk_text[:100]
       }
   ]
   ```

3. **Response Quality (`src/pipeline/response_formatter.py`)**
   ```python
   # Strict document-only mode
   if not relevant_chunks:
       return "I don't have specific information about this in my medical documents."
   ```

4. **Frontend Source Display (`src/api/static/js/app.js`)**
   ```javascript
   // Add proper source hover functionality
   function displaySources(sources) {
       // Show actual document names with hover details
   }
   ```

### Testing Requirements

1. **Performance Tests**
   - All protocol queries must complete within 10 seconds
   - Test with complex queries like "STEMI protocol"
   - Load testing with concurrent queries

2. **Source Attribution Tests**
   - Verify actual document names are displayed
   - Test source hover functionality
   - Validate source count accuracy

3. **Response Quality Tests**
   - Verify responses use only ingested documents
   - Test "no information available" responses
   - Validate confidence scores match response quality

4. **Meta Query Tests**
   - Test capability questions are handled appropriately
   - Verify routing to meta handlers

## Success Criteria

1. ✅ All medical protocol queries complete within 10 seconds
2. ✅ Source attribution shows actual document names with hover details
3. ✅ Responses strictly use only ingested medical documents
4. ✅ Meta queries receive appropriate capability responses
5. ✅ Response quality matches or exceeds previous system performance
6. ✅ No fallback to general medical knowledge

## Priority: CRITICAL

This PRP addresses fundamental usability issues that prevent the system from being deployed in a medical environment. All issues must be resolved before the system can be considered production-ready.

## Estimated Effort: 2-3 days

- Performance optimization: 1 day
- Source attribution fixes: 0.5 days  
- Response quality enhancement: 1 day
- Meta query handling: 0.5 days
- Testing and validation: 0.5 days

## Dependencies

- Requires access to ingested document database
- Needs frontend JavaScript modifications
- May require LLM prompt template updates
- Could need vector search index optimization