name: "Fix Infrastructure and Service Dependencies"
description: |

## Goal
Fix critical infrastructure and service dependency issues preventing ED Bot v8 from functioning end-to-end. The query classification pipeline is working, but database connections, LLM backend, Redis caching, and health monitoring are failing due to misconfigured hostnames and missing services.

## Why
- **User Impact**: Users receive generic "error processing query" instead of medical information
- **Service Reliability**: Health score of 0.222/1.0 prevents production deployment
- **Pipeline Broken**: Query classification works but routing/response generation fails
- **Infrastructure Mismatch**: Container hostnames used in host development environment

## What
Fix all infrastructure components to work correctly in host development mode:
1. Database hostname configuration (currently trying "db" instead of "localhost")
2. LLM backend service availability (Ollama 404 errors)
3. Redis caching service connectivity and configuration
4. Health monitoring accuracy and service dependency checks
5. End-to-end query processing pipeline validation

### Success Criteria
- [ ] Health check reports healthy status (>0.8 score)
- [ ] Database queries work without hostname resolution errors
- [ ] LLM backend responds to generation requests
- [ ] Redis caching operational for query results
- [ ] Manual testing shows real medical responses (not error messages)
- [ ] All 6 query types return substantive content

## All Needed Context

### Documentation & References
```yaml
- url: https://docs.docker.com/compose/networking/
  why: Understanding container vs host networking for hostname resolution
  critical: Container hostnames ("db", "redis") don't resolve on host

- url: https://ollama.ai/docs/api
  why: Ollama API endpoint documentation for LLM backend
  critical: /api/generate endpoint returning 404, may need /api/chat

- file: docker-compose.v8.yml
  why: Service configuration and networking setup
  pattern: Shows which services should be running and their ports

- file: src/config/settings.py
  why: Environment-aware configuration for host vs container mode
  critical: Database and service hostnames need environment detection

- file: CLAUDE.md
  why: Make commands and service startup procedures
  pattern: Documents how to start services for development
```

### Current Error Analysis
```bash
# Database Connection Errors
ERROR: could not translate host name "db" to address: Temporary failure in name resolution
CAUSE: Components using container hostname in host development mode
LOCATION: src/pipeline/router.py, src/pipeline/rag_retriever.py

# LLM Backend Errors  
ERROR: Client error '404 Not Found' for url 'http://localhost:11434/api/generate'
CAUSE: Ollama service not running or wrong API endpoint
LOCATION: src/ai/ollama_client.py, src/pipeline/router.py

# Redis Connection Errors
ERROR: Error -3 connecting to redis:6379. Temporary failure in name resolution  
CAUSE: Redis hostname configuration and service availability
LOCATION: src/api/dependencies.py (partially fixed)

# Health Score Issues
INFO: Health check complete: unhealthy (score: 0.222)
CAUSE: Multiple service dependencies failing checks
LOCATION: src/observability/health.py
```

### Service Architecture Analysis
```yaml
Expected Services:
  - PostgreSQL: localhost:5432 (for database queries)
  - Redis: localhost:6379 (for caching)  
  - Ollama: localhost:11434 (for LLM inference)
  
Current State:
  - PostgreSQL: ✅ Available (health check passes some tests)
  - Redis: ❌ Connection failing or not running
  - Ollama: ❌ 404 errors on API calls

Service Dependencies:
  - QueryProcessor → Database (for document retrieval)
  - QueryRouter → Database (for protocol/form queries)  
  - QueryProcessor → Redis (for caching)
  - QueryRouter → LLM Client → Ollama (for response generation)
  - HealthMonitor → All services (for status reporting)
```

### Known Configuration Issues
```python
# ISSUE 1: Mixed hostname configuration
# Some places use "localhost", others use container names
DATABASE_URL: postgresql+psycopg2://postgres:postgres@localhost:5432/edbotv8  # ✅ Correct
REDIS_HOST: localhost  # ✅ Fixed in dependencies.py
DB_HOST in other components: "db"  # ❌ Wrong for host mode

# ISSUE 2: Ollama API endpoint mismatch
# Current: http://localhost:11434/api/generate
# May need: http://localhost:11434/api/chat or different endpoint

# ISSUE 3: Service availability
# Services may not be running or accessible on expected ports
```

## Implementation Blueprint

### Service Startup Verification
```bash
# Check which services are actually running
netstat -tlnp | grep -E "(5432|6379|11434)"
docker ps | grep -E "(postgres|redis|ollama)"

# Expected output for healthy system:
# tcp 0.0.0.0:5432 ... postgres
# tcp 0.0.0.0:6379 ... redis  
# tcp 0.0.0.0:11434 ... ollama
```

### List of Tasks (In Order)

```yaml
Task 1 - Audit Current Service Status:
  RUN diagnostic commands to check service availability:
    - netstat -tlnp | grep -E "(5432|6379|11434)"
    - curl -s http://localhost:11434/api/tags (test Ollama)
    - curl -s http://localhost:6379 (test Redis - will fail but show connection)
    - PGPASSWORD=postgres psql -h localhost -p 5432 -U postgres -d edbotv8 -c "SELECT 1" (test DB)
  DOCUMENT which services are running vs expected

Task 2 - Start Missing Services:
  IF Ollama not running:
    - CHECK if ollama is installed: which ollama
    - START Ollama service: ollama serve (background) or systemctl start ollama
    - VERIFY with: curl -s http://localhost:11434/api/tags
    
  IF Redis not running:
    - CHECK if redis is installed: which redis-server
    - START Redis: redis-server (background) or systemctl start redis
    - VERIFY with: redis-cli ping
    
  IF PostgreSQL issues:
    - VERIFY connection: PGPASSWORD=postgres psql -h localhost -p 5432 -U postgres -d edbotv8 -c "SELECT version();"
    - CHECK if seeded: PGPASSWORD=postgres psql -h localhost -p 5432 -U postgres -d edbotv8 -c "SELECT COUNT(*) FROM documents;"

Task 3 - Fix Database Hostname Configuration:
  MODIFY files using hardcoded "db" hostname:
    - SEARCH for: grep -r "host.*db" src/ --include="*.py"
    - FIND locations using "db" as hostname
    - REPLACE with environment-aware hostname resolution
    - PATTERN: Use settings.db_host with fallback to "localhost"

Task 4 - Fix Ollama API Endpoint:
  MODIFY src/ai/ollama_client.py:
    - CHECK current API endpoint being used
    - TEST different endpoints: /api/generate vs /api/chat vs /v1/chat/completions
    - UPDATE to working endpoint based on Ollama version
    - ADD proper error handling for API responses

Task 5 - Verify Service Health Configuration:
  MODIFY src/observability/health.py:
    - ENSURE all health checks use localhost hostnames
    - VERIFY timeout settings are appropriate
    - TEST each health check method individually
    - UPDATE health scoring to reflect actual service importance

Task 6 - End-to-End Pipeline Testing:
  TEST complete query processing:
    - curl -X POST http://localhost:8002/api/v1/query -H "Content-Type: application/json" -d '{"query": "who is on call for cardiology"}'
    - VERIFY response contains actual contact information, not error message
    - TEST all 6 query types: CONTACT, FORM, PROTOCOL, CRITERIA, DOSAGE, SUMMARY
    - CONFIRM health endpoint returns >0.8 score
```

### Environment-Aware Configuration Pattern
```python
# PATTERN: Environment detection for hostname resolution
def get_database_hostname():
    """Get database hostname based on environment context."""
    # Check if running in container (has /.dockerenv or container env vars)
    if os.path.exists('/.dockerenv') or os.environ.get('CONTAINER_ENV'):
        return "db"  # Use container hostname
    else:
        return os.environ.get('DB_HOST', 'localhost')  # Use host networking

# Apply to all service connections:
# - Database connections
# - Redis connections  
# - Health check hostnames
# - Service discovery
```

### Service Discovery & Health Logic
```python
# PATTERN: Graceful service discovery with fallbacks
async def check_service_health(service_name, host, port, timeout=5):
    """Check if a service is responding with proper error handling."""
    try:
        # Attempt connection
        conn = await asyncio.wait_for(
            asyncio.open_connection(host, port), 
            timeout=timeout
        )
        conn[1].close()
        return True, f"{service_name} responsive on {host}:{port}"
    except Exception as e:
        return False, f"{service_name} failed: {str(e)}"

# Use for all service health checks before attempting operations
```

## Validation Loop

### Level 1: Service Availability
```bash
# Verify all required services are running
netstat -tlnp | grep -E "(5432|6379|11434)"

# Expected: 3 services listening on expected ports
# If missing, start services using appropriate commands
```

### Level 2: API Connectivity
```bash
# Test each service API individually
curl -s http://localhost:11434/api/tags  # Ollama
redis-cli ping  # Redis  
PGPASSWORD=postgres psql -h localhost -p 5432 -U postgres -d edbotv8 -c "SELECT 1"  # PostgreSQL

# Expected: All commands return successful responses
```

### Level 3: Application Health
```bash
# Test health endpoint
curl -s http://localhost:8002/health

# Expected: {"status": "healthy", "health_score": >0.8}
```

### Level 4: End-to-End Query Testing
```bash
# Test all 6 query types return real content
curl -X POST http://localhost:8002/api/v1/query -H "Content-Type: application/json" -d '{"query": "who is on call for cardiology"}'
# Expected: Actual contact information, not error message

curl -X POST http://localhost:8002/api/v1/query -H "Content-Type: application/json" -d '{"query": "show me blood transfusion form"}'
# Expected: PDF link or form information

curl -X POST http://localhost:8002/api/v1/query -H "Content-Type: application/json" -d '{"query": "what is the STEMI protocol"}'
# Expected: Protocol steps and timing information
```

## Final Validation Checklist
- [ ] All services responding on expected ports (5432, 6379, 11434)
- [ ] Database queries execute without hostname resolution errors
- [ ] LLM backend generates responses without 404 errors
- [ ] Redis caching operational (can set/get test values)
- [ ] Health check reports >0.8 score
- [ ] Manual API tests return medical content (not generic errors)
- [ ] All 6 query types process successfully end-to-end

## Quality Score: 9/10
This PRP addresses critical infrastructure issues with specific diagnostic commands and step-by-step fixes. The main complexity is service discovery and environment-aware configuration, but clear patterns and validation steps are provided. Success depends on proper service startup and hostname configuration consistency.

## Anti-Patterns to Avoid
- ❌ Don't hardcode hostnames - use environment-aware configuration
- ❌ Don't skip service availability checks - verify before attempting connections
- ❌ Don't ignore health check failures - investigate and fix root causes
- ❌ Don't test only happy path - verify error handling and fallbacks
- ❌ Don't mix container and host networking assumptions in same deployment
- ❌ Don't assume services are running - always verify with diagnostic commands