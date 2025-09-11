# PRP 14: Add Elasticsearch as Optional Service

## Problem Statement
The current system relies solely on pgvector for semantic search. Adding Elasticsearch as an optional service would enable hybrid search capabilities (combining keyword and semantic search) to improve retrieval precision for clinical terminology, protocol names, and form identifiers where exact matches matter.

## Success Criteria
- Elasticsearch service runs healthy under optional compose profile
- Default system continues using pgvector-only without regression
- ES connection attempts fail gracefully when service unavailable
- `GET :9200/_cluster/health` returns green status when enabled

## Implementation Approach

### 1. Docker Compose Configuration
```yaml
# docker-compose.v8.yml
elasticsearch:
  image: elasticsearch:8.11.1
  container_name: edbot-elasticsearch
  profiles: [search]  # Optional profile
  environment:
    - discovery.type=single-node
    - xpack.security.enabled=false  # Dev only
    - ES_JAVA_OPTS=-Xms512m -Xmx512m
    - cluster.name=edbot-cluster
  ports:
    - "9200:9200"
  volumes:
    - es_data:/usr/share/elasticsearch/data
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:9200/_cluster/health"]
    interval: 30s
    timeout: 10s
    retries: 5
```

### 2. Settings Configuration
```python
# src/config/settings.py
class Settings(BaseSettings):
    # Search backend configuration
    search_backend: Literal["pgvector", "hybrid"] = Field(
        default="pgvector",
        description="Search backend: pgvector (default) or hybrid (pgvector + ES)"
    )
    
    # Elasticsearch settings
    elasticsearch_url: str = Field(
        default="http://elasticsearch:9200",
        description="Elasticsearch URL for hybrid search"
    )
    elasticsearch_index_prefix: str = Field(
        default="edbot",
        description="Index prefix for Elasticsearch"
    )
    elasticsearch_timeout: int = Field(
        default=30,
        description="Elasticsearch request timeout in seconds"
    )
```

### 3. Connection Manager
```python
# src/search/elasticsearch_client.py
from elasticsearch import Elasticsearch
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class ElasticsearchClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._client: Optional[Elasticsearch] = None
        self.enabled = settings.search_backend == "hybrid"
        
    def get_client(self) -> Optional[Elasticsearch]:
        """Get ES client with lazy initialization and graceful fallback"""
        if not self.enabled:
            return None
            
        if self._client is None:
            try:
                self._client = Elasticsearch(
                    [self.settings.elasticsearch_url],
                    timeout=self.settings.elasticsearch_timeout,
                    max_retries=3,
                    retry_on_timeout=True
                )
                # Test connection
                if not self._client.ping():
                    logger.warning("Elasticsearch ping failed, disabling hybrid search")
                    self.enabled = False
                    return None
                logger.info("Elasticsearch connection established")
            except Exception as e:
                logger.warning(f"Failed to connect to Elasticsearch: {e}")
                self.enabled = False
                return None
                
        return self._client
```

### 4. Makefile Targets
```makefile
# Makefile.v8
up-search:  ## Start stack with Elasticsearch for hybrid search
	docker compose --profile cpu --profile search up -d
	@echo "Waiting for Elasticsearch..."
	@sleep 10
	@curl -s http://localhost:9200/_cluster/health | jq '.'

es-health:  ## Check Elasticsearch health
	@curl -s http://localhost:9200/_cluster/health | jq '.'

es-indices:  ## List Elasticsearch indices
	@curl -s http://localhost:9200/_cat/indices?v
```

### 5. Dependency Injection
```python
# src/api/dependencies.py
from src.search.elasticsearch_client import ElasticsearchClient

def get_elasticsearch_client(settings: Settings = Depends(get_settings)) -> Optional[ElasticsearchClient]:
    """Get Elasticsearch client if hybrid search enabled"""
    if settings.search_backend == "hybrid":
        client = ElasticsearchClient(settings)
        return client if client.get_client() else None
    return None
```

## Testing Strategy
```bash
# Test default (pgvector only)
docker compose up -d
curl http://localhost:8001/health  # Should work without ES

# Test with Elasticsearch
docker compose --profile search up -d
sleep 10
curl http://localhost:9200/_cluster/health  # Should be green
curl http://localhost:8001/health  # Should still work

# Test graceful degradation
docker compose stop elasticsearch
curl http://localhost:8001/api/v1/query  # Should fallback to pgvector
```

## Rollback Plan
1. Set `SEARCH_BACKEND=pgvector` in environment
2. Stop Elasticsearch: `docker compose stop elasticsearch`
3. System continues with pgvector-only search
4. Optional: Remove ES data volume if needed

## Security Considerations
- Security disabled for dev environment only
- Production would require:
  - TLS/SSL enabled
  - Authentication configured
  - Network isolation
  - Resource limits enforced

## Performance Impact
- No impact when disabled (default)
- When enabled:
  - Additional 512MB memory for ES
  - ~10s startup delay for ES health
  - Network overhead for dual indexing
  - Improved search precision for exact matches