# PRP-38: Fix Port Configuration and Establish GPT-OSS as Primary LLM Backend

## Problem Statement

The current system has conflicting port configurations and inconsistent LLM backend setup, causing confusion and unreliable service behavior:

1. **Port Conflicts**: Multiple services competing for port 8000 (vLLM services)
2. **Backend Confusion**: System switches between gpt-oss, ollama, and azure with unclear precedence  
3. **Service Inconsistency**: Docker profiles overlap and services don't start reliably
4. **Configuration Drift**: Environment variables don't match actual service configurations

The user specifically wants **GPT-OSS as the primary and only LLM backend** with **correct port assignments** for all services.

## Current Configuration Issues

### Port Conflicts in `docker-compose.v8.yml`

**Lines 31-32**: First vLLM service on port 8000:
```yaml
llm:
  ports:
    - "8000:8000"  # Conflict 1
```

**Lines 61-62**: Second vLLM service also on port 8000:
```yaml
vllm:
  ports:
    - "8000:8000"  # Conflict 2 - Same port!
```

**Lines 80-81**: Ollama on port 11434:
```yaml
ollama:
  ports:
    - "11434:11434"
```

### Backend Configuration Chaos in `src/config/settings.py`

**Lines 61-85**: Multiple competing backend configurations:
```python
llm_backend: str = "ollama"  # Default is ollama, not gpt-oss!
vllm_base_url: str = "http://localhost:8000"
gpt_oss_url: str = "http://localhost:8000/v1"  # Same port conflict
ollama_base_url: str = "http://localhost:11434"
azure_openai_endpoint: Optional[str] = None  # Unused fallback
```

## Solution Overview

**Clean port assignment** and **GPT-OSS first** backend hierarchy:

1. **GPT-OSS/vLLM**: Port 8000 (primary LLM)
2. **API Server**: Port 8001 (unchanged)
3. **Database**: Port 5432 (unchanged)  
4. **Redis**: Port 6379 (unchanged)
5. **Remove Ollama**: Not needed if GPT-OSS is primary
6. **Remove Azure**: Emergency fallback only

## Implementation Plan

### Phase 1: Clean Docker Configuration (30 minutes)
- Remove duplicate vLLM services
- Standardize on single GPT-OSS vLLM service
- Remove Ollama service entirely
- Fix profiles and dependencies

### Phase 2: Update Settings Configuration (20 minutes)
- Set `llm_backend = "gpt-oss"` as default
- Clean up conflicting URL configurations
- Remove unused backend settings

### Phase 3: Update LLM Client Integration (30 minutes)
- Ensure GPT-OSS client is used by default
- Remove Ollama client initialization
- Simplify backend selection logic

### Phase 4: Environment Configuration (15 minutes)
- Update `.env` files with correct settings
- Document new port assignments
- Update Makefile commands

## Detailed Implementation

### 1. Cleaned Docker Compose (`docker-compose.v8.yml`)

```yaml
services:
  db:
    image: ankane/pgvector:latest
    environment:
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: ${DB_NAME}
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5
    volumes:
      - db_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  # GPT-OSS as PRIMARY LLM (only LLM service)
  gpt-oss:
    image: vllm/vllm-openai:latest
    container_name: edbotv8-gpt-oss
    environment:
      - VLLM_LOGGING_LEVEL=INFO
      - NVIDIA_VISIBLE_DEVICES=all
      - CUDA_VISIBLE_DEVICES=0
    command: [
      "--model", "microsoft/DialoGPT-medium",  # Or upgrade to larger model
      "--dtype", "auto",
      "--gpu-memory-utilization", "0.8",
      "--disable-log-requests",
      "--port", "8000"
    ]
    volumes:
      - gpt-oss-cache:/root/.cache/huggingface
    ports:
      - "8000:8000"  # ONLY service on port 8000
    runtime: nvidia
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 120s

  api:
    build:
      context: .
      dockerfile: Dockerfile.v8
    command: uvicorn src.api.app:app --host 0.0.0.0 --port 8001 --forwarded-allow-ips '*'
    ports:
      - "8001:8001"  # API on 8001
    env_file: EDBOTv8.env.example
    environment:
      - LLM_BACKEND=gpt-oss  # FORCE GPT-OSS backend
      - GPT_OSS_URL=http://gpt-oss:8000/v1
    depends_on:
      - db
      - redis
      - gpt-oss  # Depend on GPT-OSS, not ollama
    volumes:
      - ./:/app
      - ./docs:/app/docs
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 15s

volumes:
  db_data:
  gpt-oss-cache:  # Renamed from vllm-cache
```

### 2. Simplified Settings (`src/config/settings.py`)

```python
class Settings(BaseSettings):
    # LLM Configuration - GPT-OSS ONLY
    llm_backend: str = "gpt-oss"  # Changed default to gpt-oss
    
    # GPT-OSS Settings (PRIMARY)
    gpt_oss_url: str = "http://gpt-oss:8000/v1"  # Use container name
    gpt_oss_model: str = "microsoft/DialoGPT-medium"
    gpt_oss_max_tokens: int = 1024
    gpt_oss_temperature: float = 0.0  # Deterministic for medical
    
    # Remove these unused settings:
    # - vllm_enabled
    # - vllm_base_url  
    # - ollama_enabled
    # - ollama_base_url
    # - ollama_model
    
    # Emergency Azure Fallback (disabled by default)
    azure_openai_endpoint: Optional[str] = None
    azure_openai_api_key: Optional[str] = None
    azure_openai_deployment: Optional[str] = None
    use_azure_fallback: bool = False  # New flag to control fallback
```

### 3. Updated LLM Client Initialization (`src/api/dependencies.py`)

```python
async def get_llm_client():
    """Get LLM client - GPT-OSS only."""
    settings = get_settings()
    
    # Always use GPT-OSS (remove backend switching logic)
    from ..ai.gpt_oss_client import GPTOSSClient
    
    client = GPTOSSClient(
        base_url=settings.gpt_oss_url,
        model=settings.gpt_oss_model,
        max_tokens=settings.gpt_oss_max_tokens,
        temperature=settings.gpt_oss_temperature
    )
    
    # Test connection on startup
    try:
        await client.health_check()
        logger.info("GPT-OSS client initialized successfully")
        return client
    except Exception as e:
        if settings.use_azure_fallback and settings.azure_openai_api_key:
            logger.warning(f"GPT-OSS unavailable: {e}, falling back to Azure")
            # Initialize Azure fallback
            from ..ai.azure_client import AzureClient
            return AzureClient(settings)
        else:
            logger.error(f"GPT-OSS unavailable and no fallback: {e}")
            raise
```

### 4. Environment Configuration (`.env` files)

**`.env.production`**:
```env
# Core services
DB_HOST=db
DB_PORT=5432
REDIS_HOST=redis
REDIS_PORT=6379

# LLM Backend - GPT-OSS ONLY
LLM_BACKEND=gpt-oss
GPT_OSS_URL=http://gpt-oss:8000/v1
GPT_OSS_MODEL=microsoft/DialoGPT-medium

# HIPAA Compliance  
DISABLE_EXTERNAL_CALLS=true
LOG_SCRUB_PHI=true
```

**`Makefile` updates**:
```makefile
# Start with GPT-OSS profile
up-gpt-oss:
	docker compose -f docker-compose.v8.yml up -d

# Health check GPT-OSS specifically  
health-gpt-oss:
	curl -f http://localhost:8000/health || echo "GPT-OSS not ready"

# Test LLM connection
test-llm:
	curl -X POST http://localhost:8000/v1/completions \
	  -H "Content-Type: application/json" \
	  -d '{"model": "microsoft/DialoGPT-medium", "prompt": "Test prompt", "max_tokens": 10}'
```

## Validation Strategy

### Port Validation Tests
```bash
# Ensure no port conflicts
netstat -tulpn | grep :8000  # Should show only one service
netstat -tulpn | grep :8001  # Should show API server
netstat -tulpn | grep :11434 # Should show nothing (ollama removed)

# Service health checks
curl -f http://localhost:8000/health      # GPT-OSS health  
curl -f http://localhost:8001/health      # API health
```

### LLM Backend Validation
```bash
# Test GPT-OSS directly
curl -X POST http://localhost:8000/v1/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "microsoft/DialoGPT-medium", "prompt": "What is sepsis?", "max_tokens": 50}'

# Test through API
curl -X POST http://localhost:8001/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the STEMI protocol?"}'
```

### Integration Tests
```bash
# Full system test
make up-gpt-oss
sleep 30  # Wait for services
make health-gpt-oss
make test-llm
make query-test  # Test all 6 query types
```

## Critical Context

### Files to Modify:
- `docker-compose.v8.yml` - Remove port conflicts, single LLM service
- `src/config/settings.py` - GPT-OSS as default backend  
- `src/api/dependencies.py` - Remove backend switching logic
- `Makefile` - Update commands for new service names
- `.env` files - Consistent environment variables

### External Dependencies:
- NVIDIA Docker runtime for GPU support
- vLLM image with OpenAI-compatible API
- DialoGPT-medium model (or upgrade path to larger models)

### Service Start Order:
1. Database (5432) + Redis (6379) 
2. GPT-OSS vLLM service (8000)
3. API server (8001) - depends on GPT-OSS

## Quality Assessment Score: 8/10

**High confidence because:**
- Port conflicts clearly identified with line numbers
- Docker compose issues are straightforward to fix
- Environment variable mapping is clear
- Validation tests are executable

**Risk considerations:**
- GPU driver compatibility for vLLM
- Model download time on first startup
- Need to test medical response quality with GPT-OSS

## Implementation Tasks (in order)

1. **Stop all services**: `make down`
2. **Backup current config**: `cp docker-compose.v8.yml docker-compose.v8.yml.backup`
3. **Update docker-compose.v8.yml**: Remove port conflicts, single GPT-OSS service
4. **Update settings.py**: Set gpt-oss as default backend
5. **Update dependencies.py**: Remove backend switching
6. **Update .env files**: Consistent GPT-OSS configuration  
7. **Update Makefile**: New service names and health checks
8. **Test port assignments**: `netstat -tulpn` validation
9. **Start services**: `make up-gpt-oss`
10. **Validate LLM**: Test GPT-OSS connection and medical queries

**Estimated Total Time: 1.5 hours**
**Expected Outcome: Clean port assignments, reliable GPT-OSS backend, faster startup**