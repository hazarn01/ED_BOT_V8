# PRP-28: Transition to GPT-OSS 20B as Primary LLM

## Status: PROPOSED
**Created**: 2025-01-26
**Priority**: HIGH
**Effort**: 4 hours

## Context
With 128GB RAM now available, we can run GPT-OSS 20B locally via vLLM, providing superior medical response quality while maintaining HIPAA compliance and eliminating external dependencies.

## Problem Statement
Current Ollama/Mistral 7B setup has limitations:
- Lower quality medical responses compared to larger models
- Less nuanced understanding of medical terminology
- Reduced accuracy in complex query classification
- Limited context window for protocol synthesis

## Proposed Solution

### 1. vLLM Service Configuration
Create dedicated vLLM service in docker-compose for GPT-OSS 20B inference:
- Allocate 40-50GB RAM for model loading
- Configure tensor parallelism for optimal throughput
- Set up health checks and auto-restart policies
- Implement request batching for efficiency

### 2. LLM Backend Switching
Enhance existing LLM abstraction to support seamless backend switching:
- Primary: GPT-OSS 20B via vLLM
- Fallback 1: Ollama/Mistral (if vLLM unavailable)
- Fallback 2: Azure OpenAI (emergency only)
- Runtime detection and automatic failover

### 3. Performance Optimization
Tune vLLM settings for medical workloads:
- KV cache optimization for repeated queries
- Continuous batching for multi-user scenarios
- Quantization options (FP16/INT8) if needed
- GPU offloading for acceleration (if available)

### 4. Medical-Specific Prompting
Optimize prompts for GPT-OSS 20B capabilities:
- Enhanced medical reasoning chains
- Multi-hop citation tracking
- Confidence calibration for medical advice
- Safety guardrails for dosage validation

## Implementation Plan

### Phase 1: vLLM Service Setup (1 hour)
```yaml
# docker-compose.v8.yml additions
vllm:
  image: vllm/vllm-openai:latest
  container_name: edbotv8-vllm
  profiles: ["gpt-oss"]
  environment:
    - MODEL_NAME=TheBloke/GPT-OSS-20B-GPTQ
    - TENSOR_PARALLEL_SIZE=1
    - MAX_MODEL_LEN=4096
    - GPU_MEMORY_UTILIZATION=0.95
  volumes:
    - vllm-cache:/root/.cache/huggingface
  ports:
    - "8002:8000"
  deploy:
    resources:
      limits:
        memory: 50G
      reservations:
        memory: 40G
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
    interval: 30s
    timeout: 10s
    retries: 3
```

### Phase 2: LLM Client Enhancement (1.5 hours)
```python
# src/ai/llm_client.py modifications
class LLMClient:
    def __init__(self, settings: Settings):
        self.backend = settings.LLM_BACKEND
        self.clients = self._initialize_clients(settings)
        
    def _initialize_clients(self, settings):
        clients = {}
        
        # Primary: GPT-OSS via vLLM
        if settings.VLLM_ENABLED:
            clients['vllm'] = AsyncOpenAI(
                base_url=settings.VLLM_BASE_URL,
                api_key="EMPTY",
                timeout=30.0
            )
        
        # Fallback: Ollama
        if settings.OLLAMA_ENABLED:
            clients['ollama'] = AsyncClient(
                host=settings.OLLAMA_BASE_URL
            )
            
        return clients
    
    async def generate(self, prompt: str, **kwargs):
        # Try backends in priority order
        backends = ['vllm', 'ollama', 'azure']
        
        for backend in backends:
            if backend in self.clients:
                try:
                    return await self._generate_with_backend(
                        backend, prompt, **kwargs
                    )
                except Exception as e:
                    logger.warning(f"{backend} failed: {e}")
                    continue
                    
        raise RuntimeError("All LLM backends failed")
```

### Phase 3: Configuration Updates (30 mins)
```python
# src/config/settings.py additions
class Settings(BaseSettings):
    # LLM Backend Configuration
    LLM_BACKEND: str = "vllm"  # Primary backend
    
    # vLLM Settings
    VLLM_ENABLED: bool = True
    VLLM_BASE_URL: str = "http://vllm:8000/v1"
    VLLM_MODEL: str = "TheBloke/GPT-OSS-20B-GPTQ"
    VLLM_MAX_TOKENS: int = 2048
    VLLM_TEMPERATURE: float = 0.0  # Deterministic for medical
    
    # Ollama Settings (Fallback)
    OLLAMA_ENABLED: bool = True
    OLLAMA_BASE_URL: str = "http://ollama:11434"
    
    # Memory Allocation
    VLLM_MEMORY_GB: int = 45  # Allocate 45GB for model
    SYSTEM_RESERVED_GB: int = 20  # Keep 20GB for system
```

### Phase 4: Testing & Validation (1 hour)
```python
# tests/integration/test_gpt_oss.py
async def test_gpt_oss_medical_accuracy():
    """Verify GPT-OSS improves medical response quality"""
    
    test_queries = [
        "complex STEMI protocol with contraindications",
        "pediatric dosing for epinephrine in anaphylaxis",
        "differential diagnosis for chest pain with EKG changes"
    ]
    
    for query in test_queries:
        # Compare responses from different models
        mistral_response = await get_mistral_response(query)
        gpt_oss_response = await get_gpt_oss_response(query)
        
        # GPT-OSS should provide more detailed, accurate responses
        assert len(gpt_oss_response) > len(mistral_response)
        assert_medical_accuracy(gpt_oss_response)
        assert_citation_preservation(gpt_oss_response)
```

## Rollout Strategy

### Stage 1: Development Testing
1. Deploy vLLM service with GPT-OSS 20B
2. Run parallel inference comparing Mistral vs GPT-OSS
3. Validate medical accuracy improvements
4. Monitor memory usage and response times

### Stage 2: A/B Testing
1. Route 10% of queries to GPT-OSS
2. Compare quality metrics:
   - Classification accuracy
   - Response completeness
   - Citation preservation
   - User satisfaction
3. Gradually increase to 50% if metrics improve

### Stage 3: Full Migration
1. Make GPT-OSS primary backend
2. Keep Ollama as hot standby
3. Monitor for 48 hours
4. Document performance improvements

## Success Criteria
- [ ] GPT-OSS 20B running with <50GB memory usage
- [ ] Response time <2s for 95% of queries
- [ ] Classification accuracy >95% (up from 90%)
- [ ] Zero external API calls (HIPAA compliance)
- [ ] Automatic fallback working seamlessly
- [ ] Medical validation tests passing

## Risk Mitigation
- **Memory exhaustion**: Implement swap file, tune KV cache
- **Slow cold starts**: Pre-warm model on container start
- **Response latency**: Use continuous batching, optimize prompts
- **Model download**: Pre-cache model weights in Docker image

## Commands

```bash
# Start with GPT-OSS profile
make up-gpt-oss

# Test model inference
make test-llm-backend

# Compare model outputs
make compare-models

# Monitor memory usage
make monitor-memory
```

## Dependencies
- PRP-22: Configuration flags for backend selection
- PRP-24: Observability for performance monitoring
- PRP-27: Async patterns for concurrent inference

## Notes
- GPT-OSS 20B requires ~40GB RAM when quantized to 4-bit
- Consider INT8 quantization if memory becomes tight
- vLLM supports PagedAttention for efficient memory use
- Can add GPU acceleration later if CUDA device available