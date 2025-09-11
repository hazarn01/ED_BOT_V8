# Pull Request: Fix source attribution to display document names instead of generic citations

## Summary
- Fixed source attribution issue where responses only showed "Source:1" instead of actual document names
- Implemented proper RAG retrieval infrastructure to preserve document metadata throughout the pipeline
- Enhanced citation formatting to ensure document display names are shown in all responses

## Problem Statement
The ED Bot v8 system was displaying generic source citations like "Source:1" instead of meaningful document names. This made it difficult for medical staff to verify the source of information and reduced trust in the system's responses.

## Changes Made

### 1. RAG Retrieval Module (`src/pipeline/rag_retriever.py`)
- Created new RAG retriever class for semantic search with pgvector
- Implemented document metadata preservation in search results
- Added support for retrieving document display names from registry
- Integrated with existing document chunk infrastructure

### 2. Router Updates (`src/pipeline/router.py`)
- Integrated RAG retriever for all query types (protocol, criteria, dosage, summary)
- Added `_resolve_document_sources_with_display_names()` method for proper source resolution
- Modified all query handlers to use new source format
- Updated LLM prompt generation to include proper document citations
- Changed source format from strings to dictionaries with display_name and filename

### 3. Response Formatter Updates (`src/pipeline/response_formatter.py`)
- Enhanced `_extract_sources()` to handle both legacy (string) and new (dict) formats
- Modified context building to use document display names
- Updated all response types to preserve source attribution
- Ensured backward compatibility with existing code

### 4. Testing (`tests/unit/test_source_attribution.py`)
- Added comprehensive test suite with 6 test cases
- Tests verify display names are preserved through entire pipeline
- Tests ensure backward compatibility with legacy format
- Mock testing for all components

## Before/After Examples

### Before:
```
Query: "What is the ED STEMI protocol?"
Response: "The STEMI protocol requires door-to-balloon time under 90 minutes..."
Sources: ["Source:1"]
```

### After:
```
Query: "What is the ED STEMI protocol?"
Response: "The STEMI protocol requires door-to-balloon time under 90 minutes..."
Sources: [{"display_name": "STEMI Activation Guidelines", "filename": "STEMI.pdf"}]
```

### Contact Query Before:
```
Query: "Who is on call for cardiology?"
Response: "The on-call cardiology physician is Dr. Sarah Johnson..."
Sources: ["amion_schedule"]
```

### Contact Query After:
```
Query: "Who is on call for cardiology?"
Response: "The on-call cardiology physician is Dr. Sarah Johnson..."
Sources: [{"display_name": "Amion On-Call Schedule", "filename": "amion_schedule"}]
```

## Test Results
```bash
python3 -m pytest tests/unit/test_source_attribution.py -v

tests/unit/test_source_attribution.py::TestSourceAttribution::test_response_formatter_extracts_display_names PASSED
tests/unit/test_source_attribution.py::TestSourceAttribution::test_response_formatter_handles_legacy_format PASSED
tests/unit/test_source_attribution.py::TestSourceAttribution::test_router_preserves_display_names PASSED
tests/unit/test_source_attribution.py::TestSourceAttribution::test_rag_retriever_includes_display_names PASSED
tests/unit/test_source_attribution.py::TestSourceAttribution::test_llm_response_includes_proper_citations PASSED
tests/unit/test_source_attribution.py::TestSourceAttribution::test_source_resolution_with_display_names PASSED

======================== 6 passed in 1.24s =========================
```

## Impact
- **Improved Trust**: Medical staff can now verify information sources with meaningful document names
- **Better Compliance**: Meets medical documentation standards requiring clear source attribution
- **Enhanced Usability**: Users can quickly identify which protocol or guideline information comes from
- **Maintained Compatibility**: Existing code continues to work with backward compatibility support

## Technical Details

### Source Format Migration
The system now uses a structured format for sources:
```python
# Old format
sources = ["filename.pdf"]

# New format
sources = [
    {
        "display_name": "Human-Readable Document Name",
        "filename": "filename.pdf"
    }
]
```

### RAG Integration
- Utilizes pgvector for semantic search
- Preserves document metadata through retrieval pipeline
- Supports query-type-specific retrieval strategies

### LLM Citation Instructions
Enhanced prompts now include:
```
IMPORTANT: When citing sources in your response, use the exact document names provided.
Format citations as: [Source: Document Name]
Available sources to cite: STEMI Activation Guidelines, Cardiac Protocol Manual
```

## Files Changed
- `src/pipeline/rag_retriever.py` (New file - 262 lines)
- `src/pipeline/router.py` (Modified - 122 lines changed)
- `src/pipeline/response_formatter.py` (Modified - 88 lines changed)
- `tests/unit/test_source_attribution.py` (New file - 216 lines)

## Deployment Notes
- No database migrations required (uses existing schema)
- Backward compatible with existing API responses
- No configuration changes needed

## Review Checklist
- [x] Code follows project style guidelines
- [x] Tests added and passing
- [x] Backward compatibility maintained
- [x] Documentation updated in code comments
- [x] No PHI or sensitive data exposed
- [x] Medical safety validation preserved

## Next Steps
After merge:
1. Monitor logs for any source resolution errors
2. Verify document display names are showing correctly in production
3. Consider adding more comprehensive integration tests
4. Update user documentation with new citation format

---

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>