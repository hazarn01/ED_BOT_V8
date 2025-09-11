import logging
from typing import Optional

from elasticsearch import Elasticsearch

from src.config.settings import Settings

logger = logging.getLogger(__name__)


class ElasticsearchClient:
    """Elasticsearch client with lazy initialization and graceful fallback."""
    
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
    
    def is_available(self) -> bool:
        """Check if Elasticsearch is available and healthy."""
        return self.enabled and self.get_client() is not None
    
    def get_cluster_health(self) -> Optional[dict]:
        """Get Elasticsearch cluster health information."""
        client = self.get_client()
        if not client:
            return None
            
        try:
            return client.cluster.health()
        except Exception as e:
            logger.error(f"Failed to get cluster health: {e}")
            return None
