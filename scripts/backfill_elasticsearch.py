#!/usr/bin/env python3
"""
Backfill existing documents from PostgreSQL to Elasticsearch.
This script handles migrating existing documents when enabling hybrid search.
"""

import argparse
import asyncio
import hashlib
import os
import sys
from typing import Dict, Optional

from elasticsearch.helpers import bulk
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.config.settings import get_settings
from src.models.entities import Document, DocumentChunk, DocumentRegistry
from src.search.elasticsearch_client import ElasticsearchClient
from src.search.es_index_manager import ElasticsearchIndexManager
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ElasticsearchBackfiller:
    """Handles backfilling existing PostgreSQL documents to Elasticsearch."""
    
    def __init__(self, dry_run: bool = True):
        self.settings = get_settings()
        self.dry_run = dry_run
        
        # Database setup
        self.engine = create_engine(self.settings.database_url)
        self.SessionLocal = sessionmaker(bind=self.engine)
        
        # Elasticsearch setup
        self.es_client = ElasticsearchClient(self.settings)
        if not self.es_client.is_available():
            raise RuntimeError("Elasticsearch is not available. Please start ES service first.")
            
        self.index_manager = ElasticsearchIndexManager(self.es_client, self.settings)
        
    async def backfill_all(self) -> Dict[str, int]:
        """Backfill all documents, chunks, and registry entries."""
        logger.info("Starting Elasticsearch backfill process")
        
        if self.dry_run:
            logger.info("DRY RUN MODE - No changes will be made to Elasticsearch")
        
        # Ensure indices exist
        if not self.dry_run:
            self.index_manager.create_indices()
        
        # Get database counts
        with self.SessionLocal() as session:
            doc_count = session.scalar(select(func.count(Document.id)))
            chunk_count = session.scalar(select(func.count(DocumentChunk.id)))
            registry_count = session.scalar(select(func.count(DocumentRegistry.id)))
            
        logger.info(f"Found {doc_count} documents, {chunk_count} chunks, {registry_count} registry entries to backfill")
        
        if doc_count == 0:
            logger.warning("No documents found in database")
            return {"documents": 0, "chunks": 0, "registry": 0}
        
        # Backfill in batches
        results = {
            "documents": await self._backfill_documents(),
            "chunks": await self._backfill_chunks(),
            "registry": await self._backfill_registry()
        }
        
        # Verify counts if not dry run
        if not self.dry_run:
            await self._verify_counts()
            
        return results
        
    async def _backfill_documents(self) -> int:
        """Backfill documents to Elasticsearch."""
        logger.info("Backfilling documents...")
        
        batch_size = 100
        total_processed = 0
        
        with self.SessionLocal() as session:
            # Get total count for progress tracking
            total_docs = session.scalar(select(func.count(Document.id)))
            
            for offset in range(0, total_docs, batch_size):
                docs = session.execute(
                    select(Document).offset(offset).limit(batch_size)
                ).scalars().all()
                
                operations = []
                for doc in docs:
                    doc_id = hashlib.md5(f"{doc.id}".encode()).hexdigest()
                    doc_source = {
                        "id": str(doc.id),
                        "content": doc.content[:10000] if doc.content else "",
                        "content_type": doc.content_type,
                        "filename": doc.filename,
                        "title": doc.meta.get("title", doc.filename),
                        "protocol_name": self._extract_protocol_name(doc),
                        "form_name": self._extract_form_name(doc),
                        "medical_specialties": doc.meta.get("medical_specialties", []),
                        "tags": doc.meta.get("tags", []),
                        "file_type": doc.file_type,
                        "file_hash": doc.file_hash,
                        "metadata": doc.meta,
                        "created_at": doc.created_at.isoformat(),
                        "updated_at": doc.updated_at.isoformat()
                    }
                    
                    operations.append({
                        "_index": f"{self.settings.elasticsearch_index_prefix}_documents",
                        "_id": doc_id,
                        "_source": doc_source
                    })
                    
                if not self.dry_run and operations:
                    es = self.es_client.get_client()
                    success, failed = bulk(es, operations, chunk_size=50, raise_on_error=False)
                    if failed:
                        logger.error(f"Failed to index {len(failed)} documents")
                    total_processed += success
                else:
                    total_processed += len(operations)
                    
                logger.info(f"Processed {total_processed}/{total_docs} documents")
                
        return total_processed
        
    async def _backfill_chunks(self) -> int:
        """Backfill chunks to Elasticsearch."""
        logger.info("Backfilling chunks...")
        
        batch_size = 200
        total_processed = 0
        
        with self.SessionLocal() as session:
            total_chunks = session.scalar(select(func.count(DocumentChunk.id)))
            
            for offset in range(0, total_chunks, batch_size):
                chunks = session.execute(
                    select(DocumentChunk).offset(offset).limit(batch_size)
                ).scalars().all()
                
                operations = []
                for chunk in chunks:
                    chunk_id = hashlib.md5(f"{chunk.id}".encode()).hexdigest()
                    chunk_source = {
                        "id": str(chunk.id),
                        "document_id": str(chunk.document_id),
                        "content": chunk.chunk_text,
                        "chunk_index": chunk.chunk_index,
                        "chunk_type": chunk.chunk_type,
                        "medical_category": chunk.medical_category,
                        "urgency_level": chunk.urgency_level,
                        "contains_contact": chunk.contains_contact,
                        "contains_dosage": chunk.contains_dosage,
                        "page_number": chunk.page_number,
                        "metadata": chunk.meta,
                        "created_at": chunk.created_at.isoformat()
                    }
                    
                    operations.append({
                        "_index": f"{self.settings.elasticsearch_index_prefix}_chunks",
                        "_id": chunk_id,
                        "_source": chunk_source
                    })
                    
                if not self.dry_run and operations:
                    es = self.es_client.get_client()
                    success, failed = bulk(es, operations, chunk_size=100, raise_on_error=False)
                    if failed:
                        logger.error(f"Failed to index {len(failed)} chunks")
                    total_processed += success
                else:
                    total_processed += len(operations)
                    
                logger.info(f"Processed {total_processed}/{total_chunks} chunks")
                
        return total_processed
        
    async def _backfill_registry(self) -> int:
        """Backfill registry entries to Elasticsearch."""
        logger.info("Backfilling registry entries...")
        
        batch_size = 100
        total_processed = 0
        
        with self.SessionLocal() as session:
            total_registry = session.scalar(select(func.count(DocumentRegistry.id)))
            
            for offset in range(0, total_registry, batch_size):
                registry_entries = session.execute(
                    select(DocumentRegistry).offset(offset).limit(batch_size)
                ).scalars().all()
                
                operations = []
                for registry in registry_entries:
                    registry_id = hashlib.md5(f"{registry.id}".encode()).hexdigest()
                    registry_source = {
                        "id": str(registry.id),
                        "document_id": str(registry.document_id),
                        "keywords": registry.keywords,
                        "display_name": registry.display_name,
                        "file_path": registry.file_path,
                        "category": registry.category,
                        "priority": registry.priority,
                        "quick_access": registry.quick_access,
                        "metadata": registry.meta
                    }
                    
                    operations.append({
                        "_index": f"{self.settings.elasticsearch_index_prefix}_registry",
                        "_id": registry_id,
                        "_source": registry_source
                    })
                    
                if not self.dry_run and operations:
                    es = self.es_client.get_client()
                    success, failed = bulk(es, operations, chunk_size=50, raise_on_error=False)
                    if failed:
                        logger.error(f"Failed to index {len(failed)} registry entries")
                    total_processed += success
                else:
                    total_processed += len(operations)
                    
                logger.info(f"Processed {total_processed}/{total_registry} registry entries")
                
        return total_processed
        
    async def _verify_counts(self):
        """Verify that ES counts match database counts."""
        logger.info("Verifying document counts...")
        
        # Get database counts
        with self.SessionLocal() as session:
            db_doc_count = session.scalar(select(func.count(Document.id)))
            db_chunk_count = session.scalar(select(func.count(DocumentChunk.id)))
            db_registry_count = session.scalar(select(func.count(DocumentRegistry.id)))
        
        # Get Elasticsearch counts
        es = self.es_client.get_client()
        es_doc_count = es.count(index=f"{self.settings.elasticsearch_index_prefix}_documents")["count"]
        es_chunk_count = es.count(index=f"{self.settings.elasticsearch_index_prefix}_chunks")["count"]
        es_registry_count = es.count(index=f"{self.settings.elasticsearch_index_prefix}_registry")["count"]
        
        # Calculate match rates
        doc_match_rate = (es_doc_count / db_doc_count * 100) if db_doc_count > 0 else 0
        chunk_match_rate = (es_chunk_count / db_chunk_count * 100) if db_chunk_count > 0 else 0
        registry_match_rate = (es_registry_count / db_registry_count * 100) if db_registry_count > 0 else 0
        
        logger.info("Count verification results:")
        logger.info(f"Documents - DB: {db_doc_count}, ES: {es_doc_count}, Match: {doc_match_rate:.1f}%")
        logger.info(f"Chunks - DB: {db_chunk_count}, ES: {es_chunk_count}, Match: {chunk_match_rate:.1f}%")
        logger.info(f"Registry - DB: {db_registry_count}, ES: {es_registry_count}, Match: {registry_match_rate:.1f}%")
        
        # Warn if match rates are low
        if any(rate < 95.0 for rate in [doc_match_rate, chunk_match_rate, registry_match_rate]):
            logger.warning("Some indices have low match rates. Consider re-running backfill.")
            
    def _extract_protocol_name(self, document: Document) -> Optional[str]:
        """Extract protocol name from document for exact matching."""
        if document.content_type == "protocol":
            title = document.meta.get("title", "").lower()
            filename = document.filename.lower()
            
            protocol_keywords = ["protocol", "pathway", "algorithm", "guideline"]
            for content in [title, filename]:
                if any(keyword in content for keyword in protocol_keywords):
                    name = content.replace(".pdf", "").replace("_", " ").strip()
                    return name
        return None
        
    def _extract_form_name(self, document: Document) -> Optional[str]:
        """Extract form name from document for exact matching."""
        if document.content_type == "form":
            title = document.meta.get("title", "").lower()
            filename = document.filename.lower()
            
            form_keywords = ["form", "consent", "checklist", "template"]
            for content in [title, filename]:
                if any(keyword in content for keyword in form_keywords):
                    name = content.replace(".pdf", "").replace("_", " ").strip()
                    return name
        return None


async def main():
    """Main entry point for backfill script."""
    parser = argparse.ArgumentParser(description="Backfill PostgreSQL documents to Elasticsearch")
    parser.add_argument("--execute", action="store_true", 
                      help="Actually perform backfill (default is dry run)")
    parser.add_argument("--force", action="store_true",
                      help="Force backfill even if indices already exist")
    
    args = parser.parse_args()
    
    try:
        backfiller = ElasticsearchBackfiller(dry_run=not args.execute)
        results = await backfiller.backfill_all()
        
        print("\n" + "="*50)
        print("BACKFILL RESULTS")
        print("="*50)
        print(f"Documents indexed: {results['documents']}")
        print(f"Chunks indexed: {results['chunks']}")
        print(f"Registry entries indexed: {results['registry']}")
        print(f"Total items indexed: {sum(results.values())}")
        
        if not args.execute:
            print("\nThis was a DRY RUN. Use --execute to actually perform the backfill.")
        else:
            print("\nBackfill completed successfully!")
            
    except Exception as e:
        logger.error(f"Backfill failed: {e}")
        print(f"ERROR: {e}")
        return 1
        
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))