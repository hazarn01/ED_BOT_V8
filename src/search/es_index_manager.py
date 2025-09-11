"""Elasticsearch index management for document ingestion."""

import logging
from typing import Dict

from elasticsearch.exceptions import RequestError

from ..config.settings import Settings
from .elasticsearch_client import ElasticsearchClient
from .es_mappings import (
    CHUNK_INDEX_MAPPING,
    DOCUMENT_INDEX_MAPPING,
    REGISTRY_INDEX_MAPPING,
)

logger = logging.getLogger(__name__)


class ElasticsearchIndexManager:
    """Manages Elasticsearch indices for the ED Bot system."""
    
    def __init__(self, es_client: ElasticsearchClient, settings: Settings):
        self.es_client = es_client
        self.settings = settings
        self.index_prefix = settings.elasticsearch_index_prefix
        
    def get_index_names(self) -> Dict[str, str]:
        """Get the full index names for all indices."""
        return {
            'documents': f"{self.index_prefix}_documents",
            'chunks': f"{self.index_prefix}_chunks", 
            'registry': f"{self.index_prefix}_registry"
        }
        
    def create_indices(self) -> bool:
        """Create ES indices with proper mappings."""
        es = self.es_client.get_client()
        if not es:
            logger.warning("Elasticsearch client not available")
            return False
            
        index_names = self.get_index_names()
        indices_config = [
            (index_names['documents'], DOCUMENT_INDEX_MAPPING),
            (index_names['chunks'], CHUNK_INDEX_MAPPING),
            (index_names['registry'], REGISTRY_INDEX_MAPPING)
        ]
        
        success_count = 0
        for index_name, mapping in indices_config:
            try:
                if not es.indices.exists(index=index_name):
                    es.indices.create(index=index_name, body=mapping)
                    logger.info(f"Created index: {index_name}")
                    success_count += 1
                else:
                    # Update mapping if needed
                    try:
                        es.indices.put_mapping(index=index_name, body=mapping["mappings"])
                        logger.info(f"Updated mapping for existing index: {index_name}")
                        success_count += 1
                    except RequestError as e:
                        if "mapper_parsing_exception" in str(e):
                            logger.warning(f"Mapping update failed for {index_name}: {e}")
                            # Continue with existing mapping
                            success_count += 1
                        else:
                            raise
                            
            except Exception as e:
                logger.error(f"Failed to create/update index {index_name}: {e}")
                
        logger.info(f"Successfully processed {success_count}/{len(indices_config)} indices")
        return success_count == len(indices_config)
        
    def delete_indices(self, confirm: bool = False) -> bool:
        """Delete all ES indices (careful!)."""
        if not confirm:
            logger.warning("delete_indices called without confirmation - use confirm=True")
            return False
            
        es = self.es_client.get_client()
        if not es:
            logger.warning("Elasticsearch client not available")
            return False
            
        try:
            pattern = f"{self.index_prefix}_*"
            es.indices.delete(index=pattern, ignore_unavailable=True)
            logger.info(f"Deleted indices matching pattern: {pattern}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete indices: {e}")
            return False
            
    def get_index_stats(self) -> Dict[str, Dict]:
        """Get statistics for all indices."""
        es = self.es_client.get_client()
        if not es:
            return {}
            
        index_names = self.get_index_names()
        stats = {}
        
        for logical_name, index_name in index_names.items():
            try:
                if es.indices.exists(index=index_name):
                    # Get document count
                    count_result = es.count(index=index_name)
                    
                    # Get index size
                    stats_result = es.indices.stats(index=index_name)
                    index_stats = stats_result['indices'][index_name]
                    
                    stats[logical_name] = {
                        'index_name': index_name,
                        'document_count': count_result['count'],
                        'size_bytes': index_stats['total']['store']['size_in_bytes'],
                        'size_mb': round(index_stats['total']['store']['size_in_bytes'] / 1024 / 1024, 2)
                    }
                else:
                    stats[logical_name] = {
                        'index_name': index_name,
                        'exists': False
                    }
            except Exception as e:
                logger.error(f"Failed to get stats for {index_name}: {e}")
                stats[logical_name] = {
                    'index_name': index_name,
                    'error': str(e)
                }
                
        return stats
        
    def verify_indices_health(self) -> Dict[str, str]:
        """Verify health status of all indices."""
        es = self.es_client.get_client()
        if not es:
            return {'status': 'elasticsearch_unavailable'}
            
        index_names = self.get_index_names()
        health_status = {}
        
        try:
            cluster_health = es.cluster.health()
            health_status['cluster'] = cluster_health['status']
            
            for logical_name, index_name in index_names.items():
                if es.indices.exists(index=index_name):
                    index_health = es.cluster.health(index=index_name)
                    health_status[logical_name] = index_health['status']
                else:
                    health_status[logical_name] = 'missing'
                    
        except Exception as e:
            logger.error(f"Failed to check indices health: {e}")
            health_status['error'] = str(e)
            
        return health_status
        
    def reindex_from_alias(self, source_alias: str, dest_index: str) -> bool:
        """Reindex documents from an alias to a new index."""
        es = self.es_client.get_client()
        if not es:
            return False
            
        try:
            reindex_body = {
                "source": {"index": source_alias},
                "dest": {"index": dest_index}
            }
            
            result = es.reindex(body=reindex_body, wait_for_completion=True)
            
            if result.get('timed_out'):
                logger.warning(f"Reindex from {source_alias} to {dest_index} timed out")
                return False
                
            logger.info(f"Reindexed {result.get('total', 0)} documents from {source_alias} to {dest_index}")
            return True
            
        except Exception as e:
            logger.error(f"Reindex failed: {e}")
            return False
            
    def optimize_indices(self) -> bool:
        """Optimize indices for better search performance."""
        es = self.es_client.get_client()
        if not es:
            return False
            
        index_names = self.get_index_names()
        
        try:
            for logical_name, index_name in index_names.items():
                if es.indices.exists(index=index_name):
                    # Force merge to optimize segments
                    es.indices.forcemerge(index=index_name, max_num_segments=1)
                    logger.info(f"Optimized index: {index_name}")
                    
            return True
            
        except Exception as e:
            logger.error(f"Failed to optimize indices: {e}")
            return False