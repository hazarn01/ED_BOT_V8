name: "Fix Query Processing Pipeline and System Health Issues"
description: |

## Goal
Fix critical issues preventing ED Bot v8 from properly processing medical queries and reporting healthy system status. The system is currently returning fallback responses instead of processing queries through the classification → routing → LLM pipeline.

## Why
- **User Impact**: Users receive "system being set up" messages instead of actual medical information
- **System Reliability**: Health checks report unhealthy (0.222/1.0) preventing production deployment
- **Test Coverage**: 11 failing unit tests prevent confidence in system behavior
- **Integration Failure**: Query processing pipeline disconnected from API endpoints

## What
Restore full query processing functionality with proper:
1. Query classification returning structured results instead of tuples
2. API endpoints using real implementation instead of stub responses  
3. Database connections working correctly for health monitoring
4. Unit tests passing with consistent API contracts
5. LLM client initialization for classification and response generation

### Success Criteria
- [ ] All 6 query types (CONTACT, FORM, PROTOCOL, CRITERIA, DOSAGE, SUMMARY) return real responses
- [ ] Health check reports healthy status (>0.8 score)
- [ ] All unit tests pass without mocking errors
- [ ] API processes queries through full pipeline: classify → route → generate → respond
- [ ] Manual testing shows correct responses for sample queries from CLAUDE.md

## All Needed Context

### Documentation & References
```yaml
- url: https://fastapi.tiangolo.com/tutorial/dependencies/
  why: Dependency injection patterns for query processor initialization
  critical: Async dependencies and caching patterns for medical queries

- url: https://pytest-with-eric.com/pytest-advanced/pytest-asyncio/
  why: Async testing patterns for query classification  
  critical: AsyncMock usage and fixture setup for LLM client testing

- file: src/api/endpoints.py
  why: Real query processing implementation that should be used
  pattern: Uses QueryProcessor dependency injection correctly

- file: src/api/endpoints/query.py  
  why: Stub implementation currently being used (WRONG)
  critical: This is hardcoded to return "system being set up" message

- file: src/pipeline/classifier.py
  why: QueryClassifier returns tuple but tests expect ClassificationResult
  critical: Return type mismatch causing all classification tests to fail

- file: src/pipeline/query_processor.py  
  why: Main orchestrator that ties everything together
  pattern: Shows expected flow: classify → route → validate → respond

- file: src/observability/health.py
  why: Health monitoring implementation
  critical: Database connection using wrong hostname causing failures

- file: tests/unit/test_classifier.py
  why: Expected API patterns for testing query classification
  critical: Tests expect .query_type and .confidence attributes
```

### Current Codebase Tree (Query Processing Related)
```bash
src/
├── api/
│   ├── endpoints.py                 # ✅ Real query implementation (SHOULD USE)
│   ├── endpoints/
│   │   ├── __init__.py             # ❌ Routes to stub implementation
│   │   └── query.py                # ❌ Stub with hardcoded fallback
│   ├── dependencies.py             # ✅ Query processor DI setup  
│   └── app.py                      # Routes API calls
├── pipeline/
│   ├── classifier.py               # ❌ Returns tuple instead of object
│   ├── query_processor.py          # ✅ Main orchestrator
│   └── router.py                   # Query routing logic
├── models/
│   ├── query_types.py             # QueryType enum
│   └── schemas.py                 # ✅ QueryResponse model exists
├── observability/
│   └── health.py                  # ❌ Database hostname issues
└── ai/
    ├── gpt_oss_client.py          # Primary LLM client
    └── ollama_client.py           # Fallback LLM client
```

### Desired Codebase Tree (Files to Add/Modify)
```bash
src/
├── models/
│   └── classification.py          # ADD: ClassificationResult model
├── api/endpoints/
│   └── query.py                   # MODIFY: Use real implementation
├── pipeline/
│   └── classifier.py              # MODIFY: Return ClassificationResult
├── observability/
│   └── health.py                  # MODIFY: Fix database connection
└── tests/unit/
    └── test_classifier.py         # MODIFY: Fix async mocking
```

### Known Gotchas & Library Quirks
```python
# CRITICAL: QueryClassifier.classify_query() is async but returns tuple
# Tests expect: result.query_type and result.confidence  
# Current: query_type, confidence = await classifier.classify_query(query)

# CRITICAL: FastAPI dependency injection with async functions
# Pattern: All dependencies must be properly typed and cached
# Gotcha: Redis client connection uses 'redis' hostname in container, 'localhost' outside

# CRITICAL: pytest-asyncio requires proper async test setup
# Pattern: @pytest.mark.asyncio with AsyncMock for LLM clients
# Gotcha: Mock object needs proper spec= parameter for method introspection

# CRITICAL: Database health checks use different hostnames  
# Container context: 'db' hostname
# Host context: 'localhost' hostname
# Pattern: Use environment-aware connection strings

# CRITICAL: LLM client initialization in QueryClassifier
# Current: No clients passed to constructor (primary_client=None)
# Required: Must inject working GPTOSSClient or OllamaClient
```

## Implementation Blueprint

### Data Models and Structure
```python
# ADD: src/models/classification.py - Missing ClassificationResult model
from pydantic import BaseModel, Field
from .query_types import QueryType

class ClassificationResult(BaseModel):
    """Result of query classification with confidence score."""
    query_type: QueryType = Field(..., description="Classified query type")
    confidence: float = Field(..., ge=0, le=1, description="Classification confidence")
    method: str = Field(..., description="Classification method used")
    keywords: List[str] = Field(default_factory=list, description="Key terms found")
    
    @classmethod
    def from_tuple(cls, query_type: QueryType, confidence: float, method: str = "hybrid") -> "ClassificationResult":
        """Create from legacy tuple return."""
        return cls(query_type=query_type, confidence=confidence, method=method)
```

### List of Tasks (In Order)

```yaml
Task 1 - Create ClassificationResult Model:
  CREATE src/models/classification.py:
    - DEFINE ClassificationResult with query_type, confidence, method fields
    - ADD from_tuple classmethod for backward compatibility
    - USE pydantic BaseModel pattern like existing schemas
    
Task 2 - Fix QueryClassifier Return Type:
  MODIFY src/pipeline/classifier.py:
    - FIND: "async def classify_query(self, query: str) -> Tuple[QueryType, float]:"
    - CHANGE to: "-> ClassificationResult"
    - FIND all return statements returning tuples
    - CHANGE to: "return ClassificationResult(query_type=X, confidence=Y, method=Z)"
    - PRESERVE all existing regex patterns and logic
    
Task 3 - Fix API Endpoint Routing:
  MODIFY src/api/endpoints/__init__.py:
    - FIND: "from .query import router as query_router" 
    - CHANGE to: "from ..endpoints import router as query_router"
    - This routes to real implementation instead of stub
    
  ALTERNATIVELY - Replace Stub Implementation:
  MODIFY src/api/endpoints/query.py:
    - FIND: hardcoded "system being set up" response
    - REPLACE entire function with real query processing logic
    - MIRROR pattern from src/api/endpoints.py:process_query()
    - USE QueryProcessor dependency injection
    
Task 4 - Fix Database Health Check Hostname:
  MODIFY src/observability/health.py:
    - FIND database connection logic using hardcoded hostnames
    - ADD environment-aware hostname resolution
    - PATTERN: Use settings.DB_HOST with fallback to 'localhost'
    - ENSURE async database connections work correctly
    
Task 5 - Fix LLM Client Initialization:
  MODIFY src/pipeline/classifier.py constructor:
    - FIND: "__init__" method with optional clients
    - ADD fallback client initialization if none provided
    - PATTERN: Mirror src/api/dependencies.py:_get_llm_client()
    - ENSURE at least one client (Ollama) is available
    
Task 6 - Fix Unit Test Mocking:
  MODIFY tests/unit/test_classifier.py:
    - FIND: mock_llm_client.generate_response.return_value
    - CHANGE to: mock_llm_client.generate.return_value  
    - ADD AsyncMock import and usage
    - PATTERN: Mock returns await classifier.classify_query() -> ClassificationResult
    - FIX all test expectations to use result.query_type, result.confidence
```

### Per Task Pseudocode

```python
# Task 2 - QueryClassifier Fix
async def classify_query(self, query: str) -> ClassificationResult:
    """Classify query using rule-based + LLM approach."""
    # PRESERVE all existing logic for rule-based classification
    rule_result = self._classify_with_rules(query)  # returns (QueryType, float)
    
    if rule_result[1] > 0.9:  # High confidence
        return ClassificationResult(
            query_type=rule_result[0], 
            confidence=rule_result[1],
            method="rules"
        )
    
    # PRESERVE LLM classification logic
    llm_result = await self._classify_with_llm(query)
    final_result = self._combine_classifications(rule_result, llm_result)
    
    return ClassificationResult(
        query_type=final_result[0],
        confidence=final_result[1], 
        method="hybrid"
    )

# Task 4 - Health Check Database Fix
async def check_database_health(self) -> HealthCheck:
    # PATTERN: Environment-aware hostname resolution
    db_host = self.settings.DB_HOST or 'localhost'
    connection_string = f"postgresql+asyncpg://postgres:postgres@{db_host}:5432/edbotv8"
    
    try:
        # Use async database connection properly
        async with get_database() as db:
            result = await db.execute(text("SELECT 1"))
            # SUCCESS: Return HEALTHY status
    except Exception as e:
        # FAILURE: Return UNHEALTHY with error details

# Task 6 - Test Fix Pattern
@pytest.mark.asyncio
async def test_classify_contact_query(self, classifier, mock_llm_client):
    # CRITICAL: Use AsyncMock for async LLM client
    mock_llm_client.generate = AsyncMock()
    mock_llm_client.generate.return_value = Mock(content="CONTACT")
    
    # Call async classifier
    result = await classifier.classify_query("who is on call")
    
    # Test ClassificationResult object
    assert result.query_type == QueryType.CONTACT_LOOKUP
    assert result.confidence > 0.8
```

### Integration Points
```yaml
DATABASE:
  - ensure: Async database connections use correct hostnames
  - pattern: "DB_HOST environment variable with localhost fallback"
  
CONFIG:
  - verify: src/api/dependencies.py LLM client factory works
  - ensure: QueryClassifier gets initialized with working clients
  
ROUTES:
  - fix: src/api/endpoints/__init__.py uses real query implementation
  - verify: /api/v1/query endpoint processes actual queries
  
TESTING:
  - update: All classifier tests use AsyncMock patterns
  - ensure: Classification results have proper object interface
```

## Validation Loop

### Level 1: Syntax & Style
```bash
# Run FIRST - fix any errors before proceeding
ruff check src/ --fix         # Auto-fix formatting 
mypy src/                     # Type checking - expect ClassificationResult issues initially

# Expected: Clean after Task 1-2 completion
```

### Level 2: Unit Tests
```bash
# Test query classification specifically
PYTHONPATH=/mnt/d/Dev/EDbotv8 python3 -m pytest tests/unit/test_classifier.py -v --asyncio-mode=auto

# Expected: All 11 tests pass after Task 6
# If failing: Check mock setup and AsyncMock usage
```

### Level 3: Integration Tests  
```bash
# Start services (already running)
# Test query processing via API

# Test all 6 query types return real responses:
curl -s -X POST http://localhost:8002/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "what is the STEMI protocol"}' | jq '.query_type'
# Expected: "protocol" not "UNKNOWN"

curl -s -X POST http://localhost:8002/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "show me blood transfusion form"}' | jq '.query_type'  
# Expected: "form" not "UNKNOWN"

curl -s -X POST http://localhost:8002/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "who is on call for cardiology"}' | jq '.query_type'
# Expected: "contact" not "UNKNOWN"
```

### Level 4: Health Check Validation
```bash
# Check system health
curl -s http://localhost:8002/health | jq '.status'
# Expected: "healthy" not "unhealthy"

# Check detailed health if available
curl -s http://localhost:8002/api/v1/health/detailed | jq '.health_score'
# Expected: > 0.8 not 0.222
```

## Final Validation Checklist
- [ ] All unit tests pass: `pytest tests/unit/test_classifier.py -v --asyncio-mode=auto`
- [ ] Query classification works: Test queries return proper types not "UNKNOWN"
- [ ] Health checks pass: System reports healthy status
- [ ] Manual API tests succeed: All 6 query types process correctly
- [ ] No type errors: `mypy src/` passes cleanly
- [ ] Integration test: Sample medical queries return real content not fallback messages

## Quality Score: 8/10
This PRP provides comprehensive context and step-by-step implementation guidance. The main complexity is the async testing patterns and dependency injection chains, but all necessary patterns and gotchas are documented. Success depends on careful execution of the task sequence and thorough testing at each validation level.

## Anti-Patterns to Avoid
- ❌ Don't change QueryClassifier API without updating all calling code
- ❌ Don't skip async patterns - use AsyncMock not regular Mock
- ❌ Don't hardcode database hostnames - use environment-aware configuration  
- ❌ Don't break existing router structure - work within current FastAPI patterns
- ❌ Don't skip validation steps - each task must work before proceeding
- ❌ Don't mock successful tests - fix underlying code issues