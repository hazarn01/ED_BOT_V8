# PRP-42: Fix GPT-OSS Timeout Issues Making App Unusable

## Goal
Fix critical GPT-OSS timeout and empty response issues that are making the EDBotv8 medical AI system completely unusable, ensuring reliable medical content generation with proper fallback mechanisms.

## Why
- **Critical System Failure**: GPT-OSS backend is timing out 100% of queries, making the Universal Quality System unusable
- **Poor User Experience**: Frontend shows constant "system load" errors instead of medical responses
- **Model Mismatch**: DialoGPT-medium is optimized for conversations, not medical content generation
- **Production Readiness**: Need reliable LLM backend for medical professionals to use the system

## What
Fix multiple interconnected issues in the GPT-OSS client implementation and provide model upgrade path:

### Success Criteria
- [ ] GPT-OSS queries complete successfully >95% of the time
- [ ] Query response time <10 seconds for medical content
- [ ] Empty response rate <5%
- [ ] Health checks pass consistently
- [ ] Proper error handling with meaningful error messages
- [ ] Model upgrade path to Mistral-7B documented and implemented

## All Needed Context

### Documentation & References
```yaml
- url: https://docs.vllm.ai/en/latest/getting_started/quickstart.html
  why: vLLM OpenAI-compatible API endpoints and usage patterns
  critical: Uses /v1/completions not /completions, /v1/models for health
  
- url: https://github.com/vllm-project/vllm/issues/1185
  why: Known vLLM empty response issues and solutions
  critical: Empty responses occur with concurrent requests and certain models
  
- url: https://docs.vllm.ai/en/latest/models/supported_models.html
  why: Better model alternatives for medical content (Mistral, Llama3)
  critical: DialoGPT-medium not recommended for instruction-following tasks
  
- url: https://docs.mistral.ai/getting-started/models/benchmark/
  why: Mistral-7B performance benchmarks for medical applications
  critical: Outperforms DialoGPT for medical content generation

- file: src/ai/gpt_oss_client.py
  why: Current broken implementation with wrong endpoints
  critical: Using /completions instead of /v1/completions, wrong health check
  
- file: src/ai/ollama_client.py  
  why: Working pattern for health checks and request formatting
  critical: Shows proper health check using /api/tags endpoint

- file: src/config/settings.py
  why: Current LLM timeout and model configuration
  critical: llm_timeout=30s too short, gpt_oss_model=DialoGPT-medium suboptimal

- file: docker-compose.v8.yml
  why: vLLM container configuration and model loading
  critical: Line 32 specifies microsoft/DialoGPT-medium model
```

### Current Codebase Structure
```bash
src/
├── ai/
│   ├── gpt_oss_client.py          # BROKEN - wrong endpoints, timeouts
│   ├── ollama_client.py           # WORKING - good pattern to follow
│   ├── llm_client.py              # Factory that chooses backend
│   └── medical_prompts.py         # Universal Quality System prompts
├── config/
│   └── settings.py                # LLM timeout and model config
├── pipeline/
│   ├── query_processor.py         # Uses LLM via dependency injection
│   └── universal_quality_orchestrator.py  # PRP-41 system using LLM
└── api/
    └── dependencies.py            # LLM client initialization
```

### Desired Codebase Structure After Fix
```bash
src/
├── ai/
│   ├── gpt_oss_client.py          # FIXED - correct vLLM endpoints
│   ├── vllm_model_manager.py      # NEW - model validation and warm-up
│   ├── enhanced_retry_logic.py    # NEW - intelligent retry for vLLM issues
│   └── medical_prompts.py         # ENHANCED - DialoGPT-optimized prompts
├── config/
│   └── settings.py                # UPDATED - longer timeouts, model options
└── tests/
    └── test_gpt_oss_integration.py # NEW - comprehensive LLM backend tests
```

### Known Gotchas & Critical Issues Discovered

```python
# CRITICAL: vLLM OpenAI API compatibility requires /v1/ prefix
# Current: POST http://localhost:8000/completions (WRONG - returns 404)
# Correct: POST http://localhost:8000/v1/completions

# CRITICAL: Health check endpoint mismatch  
# Current: GET http://localhost:8000/health (works but client reports 404)
# Better:  GET http://localhost:8000/v1/models (proper OpenAI compatibility)

# CRITICAL: DialoGPT-medium model limitations
# - Designed for chat/conversations, not instruction-following
# - Max context length only 1024 tokens  
# - Poor performance on medical content generation
# - Known to return empty responses with certain prompt formats

# CRITICAL: vLLM concurrent request bug
# - 20-50% empty responses with multiple concurrent requests
# - Affects batch inference and high-load scenarios
# - Requires retry logic and request throttling

# CRITICAL: Medical prompt format mismatch
# DialoGPT expects: "Human: question\nAssistant:"
# Current prompts: Long medical instruction prompts
```

## Implementation Blueprint

### Root Cause Analysis Summary
1. **API Endpoint Errors**: Client using wrong vLLM endpoint URLs
2. **Model Architecture Mismatch**: DialoGPT-medium designed for chat, not medical instructions  
3. **vLLM-Specific Issues**: Known empty response problems with concurrent requests
4. **Timeout Configuration**: 30s timeout too short for medical content generation
5. **Prompt Format Issues**: Medical prompts not formatted for DialoGPT's chat training

### Tasks in Implementation Order

```yaml
Task 1 - Fix vLLM API Endpoints:
  MODIFY src/ai/gpt_oss_client.py:
    - FIND: f"{self.base_url}/completions" 
    - REPLACE: f"{self.base_url}/v1/completions"
    - FIND: f"{self.base_url}/health"
    - REPLACE: f"{self.base_url}/v1/models"  
    - UPDATE: health_check() method to parse /v1/models response

Task 2 - Optimize Timeouts and Retry Logic:
  MODIFY src/config/settings.py:
    - CHANGE: llm_timeout from 30 to 60 seconds
    - ADD: llm_generation_timeout: int = 45 # Separate timeout for generation
    - ADD: llm_health_timeout: int = 10    # Separate timeout for health checks
  
  MODIFY src/ai/gpt_oss_client.py:
    - ENHANCE retry logic with exponential backoff
    - ADD specific handling for empty response errors
    - ADD request throttling to avoid vLLM concurrent request issues

Task 3 - Fix Medical Prompt Formatting:
  CREATE src/ai/dialogpt_prompt_adapter.py:
    - CONVERT medical instruction prompts to DialoGPT chat format
    - PATTERN: "Human: [medical question]\nAssistant:"
    - PRESERVE medical context but adapt to conversational style
  
  MODIFY src/ai/gpt_oss_client.py:
    - INTEGRATE prompt adapter for DialoGPT-medium
    - MAINTAIN compatibility with Universal Quality System prompts

Task 4 - Add Model Validation and Warm-up:
  CREATE src/ai/vllm_model_manager.py:
    - IMPLEMENT model availability checking
    - ADD warm-up requests on startup
    - INCLUDE model performance benchmarking
    - HANDLE model switching logic for different backends

Task 5 - Implement Better Error Handling:
  MODIFY src/ai/gpt_oss_client.py:  
    - ADD specific error types for different failure modes
    - IMPROVE logging with structured error information
    - IMPLEMENT graceful degradation for timeout scenarios
    - ADD health check recovery mechanisms

Task 6 - Add Model Upgrade Path:
  MODIFY docker-compose.v8.yml:
    - ADD environment variable for model selection
    - DOCUMENT Mistral-7B as preferred alternative
    - INCLUDE model switching without container rebuild
  
  CREATE docs/MODEL_UPGRADE_GUIDE.md:
    - DOCUMENT performance comparison DialoGPT vs Mistral-7B
    - INCLUDE step-by-step upgrade instructions
    - ADD rollback procedures

Task 7 - Comprehensive Testing:
  CREATE tests/integration/test_gpt_oss_backend.py:
    - TEST all fixed endpoints work correctly
    - VALIDATE timeout handling and retry logic
    - ENSURE empty response rate <5%
    - BENCHMARK response times <10s for medical queries
```

### Critical Implementation Details

```python
# Task 1: Fix API endpoints
async def health_check(self) -> bool:
    """Check if vLLM server is healthy using OpenAI-compatible endpoint."""
    try:
        client = await self._get_client()
        response = await client.get(f"{self.base_url}/v1/models")
        if response.status_code == 200:
            models = response.json()
            # Verify our model is available
            available = any(m["id"] == self.model for m in models.get("data", []))
            if available:
                logger.debug(f"LLM health check passed, model {self.model} available")
                return True
            else:
                logger.error(f"Model {self.model} not available in vLLM")
                return False
        return False
    except Exception as e:
        logger.error(f"LLM health check error: {e}")
        return False

# Task 2: Enhanced retry with vLLM-specific error handling  
async def _make_request(self, payload: Dict[str, Any]) -> str:
    """Make request with vLLM-optimized retry logic."""
    client = await self._get_client()
    
    for attempt in range(self.retry_attempts):
        try:
            # Add small delay between requests to avoid concurrent request issues
            if attempt > 0:
                await asyncio.sleep(0.1 * attempt)
                
            response = await client.post(
                f"{self.base_url}/v1/completions",  # FIXED: Add /v1 prefix
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=httpx.Timeout(self.llm_generation_timeout)  # Use generation-specific timeout
            )
            response.raise_for_status()
            
            result = response.json()
            
            if "choices" in result and len(result["choices"]) > 0:
                text = result["choices"][0].get("text", "").strip()
                if not text:  # Handle vLLM empty response bug
                    if attempt < self.retry_attempts - 1:
                        logger.warning(f"Empty response from vLLM, retrying... (attempt {attempt + 1})")
                        continue
                    else:
                        raise ValueError("vLLM returned empty response after all retries")
                return text
            else:
                raise ValueError("Invalid response format from vLLM")
                
        except (httpx.TimeoutException, ValueError) as e:
            if attempt == self.retry_attempts - 1:
                raise
            logger.warning(f"vLLM request failed (attempt {attempt + 1}): {e}")
            
        except httpx.HTTPStatusError as e:
            # Don't retry 4xx errors, only 5xx and network errors
            if 400 <= e.response.status_code < 500:
                raise
            if attempt == self.retry_attempts - 1:
                raise
                
        # Exponential backoff for retries
        await asyncio.sleep(self.retry_delay * (2 ** attempt))

# Task 3: DialoGPT prompt adaptation
class DialogGPTPromptAdapter:
    """Converts medical instruction prompts to DialoGPT chat format."""
    
    def adapt_medical_prompt(self, instruction_prompt: str) -> str:
        """Convert medical instruction to conversational format."""
        # Extract the core medical question/instruction
        question = self._extract_medical_question(instruction_prompt)
        
        # Format for DialoGPT's chat training
        chat_prompt = f"Human: {question}\n\nAssistant:"
        
        return chat_prompt
    
    def _extract_medical_question(self, instruction_prompt: str) -> str:
        """Extract the core question from complex medical instruction prompts."""
        # Handle Universal Quality System prompts
        if "You are an Emergency Department" in instruction_prompt:
            # Extract the actual user query from the prompt
            lines = instruction_prompt.split('\n')
            for i, line in enumerate(lines):
                if 'USER QUERY:' in line and i + 1 < len(lines):
                    return lines[i + 1].strip('"')
        
        # For simpler prompts, return as-is with slight formatting
        return instruction_prompt.strip()
```

## Validation Loop

### Level 1: Syntax & Style
```bash
# Fix any Python syntax and style issues
ruff check src/ai/gpt_oss_client.py --fix
ruff check src/ai/vllm_model_manager.py --fix  
mypy src/ai/gpt_oss_client.py
mypy src/ai/vllm_model_manager.py

# Expected: No errors. Fix any type hints or imports issues.
```

### Level 2: Unit Tests
```python
# CREATE tests/unit/test_gpt_oss_client.py
import pytest
from unittest.mock import AsyncMock, patch
from src.ai.gpt_oss_client import GPTOSSClient

@pytest.mark.asyncio
async def test_health_check_uses_correct_endpoint():
    """Health check uses /v1/models endpoint."""
    client = GPTOSSClient()
    
    with patch.object(client, '_get_client') as mock_get_client:
        mock_http_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [{"id": "microsoft/DialoGPT-medium"}]
        }
        mock_http_client.get.return_value = mock_response
        mock_get_client.return_value = mock_http_client
        
        result = await client.health_check()
        
        # Verify correct endpoint called
        mock_http_client.get.assert_called_once_with("http://localhost:8000/v1/models")
        assert result is True

@pytest.mark.asyncio 
async def test_generation_uses_correct_endpoint():
    """Generation uses /v1/completions endpoint."""
    client = GPTOSSClient()
    
    with patch.object(client, '_get_client') as mock_get_client:
        mock_http_client = AsyncMock()
        mock_response = AsyncMock() 
        mock_response.json.return_value = {
            "choices": [{"text": "Medical response"}]
        }
        mock_http_client.post.return_value = mock_response
        mock_get_client.return_value = mock_http_client
        
        await client.generate("Test medical query")
        
        # Verify correct endpoint used
        args, kwargs = mock_http_client.post.call_args
        assert args[0] == "http://localhost:8000/v1/completions"

@pytest.mark.asyncio
async def test_empty_response_retry():
    """Empty responses trigger retry logic."""
    client = GPTOSSClient()
    
    with patch.object(client, '_get_client') as mock_get_client:
        mock_http_client = AsyncMock()
        
        # First call returns empty, second returns content
        mock_responses = [
            AsyncMock(json=lambda: {"choices": [{"text": ""}]}),  # Empty
            AsyncMock(json=lambda: {"choices": [{"text": "Valid response"}]})  # Valid
        ]
        mock_http_client.post.side_effect = mock_responses
        mock_get_client.return_value = mock_http_client
        
        result = await client.generate("Test query")
        
        assert result == "Valid response"
        assert mock_http_client.post.call_count == 2  # Retried once
```

```bash
# Run unit tests
pytest tests/unit/test_gpt_oss_client.py -v

# Expected: All tests pass. If failing, fix the client implementation.
```

### Level 3: Integration Test
```bash
# Ensure vLLM container is running
docker.exe compose -f docker-compose.v8.yml --profile gpt-oss up -d gpt-oss

# Wait for model to load
sleep 60

# Test health check directly
curl -s http://localhost:8000/v1/models | jq '.data[0].id'
# Expected: "microsoft/DialoGPT-medium"

# Test completion endpoint directly  
curl -X POST http://localhost:8000/v1/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "microsoft/DialoGPT-medium",
    "prompt": "Human: What is the treatment for anaphylaxis?\nAssistant:",
    "max_tokens": 150,
    "temperature": 0.0
  }' | jq '.choices[0].text'

# Expected: Non-empty medical response

# Test full application integration
curl -X POST http://localhost:8001/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the first-line treatment for anaphylaxis?"}' \
  --connect-timeout 15

# Expected: {"response": "🚨 **Anaphylaxis Treatment**...", "query_type": "DOSAGE_LOOKUP", ...}
# NOT: {"response": "I'm unable to process...", "warnings": ["Query timed out"]}
```

### Level 4: Performance Validation  
```bash
# Test response times under load
for i in {1..10}; do
  time curl -X POST http://localhost:8001/api/v1/query \
    -H "Content-Type: application/json" \
    -d "{\"query\": \"Medical query test $i\"}" \
    --connect-timeout 15 --max-time 10
done

# Expected: 
# - Response time <10 seconds per query
# - Success rate >95% 
# - No timeout errors
# - Meaningful medical responses (not empty/generic)
```

## Final Validation Checklist
- [ ] All unit tests pass: `pytest tests/unit/test_gpt_oss_client.py -v`
- [ ] Integration test successful: vLLM endpoints respond correctly
- [ ] No timeout errors in application logs
- [ ] Medical queries return substantive responses <10s
- [ ] Health checks pass consistently
- [ ] Empty response rate <5% under normal load
- [ ] Error messages are informative (not generic "system load" messages)
- [ ] Fallback mechanisms work if vLLM is temporarily unavailable
- [ ] Model upgrade documentation completed

## Anti-Patterns to Avoid
- ❌ Don't ignore the vLLM OpenAI API compatibility requirements (/v1/ prefix)
- ❌ Don't use DialoGPT-medium for production without considering Mistral-7B upgrade
- ❌ Don't set timeouts too aggressively - medical content generation needs time
- ❌ Don't retry indefinitely on 4xx errors (client errors shouldn't be retried)
- ❌ Don't ignore empty responses - they indicate real vLLM configuration issues
- ❌ Don't use synchronous HTTP clients for LLM requests (use async httpx)
- ❌ Don't hardcode model names - make them configurable for easy upgrades

---

**Confidence Score: 8/10** - High confidence for successful one-pass implementation due to:
✅ Comprehensive root cause analysis with specific technical details  
✅ Multiple working code examples from existing codebase patterns
✅ Extensive external research on vLLM and model performance  
✅ Step-by-step validation with executable commands
✅ Clear error patterns identified with specific fixes
⚠️ Some risk due to vLLM/DialoGPT-medium compatibility edge cases that may require iteration