name: "Switch from Phi3:mini to GPT-OSS 20B for Superior Medical AI Performance"
description: |

## Goal
Replace the current phi3:mini (3.8B) model with GPT-OSS 20B via vLLM for significantly better medical response quality while maintaining the 100% query success rate achieved in PRP 30.

## Why
- **Quality Gap**: phi3:mini (3.8B) vs GPT-OSS 20B represents a 5x+ parameter difference
- **Medical Accuracy**: Larger models provide more accurate, detailed medical information
- **Architecture Intent**: CLAUDE.md specifies GPT-OSS 20B as primary, Ollama as fallback
- **Production Readiness**: phi3:mini was a temporary fix to prove the pipeline works
- **Performance**: GPT-OSS 20B designed for local GPU inference with better medical reasoning

## What
Configure and start GPT-OSS 20B via vLLM while preserving all PRP 30 infrastructure fixes:
1. Start vLLM service with GPT-OSS 20B model
2. Update LLM_BACKEND from `ollama` to `gpt-oss` 
3. Verify all 6 query types continue working with improved responses
4. Maintain fallback to phi3:mini if GPT-OSS fails
5. Validate medical accuracy improvements with ground truth data

### Success Criteria
- [ ] vLLM service running with GPT-OSS 20B on port 8000
- [ ] LLM_BACKEND=gpt-oss configuration active
- [ ] All 6 query types (100%) still working with GPT-OSS
- [ ] Response quality improved over phi3:mini baseline
- [ ] Fallback to phi3:mini works if GPT-OSS unavailable
- [ ] Ground truth validation shows better medical accuracy
- [ ] No regression in SQL fixes, database content, or query routing from PRP 30

## Context Files

### Infrastructure & Configuration
```yaml
- file: docker-compose.v8.yml
  why: Contains vLLM service definition and GPU configuration
  critical: Need to verify vLLM service is properly configured for GPT-OSS 20B
  
- file: .env
  why: Currently has LLM_BACKEND=ollama, needs change to gpt-oss
  critical: Primary configuration switch point
  
- file: src/config/settings.py
  why: LLM backend selection logic and GPT-OSS URL configuration
  critical: Ensures proper backend routing
  
- file: src/api/dependencies.py
  why: LLM client initialization and dependency injection
  critical: Must create GPT-OSS client instead of Ollama client
```

### LLM Client Implementation
```yaml
- file: src/ai/llm_client.py
  why: Unified LLM interface that routes to different backends
  critical: Handles GPT-OSS vs Ollama backend selection
  
- file: src/ai/gpt_oss_client.py
  why: vLLM/GPT-OSS specific client implementation
  critical: May need updates for proper model communication
  
- file: src/ai/ollama_client.py
  why: Current phi3:mini client for fallback scenario
  critical: Keep working as backup if GPT-OSS fails
```

### Validation & Testing
```yaml
- file: ground_truth_qa/guidelines/Hypoglycemia_EBP_Final_qa.json
  why: Medical accuracy validation for hypoglycemia responses
  critical: Compare phi3:mini vs GPT-OSS response quality
  
- file: ground_truth_qa/protocols/ED_sepsis_pathway_qa.json
  why: Protocol complexity test for sepsis management
  critical: GPT-OSS should handle complex medical workflows better
```

### Docker & Services
```yaml
- file: Makefile.v8
  why: Contains GPU vs CPU profile commands (up-gpu vs up-cpu)
  critical: May need to use GPU profile for optimal vLLM performance
  
- file: run.sh
  why: Quick startup script - should launch with appropriate profile
  critical: Ensure GPU resources available for GPT-OSS 20B
```

## Current State Analysis
```yaml
Working Components (from PRP 30):
  - All 6 query types: 100% success rate ✅
  - SQL parameter binding: Fixed ✅  
  - Database seeding: Real medical documents ✅
  - Text search fallback: Working ✅
  - Query classification: Accurate ✅
  - Response formatting: Proper citations ✅

Current Limitations:
  - Using phi3:mini (3.8B parameters) instead of GPT-OSS 20B
  - vLLM service not running (port 8000 unavailable)
  - LLM_BACKEND=ollama instead of gpt-oss
  - Missing GPU acceleration for larger model
  - Suboptimal medical reasoning capability
```

## Implementation Blueprint

### Docker Service Startup Pattern
```bash
# Current (CPU-only with phi3:mini)
make up-cpu  # Uses Ollama profile

# Target (GPU with GPT-OSS 20B)
make up-gpu  # Uses vLLM profile with GPU acceleration
```

### Configuration Switch Pattern
```bash
# Step 1: Update environment
export LLM_BACKEND=gpt-oss
export GPT_OSS_URL=http://localhost:8000/v1
export VLLM_BASE_URL=http://localhost:8000

# Step 2: Start vLLM service
docker compose -f docker-compose.v8.yml --profile gpu up -d vllm

# Step 3: Restart API with new config
uvicorn src.api.app:app --reload
```

### Fallback Safety Pattern
```python
# Ensure graceful fallback if GPT-OSS unavailable
class LLMClient:
    def __init__(self):
        self.primary = GPTOSSClient()
        self.fallback = OllamaClient()
    
    async def generate(self, prompt):
        try:
            return await self.primary.generate(prompt)
        except Exception as e:
            logger.warning(f"GPT-OSS failed, using fallback: {e}")
            return await self.fallback.generate(prompt)
```

## Task Breakdown

### Task 1: Verify Docker GPU Configuration
- Check docker-compose.v8.yml for vLLM service definition
- Verify GPU resources available on system
- Confirm GPT-OSS 20B model is configured correctly
- Test vLLM service startup in isolation

### Task 2: Start vLLM Service with GPT-OSS
- Launch vLLM container with GPU profile
- Verify service health on port 8000
- Test direct API calls to GPT-OSS model
- Confirm model loading and response generation

### Task 3: Update LLM Backend Configuration  
- Change LLM_BACKEND from ollama to gpt-oss in .env
- Update any service configuration files
- Restart API server with new configuration
- Verify dependency injection creates GPT-OSS client

### Task 4: Validate All Query Types Still Work
- Test all 6 query types maintain 100% success rate
- Compare response quality between phi3:mini and GPT-OSS
- Ensure no regression in SQL fixes or database access
- Verify proper error handling and fallback behavior

### Task 5: Performance & Quality Assessment
- Run ground truth validation with GPT-OSS responses
- Measure response time impact (GPU vs CPU)
- Document quality improvements in medical accuracy
- Establish baseline metrics for production use

### Task 6: Fallback Testing
- Simulate GPT-OSS service failure
- Verify automatic fallback to phi3:mini works
- Test recovery when GPT-OSS comes back online
- Ensure no data loss or query failures during transitions

## Validation Loop

### Level 1: Service Health Check
```bash
# Verify vLLM service is running
curl http://localhost:8000/health

# Test direct model generation
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-oss-20b", "messages": [{"role": "user", "content": "What is hypoglycemia?"}]}'
```

### Level 2: Backend Switch Validation
```bash
# Confirm backend selection
python3 -c "from src.config.settings import Settings; s=Settings(); print(f'Backend: {s.llm_backend}')"

# Test unified LLM client
python3 -c "from src.ai.llm_client import LLMClient; import asyncio; asyncio.run(LLMClient().generate('Test'))"
```

### Level 3: End-to-End Query Testing
```bash
# Test all query types with GPT-OSS
curl -X POST http://localhost:8002/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "summarize hypoglycemia treatment"}'

# Expected: Higher quality, more detailed medical response than phi3:mini
```

### Level 4: Quality Comparison Analysis  
```python
# Compare phi3:mini vs GPT-OSS responses
test_queries = [
    "What is the standard treatment for severe hypoglycemia?",
    "Describe the STEMI activation protocol timing requirements", 
    "What are the sepsis reassessment criteria at 3 hours?"
]

for query in test_queries:
    phi3_response = query_with_backend("ollama", query)
    gptoss_response = query_with_backend("gpt-oss", query)
    
    print(f"Query: {query}")
    print(f"Phi3 Quality Score: {evaluate_medical_accuracy(phi3_response)}")
    print(f"GPT-OSS Quality Score: {evaluate_medical_accuracy(gptoss_response)}")
```

## Risk Mitigation

### GPU Resource Requirements
- **Risk**: GPT-OSS 20B requires significant GPU memory
- **Mitigation**: Verify GPU specs, use model quantization if needed
- **Fallback**: Keep phi3:mini working for resource-constrained environments

### Service Startup Dependencies
- **Risk**: vLLM may take time to load 20B model on startup
- **Mitigation**: Implement health checks with retries
- **Fallback**: Start with Ollama until vLLM ready

### Configuration Conflicts
- **Risk**: Environment variables may conflict between backends
- **Mitigation**: Clear separation of GPT-OSS vs Ollama config
- **Fallback**: Preserve working .env as .env.phi3.backup

## Success Metrics

### Primary Metrics
- **Query Success Rate**: Maintain 100% (6/6 query types)
- **Response Quality**: Measurable improvement in medical accuracy
- **Service Uptime**: vLLM service healthy and responsive
- **Fallback Reliability**: Automatic fallback works when needed

### Secondary Metrics  
- **Response Time**: Acceptable latency with GPU acceleration
- **Resource Usage**: GPU memory and CPU utilization within limits
- **Error Rate**: Minimal failures during backend switching
- **Medical Accuracy**: Ground truth validation scores improve

## Final Validation Checklist
- [ ] vLLM service running with GPT-OSS 20B model loaded
- [ ] LLM_BACKEND=gpt-oss active in configuration
- [ ] All 6 query types working (CONTACT, FORM, PROTOCOL, CRITERIA, DOSAGE, SUMMARY)  
- [ ] Response quality visibly improved over phi3:mini baseline
- [ ] Fallback to phi3:mini works if GPT-OSS fails
- [ ] No regression in PRP 30 fixes (SQL, database, routing)
- [ ] Ground truth validation shows better medical accuracy scores
- [ ] Docker GPU profile working correctly
- [ ] API performance acceptable with larger model

## Quality Score: 10/10
This PRP maintains all PRP 30 infrastructure fixes while upgrading to the intended production LLM backend. The approach is conservative (preserving fallbacks) while targeting the architecture specified in CLAUDE.md documentation.

## Anti-Patterns to Avoid
- ❌ Don't break PRP 30 fixes - all SQL/database/routing improvements must be preserved
- ❌ Don't remove phi3:mini fallback - keep it as backup for reliability
- ❌ Don't skip service health checks - vLLM startup can be slow with large models
- ❌ Don't ignore GPU requirements - GPT-OSS 20B needs appropriate hardware
- ❌ Don't change multiple things at once - switch backends cleanly without other changes
- ❌ Don't skip quality validation - measure the actual improvement in medical accuracy