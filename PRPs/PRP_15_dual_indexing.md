# PRP 15: Dual Indexing During Ingestion

## Problem Statement
When hybrid search is enabled, documents need to be indexed in both PostgreSQL (with pgvector embeddings) and Elasticsearch. The ingestion pipeline must support dual indexing while maintaining backward compatibility with pgvector-only mode.

## Success Criteria
- Documents/chunks indexed in both ES and PostgreSQL when hybrid mode enabled
- ES index mappings optimized for medical terminology and exact matches
- Backfill script available for existing documents
- Counts in ES match DB doc/chunk counts within tolerance
- No performance regression in pgvector-only mode

## Implementation Approach

### 1. Elasticsearch Index Templates
```python
# src/search/es_mappings.py
DOCUMENT_INDEX_MAPPING = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "analysis": {
            "analyzer": {
                "medical_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "medical_synonyms", "stop"]
                }
            },
            "filter": {
                "medical_synonyms": {
                    "type": "synonym",
                    "synonyms": [
                        "MI,myocardial infarction,heart attack",
                        "STEMI,ST elevation myocardial infarction",
                        "ED,emergency department,ER",
                        "BP,blood pressure",
                        "HR,heart rate"
                    ]
                }
            }
        }
    },
    "mappings": {
        "properties": {
            "id": {"type": "keyword"},
            "content": {
                "type": "text",
                "analyzer": "medical_analyzer",
                "fields": {
                    "keyword": {"type": "keyword"},
                    "exact": {"type": "text", "analyzer": "standard"}
                }
            },
            "content_type": {"type": "keyword"},
            "filename": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword"}}
            },
            "title": {
                "type": "text",
                "analyzer": "medical_analyzer",
                "fields": {"keyword": {"type": "keyword"}}
            },
            "protocol_name": {"type": "keyword"},  # For exact protocol matching
            "form_name": {"type": "keyword"},      # For exact form matching
            "chunk_index": {"type": "integer"},
            "page_number": {"type": "integer"},
            "metadata": {"type": "object", "enabled": False},
            "created_at": {"type": "date"},
            "updated_at": {"type": "date"}
        }
    }
}
```

### 2. Enhanced Ingestion Task
```python
# src/ingestion/tasks.py
from src.search.elasticsearch_client import ElasticsearchClient
from elasticsearch.helpers import bulk
import hashlib

class DocumentIngestionTask:
    def __init__(self, db_session, settings, es_client: Optional[ElasticsearchClient] = None):
        self.db_session = db_session
        self.settings = settings
        self.es_client = es_client
        self.dual_index = es_client and es_client.enabled
        
    async def ingest_document(self, file_path: str, content_type: str):
        """Ingest document with dual indexing support"""
        # Existing pgvector ingestion
        document = await self._process_document(file_path, content_type)
        chunks = await self._create_chunks(document)
        embeddings = await self._generate_embeddings(chunks)
        
        # Store in PostgreSQL (existing flow)
        db_doc = await self._store_in_postgres(document, chunks, embeddings)
        
        # Dual index to Elasticsearch if enabled
        if self.dual_index:
            await self._index_to_elasticsearch(db_doc, chunks)
            
        return db_doc
        
    async def _index_to_elasticsearch(self, document, chunks):
        """Index document and chunks to Elasticsearch"""
        es = self.es_client.get_client()
        if not es:
            logger.warning("ES client unavailable, skipping ES indexing")
            return
            
        try:
            # Prepare bulk index operations
            operations = []
            
            # Index document
            doc_id = hashlib.md5(f"{document.id}".encode()).hexdigest()
            operations.append({
                "_index": f"{self.settings.elasticsearch_index_prefix}_documents",
                "_id": doc_id,
                "_source": {
                    "id": str(document.id),
                    "content": document.content[:10000],  # Limit for ES
                    "content_type": document.content_type,
                    "filename": document.filename,
                    "title": document.meta.get("title", document.filename),
                    "protocol_name": document.meta.get("protocol_name"),
                    "form_name": document.meta.get("form_name"),
                    "metadata": document.meta,
                    "created_at": document.created_at.isoformat(),
                    "updated_at": document.updated_at.isoformat()
                }
            })
            
            # Index chunks
            for chunk in chunks:
                chunk_id = hashlib.md5(f"{chunk.id}".encode()).hexdigest()
                operations.append({
                    "_index": f"{self.settings.elasticsearch_index_prefix}_chunks",
                    "_id": chunk_id,
                    "_source": {
                        "id": str(chunk.id),
                        "document_id": str(document.id),
                        "content": chunk.content,
                        "chunk_index": chunk.chunk_index,
                        "page_number": chunk.meta.get("page_number"),
                        "metadata": chunk.meta,
                        "created_at": chunk.created_at.isoformat()
                    }
                })
                
            # Bulk index
            success, failed = bulk(es, operations, raise_on_error=False)
            if failed:
                logger.error(f"Failed to index {len(failed)} items to ES")
            else:
                logger.info(f"Indexed {success} items to Elasticsearch")
                
        except Exception as e:
            logger.error(f"ES indexing failed: {e}")
            # Don't fail the entire ingestion if ES fails
```

### 3. Index Management
```python
# src/search/es_index_manager.py
class ElasticsearchIndexManager:
    def __init__(self, es_client: ElasticsearchClient, settings: Settings):
        self.es_client = es_client
        self.settings = settings
        
    def create_indices(self):
        """Create ES indices with proper mappings"""
        es = self.es_client.get_client()
        if not es:
            return
            
        indices = [
            (f"{self.settings.elasticsearch_index_prefix}_documents", DOCUMENT_INDEX_MAPPING),
            (f"{self.settings.elasticsearch_index_prefix}_chunks", CHUNK_INDEX_MAPPING)
        ]
        
        for index_name, mapping in indices:
            if not es.indices.exists(index=index_name):
                es.indices.create(index=index_name, body=mapping)
                logger.info(f"Created index: {index_name}")
            else:
                # Update mapping if needed
                es.indices.put_mapping(index=index_name, body=mapping["mappings"])
                
    def delete_indices(self):
        """Delete all ES indices (careful!)"""
        es = self.es_client.get_client()
        if es:
            pattern = f"{self.settings.elasticsearch_index_prefix}_*"
            es.indices.delete(index=pattern, ignore_unavailable=True)
```

### 4. Backfill Script
```python
# scripts/backfill_elasticsearch.py
import asyncio
from sqlalchemy import select
from src.models.entities import Document, DocumentChunk
from src.search.elasticsearch_client import ElasticsearchClient
from elasticsearch.helpers import bulk

async def backfill_to_elasticsearch(dry_run: bool = True):
    """Backfill existing documents to Elasticsearch"""
    
    # Initialize connections
    db_session = get_db_session()
    es_client = ElasticsearchClient(settings)
    es = es_client.get_client()
    
    if not es:
        print("Elasticsearch not available")
        return
        
    # Get counts
    doc_count = db_session.scalar(select(func.count(Document.id)))
    chunk_count = db_session.scalar(select(func.count(DocumentChunk.id)))
    
    print(f"Found {doc_count} documents and {chunk_count} chunks to backfill")
    
    if dry_run:
        print("DRY RUN - no changes will be made")
        return
        
    # Backfill in batches
    batch_size = 100
    operations = []
    
    # Process documents
    for offset in range(0, doc_count, batch_size):
        docs = db_session.execute(
            select(Document).offset(offset).limit(batch_size)
        ).scalars().all()
        
        for doc in docs:
            operations.append({
                "_index": f"{settings.elasticsearch_index_prefix}_documents",
                "_id": hashlib.md5(f"{doc.id}".encode()).hexdigest(),
                "_source": document_to_es_format(doc)
            })
            
    # Process chunks similarly
    # ...
    
    # Bulk index
    success, failed = bulk(es, operations, chunk_size=500, raise_on_error=False)
    print(f"Indexed {success} items, {len(failed)} failures")
    
    # Verify counts
    es_doc_count = es.count(index=f"{settings.elasticsearch_index_prefix}_documents")["count"]
    es_chunk_count = es.count(index=f"{settings.elasticsearch_index_prefix}_chunks")["count"]
    
    print(f"ES counts - Documents: {es_doc_count}, Chunks: {es_chunk_count}")
    print(f"Match rate - Documents: {es_doc_count/doc_count*100:.1f}%, Chunks: {es_chunk_count/chunk_count*100:.1f}%")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="Actually perform backfill")
    args = parser.parse_args()
    
    asyncio.run(backfill_to_elasticsearch(dry_run=not args.execute))
```

### 5. Makefile Targets
```makefile
# Makefile.v8
es-setup:  ## Create Elasticsearch indices with mappings
	python -m scripts.es_index_manager create

es-backfill:  ## Backfill existing documents to Elasticsearch
	python -m scripts.backfill_elasticsearch --execute

es-verify:  ## Verify ES and DB counts match
	@echo "Database counts:"
	@docker compose exec db psql -U edbot -d edbot_v8 -c "SELECT 'documents' as type, COUNT(*) FROM documents UNION SELECT 'chunks', COUNT(*) FROM document_chunks;"
	@echo "\nElasticsearch counts:"
	@curl -s "http://localhost:9200/edbot_*/_count" | jq '.count'
```

## Testing Strategy
```python
# tests/integration/test_dual_indexing.py
async def test_dual_indexing_enabled():
    """Test that documents are indexed in both stores"""
    settings.search_backend = "hybrid"
    
    # Ingest a document
    doc = await ingest_document("test.pdf", "protocol")
    
    # Verify in PostgreSQL
    db_doc = db_session.get(Document, doc.id)
    assert db_doc is not None
    
    # Verify in Elasticsearch
    es_doc = es.get(index="edbot_documents", id=hashlib.md5(f"{doc.id}".encode()).hexdigest())
    assert es_doc["_source"]["id"] == str(doc.id)
    
async def test_es_failure_doesnt_block():
    """Test that ES failure doesn't prevent PostgreSQL storage"""
    # Simulate ES being down
    es_client.enabled = False
    
    # Should still succeed
    doc = await ingest_document("test.pdf", "protocol")
    assert doc is not None
```

## Rollback Plan
1. Stop dual indexing: Set `SEARCH_BACKEND=pgvector`
2. Delete ES indices if needed: `make es-delete`
3. System continues with pgvector-only
4. No data loss as PostgreSQL remains source of truth

## Performance Considerations
- Async bulk indexing to minimize latency
- Batch operations for backfill
- ES indexing failures don't block primary flow
- Monitor indexing lag with metrics