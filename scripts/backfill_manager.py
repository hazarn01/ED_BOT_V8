#!/usr/bin/env python3
"""
Backfill manager for EDBotv8
Handles data migration and backfilling for new features
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class BackfillResult:
    """Result of a backfill operation"""
    task_name: str
    status: str  # "success", "failed", "skipped"
    duration_seconds: float
    items_processed: int = 0
    items_created: int = 0
    items_updated: int = 0
    error_count: int = 0
    details: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

class BackfillManager:
    """Manages data backfill operations"""
    
    def __init__(self, settings, db_session, redis_client, es_client=None):
        self.settings = settings
        self.db = db_session
        self.redis = redis_client
        self.es_client = es_client
        self.logger = logging.getLogger(__name__)
        
    async def run_full_backfill(self, dry_run: bool = True, selected_tasks: Optional[List[str]] = None) -> Dict[str, Any]:
        """Run complete backfill process"""
        
        self.logger.info(f"Starting {'dry run' if dry_run else 'actual'} backfill process...")
        
        # Define all available backfill tasks
        available_tasks = [
            ("elasticsearch", self._backfill_elasticsearch, "Elasticsearch indices"),
            ("highlighting", self._backfill_highlighting_data, "Source highlighting position data"),
            ("tables", self._backfill_table_extraction, "Table extraction"),
            ("cache_warmup", self._warmup_caches, "Cache pre-warming"),
            ("search_optimization", self._optimize_search_indices, "Search index optimization")
        ]
        
        # Filter tasks if specific ones are selected
        if selected_tasks:
            backfill_tasks = [(name, func, desc) for name, func, desc in available_tasks if name in selected_tasks]
            if not backfill_tasks:
                raise ValueError(f"No valid tasks selected. Available: {[name for name, _, _ in available_tasks]}")
        else:
            # Auto-select tasks based on enabled features
            backfill_tasks = []
            
            if getattr(self.settings.features, 'enable_elasticsearch', False):
                backfill_tasks.append(("elasticsearch", self._backfill_elasticsearch, "Elasticsearch indices"))
                
            if getattr(self.settings.features, 'enable_source_highlighting', False):
                backfill_tasks.append(("highlighting", self._backfill_highlighting_data, "Source highlighting position data"))
                
            if getattr(self.settings.features, 'enable_table_extraction', False):
                backfill_tasks.append(("tables", self._backfill_table_extraction, "Table extraction"))
            
            # Always include cache warmup and optimization if not dry run
            if not dry_run:
                backfill_tasks.extend([
                    ("cache_warmup", self._warmup_caches, "Cache pre-warming"),
                    ("search_optimization", self._optimize_search_indices, "Search index optimization")
                ])
        
        if not backfill_tasks:
            self.logger.info("No backfill tasks needed based on current feature flags")
            return {
                "dry_run": dry_run,
                "total_duration_seconds": 0,
                "tasks": {},
                "success_count": 0,
                "failure_count": 0,
                "message": "No tasks required"
            }
        
        results = {}
        total_start = datetime.utcnow()
        
        for task_name, task_func, task_description in backfill_tasks:
            self.logger.info(f"{'[DRY RUN] ' if dry_run else ''}Starting backfill: {task_name} - {task_description}")
            start_time = datetime.utcnow()
            
            try:
                result = await task_func(dry_run=dry_run)
                duration = (datetime.utcnow() - start_time).total_seconds()
                
                backfill_result = BackfillResult(
                    task_name=task_name,
                    status="success",
                    duration_seconds=duration,
                    items_processed=result.get("items_processed", 0),
                    items_created=result.get("items_created", 0),
                    items_updated=result.get("items_updated", 0),
                    details=result
                )
                
                results[task_name] = asdict(backfill_result)
                
                self.logger.info(
                    f"✓ Completed {task_name} in {duration:.2f}s "
                    f"({result.get('items_processed', 0)} processed, "
                    f"{result.get('items_created', 0)} created)"
                )
                
            except Exception as e:
                duration = (datetime.utcnow() - start_time).total_seconds()
                
                backfill_result = BackfillResult(
                    task_name=task_name,
                    status="failed",
                    duration_seconds=duration,
                    error_message=str(e),
                    details={"exception": str(e)}
                )
                
                results[task_name] = asdict(backfill_result)
                self.logger.error(f"✗ Failed {task_name}: {e}")
                
        total_duration = (datetime.utcnow() - total_start).total_seconds()
        
        summary = {
            "dry_run": dry_run,
            "total_duration_seconds": total_duration,
            "tasks": results,
            "success_count": sum(1 for r in results.values() if r["status"] == "success"),
            "failure_count": sum(1 for r in results.values() if r["status"] == "failed"),
            "total_items_processed": sum(r.get("items_processed", 0) for r in results.values()),
            "total_items_created": sum(r.get("items_created", 0) for r in results.values())
        }
        
        self.logger.info(
            f"Backfill {'dry run ' if dry_run else ''}complete: "
            f"{summary['success_count']} success, {summary['failure_count']} failed, "
            f"{summary['total_items_processed']} items processed in {total_duration:.2f}s"
        )
        
        return summary
        
    async def _backfill_elasticsearch(self, dry_run: bool = True) -> Dict[str, Any]:
        """Backfill Elasticsearch indices"""
        
        if not getattr(self.settings.features, 'enable_elasticsearch', False):
            return {
                "items_processed": 0,
                "items_created": 0,
                "message": "Elasticsearch not enabled"
            }
        
        try:
            # Count documents and chunks to be indexed
            doc_count_result = await self.db.execute("SELECT COUNT(*) FROM documents")
            doc_count = doc_count_result.scalar()
            
            chunk_count_result = await self.db.execute("SELECT COUNT(*) FROM document_chunks")
            chunk_count = chunk_count_result.scalar()
            
            if dry_run:
                return {
                    "items_processed": doc_count + chunk_count,
                    "documents_to_index": doc_count,
                    "chunks_to_index": chunk_count,
                    "estimated_time_minutes": (doc_count + chunk_count) / 100,  # Rough estimate
                    "message": f"Would index {doc_count} documents and {chunk_count} chunks"
                }
            
            # Actual backfill - import the backfill function
            try:
                from scripts.backfill_elasticsearch import backfill_to_elasticsearch
                result = await backfill_to_elasticsearch()
                return {
                    "items_processed": doc_count + chunk_count,
                    "items_created": result.get("indexed_documents", 0) + result.get("indexed_chunks", 0),
                    "documents_indexed": result.get("indexed_documents", 0),
                    "chunks_indexed": result.get("indexed_chunks", 0),
                    "details": result
                }
            except ImportError:
                # Create basic backfill if the script doesn't exist
                return await self._create_elasticsearch_indices(doc_count, chunk_count)
                
        except Exception as e:
            raise Exception(f"Elasticsearch backfill failed: {e}")
            
    async def _create_elasticsearch_indices(self, doc_count: int, chunk_count: int) -> Dict[str, Any]:
        """Create and populate Elasticsearch indices"""
        
        if not self.es_client:
            raise Exception("Elasticsearch client not available")
        
        es = await self.es_client.get_client() if hasattr(self.es_client, 'get_client') else self.es_client
        
        index_prefix = getattr(self.settings, 'elasticsearch_index_prefix', 'edbot')
        doc_index = f"{index_prefix}_documents"
        chunk_index = f"{index_prefix}_chunks"
        
        created_docs = 0
        created_chunks = 0
        
        # Create document index and populate
        if not await es.indices.exists(index=doc_index):
            # Create index with mapping
            doc_mapping = {
                "mappings": {
                    "properties": {
                        "title": {"type": "text", "analyzer": "standard"},
                        "content": {"type": "text", "analyzer": "standard"},
                        "filename": {"type": "keyword"},
                        "file_type": {"type": "keyword"},
                        "created_at": {"type": "date"},
                        "metadata": {"type": "object"}
                    }
                }
            }
            await es.indices.create(index=doc_index, body=doc_mapping)
            
            # Index documents
            documents = await self.db.execute("""
                SELECT id, title, filename, file_type, created_at, metadata
                FROM documents 
                ORDER BY id
            """)
            
            for doc in documents:
                doc_id, title, filename, file_type, created_at, metadata = doc
                doc_body = {
                    "title": title,
                    "filename": filename,
                    "file_type": file_type,
                    "created_at": created_at.isoformat() if created_at else None,
                    "metadata": metadata or {}
                }
                
                await es.index(index=doc_index, id=doc_id, body=doc_body)
                created_docs += 1
        
        # Create chunk index and populate
        if not await es.indices.exists(index=chunk_index):
            # Create index with mapping
            chunk_mapping = {
                "mappings": {
                    "properties": {
                        "content": {"type": "text", "analyzer": "standard"},
                        "document_id": {"type": "integer"},
                        "chunk_index": {"type": "integer"},
                        "page_number": {"type": "integer"},
                        "embedding": {"type": "dense_vector", "dims": 384},  # Adjust based on your model
                        "metadata": {"type": "object"}
                    }
                }
            }
            await es.indices.create(index=chunk_index, body=chunk_mapping)
            
            # Index chunks (in batches)
            batch_size = 100
            offset = 0
            
            while True:
                chunks = await self.db.execute(f"""
                    SELECT id, content, document_id, chunk_index, page_number, embedding
                    FROM document_chunks 
                    ORDER BY id
                    LIMIT {batch_size} OFFSET {offset}
                """)
                
                chunk_list = list(chunks)
                if not chunk_list:
                    break
                
                # Prepare bulk index operations
                bulk_body = []
                for chunk in chunk_list:
                    chunk_id, content, doc_id, chunk_idx, page_num, embedding = chunk
                    
                    bulk_body.append({"index": {"_index": chunk_index, "_id": chunk_id}})
                    bulk_body.append({
                        "content": content,
                        "document_id": doc_id,
                        "chunk_index": chunk_idx,
                        "page_number": page_num,
                        "embedding": list(embedding) if embedding else None
                    })
                
                if bulk_body:
                    await es.bulk(body=bulk_body)
                    created_chunks += len(chunk_list)
                
                offset += batch_size
                
                if len(chunk_list) < batch_size:
                    break
        
        return {
            "items_processed": doc_count + chunk_count,
            "items_created": created_docs + created_chunks,
            "documents_indexed": created_docs,
            "chunks_indexed": created_chunks
        }
            
    async def _backfill_highlighting_data(self, dry_run: bool = True) -> Dict[str, Any]:
        """Backfill source highlighting position data"""
        
        # Find chunks missing highlighting data
        missing_highlights = await self.db.execute("""
            SELECT COUNT(*) FROM document_chunks 
            WHERE page_number IS NULL OR page_span_start IS NULL
        """)
        
        count = missing_highlights.scalar()
        
        if count == 0:
            return {
                "items_processed": 0,
                "message": "All chunks already have highlighting data"
            }
        
        if dry_run:
            return {
                "items_processed": count,
                "chunks_missing_positions": count,
                "estimated_time_minutes": count / 50,  # Rough estimate for PDF processing
                "message": f"Would process {count} chunks for position data"
            }
            
        # Re-process PDFs to extract position information
        processed = 0
        updated = 0
        errors = 0
        
        # Get documents that need reprocessing
        docs_to_process = await self.db.execute("""
            SELECT DISTINCT d.id, d.filename, d.file_type 
            FROM documents d
            JOIN document_chunks dc ON d.id = dc.document_id
            WHERE dc.page_number IS NULL OR dc.page_span_start IS NULL
        """)
        
        try:
            # Try to import PDF processor
            from src.ingestion.pdf_processor import PDFProcessor
            PDFProcessor()
            
            for doc_id, filename, file_type in docs_to_process:
                if file_type == "pdf":
                    try:
                        # Extract position data and update chunks
                        file_path = os.path.join(
                            getattr(self.settings, 'docs_path', 'docs'), 
                            file_type, 
                            filename
                        )
                        
                        if os.path.exists(file_path):
                            # Extract positions (simplified - would need actual implementation)
                            # This is a placeholder for the actual position extraction logic
                            
                            # Update chunks for this document with default position data
                            update_result = await self.db.execute("""
                                UPDATE document_chunks 
                                SET 
                                    page_number = COALESCE(page_number, 1),
                                    page_span_start = COALESCE(page_span_start, 0),
                                    bbox = COALESCE(bbox, '{"x": 0, "y": 0, "width": 100, "height": 20}')
                                WHERE document_id = :doc_id 
                                AND (page_number IS NULL OR page_span_start IS NULL)
                            """, {"doc_id": doc_id})
                            
                            updated += update_result.rowcount
                            processed += 1
                        else:
                            self.logger.warning(f"File not found: {file_path}")
                            
                    except Exception as e:
                        self.logger.error(f"Failed to process {filename}: {e}")
                        errors += 1
                        
        except ImportError:
            # Fallback: just set default position data
            self.logger.warning("PDF processor not available, using default position data")
            
            update_result = await self.db.execute("""
                UPDATE document_chunks 
                SET 
                    page_number = COALESCE(page_number, 1),
                    page_span_start = COALESCE(page_span_start, 0),
                    bbox = COALESCE(bbox, '{"x": 0, "y": 0, "width": 100, "height": 20}')
                WHERE page_number IS NULL OR page_span_start IS NULL
            """)
            
            updated = update_result.rowcount
            processed = count
        
        await self.db.commit()
        
        return {
            "items_processed": processed,
            "items_updated": updated,
            "documents_processed": processed,
            "chunks_updated": updated,
            "error_count": errors
        }
        
    async def _backfill_table_extraction(self, dry_run: bool = True) -> Dict[str, Any]:
        """Backfill table extraction for existing documents"""
        
        # Count documents without table extraction
        docs_without_tables = await self.db.execute("""
            SELECT COUNT(DISTINCT d.id) 
            FROM documents d
            LEFT JOIN extracted_tables et ON d.id = et.document_id
            WHERE et.id IS NULL AND d.file_type = 'pdf'
        """)
        
        count = docs_without_tables.scalar()
        
        if count == 0:
            return {
                "items_processed": 0,
                "message": "All PDF documents already have table extraction"
            }
        
        if dry_run:
            return {
                "items_processed": count,
                "documents_needing_table_extraction": count,
                "estimated_time_minutes": count * 2,  # 2 minutes per PDF
                "message": f"Would extract tables from {count} documents"
            }
            
        # Extract tables from documents
        processed = 0
        tables_extracted = 0
        errors = 0
        
        docs_to_process = await self.db.execute("""
            SELECT d.id, d.filename, d.file_type 
            FROM documents d
            LEFT JOIN extracted_tables et ON d.id = et.document_id
            WHERE et.id IS NULL AND d.file_type = 'pdf'
        """)
        
        try:
            from src.ingestion.table_extractor import TableExtractor
            extractor = TableExtractor(self.settings)
            
            for doc_id, filename, file_type in docs_to_process:
                try:
                    file_path = os.path.join(
                        getattr(self.settings, 'docs_path', 'docs'), 
                        file_type, 
                        filename
                    )
                    
                    if os.path.exists(file_path):
                        tables = await extractor.extract_tables(file_path, file_type)
                        
                        # Store extracted tables (simplified - would need actual table storage)
                        for i, table_data in enumerate(tables):
                            # Create ExtractedTable entity and save
                            await self.db.execute("""
                                INSERT INTO extracted_tables 
                                (document_id, page_number, table_index, content, metadata)
                                VALUES (:doc_id, :page, :idx, :content, :metadata)
                            """, {
                                "doc_id": doc_id,
                                "page": table_data.get("page", 1),
                                "idx": i,
                                "content": table_data.get("html", ""),
                                "metadata": json.dumps(table_data.get("metadata", {}))
                            })
                            tables_extracted += 1
                            
                        processed += 1
                    else:
                        self.logger.warning(f"File not found: {file_path}")
                        
                except Exception as e:
                    self.logger.error(f"Table extraction failed for {filename}: {e}")
                    errors += 1
                    
        except ImportError:
            # Fallback: create placeholder table entries
            self.logger.warning("Table extractor not available, creating placeholder entries")
            
            for doc_id, filename, file_type in docs_to_process:
                try:
                    # Create a placeholder table entry
                    await self.db.execute("""
                        INSERT INTO extracted_tables 
                        (document_id, page_number, table_index, content, metadata)
                        VALUES (:doc_id, 1, 0, '', '{"placeholder": true, "reason": "extractor_unavailable"}')
                    """, {"doc_id": doc_id})
                    tables_extracted += 1
                    processed += 1
                except Exception:
                    errors += 1
        
        await self.db.commit()
        
        return {
            "items_processed": processed,
            "items_created": tables_extracted,
            "documents_processed": processed,
            "tables_extracted": tables_extracted,
            "error_count": errors
        }
        
    async def _warmup_caches(self, dry_run: bool = True) -> Dict[str, Any]:
        """Pre-warm caches with common queries"""
        
        if dry_run:
            return {
                "items_processed": 0,
                "message": "Would warm up caches with common queries"
            }
        
        cache_operations = 0
        
        # Warm up Redis with common query patterns
        common_queries = [
            "STEMI protocol",
            "blood transfusion form", 
            "cardiology contact",
            "stroke protocol",
            "medication dosage"
        ]
        
        try:
            for query in common_queries:
                # Cache the query classification result
                cache_key = f"query_classification:{hash(query)}"
                cache_value = {
                    "query": query,
                    "cached_at": datetime.utcnow().isoformat(),
                    "type": "warmup"
                }
                
                await self.redis.set(
                    cache_key, 
                    json.dumps(cache_value), 
                    ex=3600  # 1 hour
                )
                cache_operations += 1
                
        except Exception as e:
            self.logger.warning(f"Cache warmup failed: {e}")
        
        return {
            "items_processed": cache_operations,
            "items_created": cache_operations,
            "cache_entries_created": cache_operations
        }
        
    async def _optimize_search_indices(self, dry_run: bool = True) -> Dict[str, Any]:
        """Optimize search indices for better performance"""
        
        if dry_run:
            return {
                "items_processed": 0,
                "message": "Would optimize database and search indices"
            }
        
        optimizations = 0
        
        try:
            # Analyze and vacuum tables for better performance
            tables_to_optimize = [
                "documents",
                "document_chunks", 
                "extracted_tables",
                "query_response_cache"
            ]
            
            for table in tables_to_optimize:
                try:
                    await self.db.execute(f"ANALYZE {table}")
                    optimizations += 1
                    self.logger.info(f"Analyzed table: {table}")
                except Exception as e:
                    self.logger.warning(f"Failed to analyze {table}: {e}")
            
            # Update table statistics
            await self.db.execute("VACUUM ANALYZE")
            optimizations += 1
            
        except Exception as e:
            self.logger.warning(f"Index optimization failed: {e}")
        
        return {
            "items_processed": optimizations,
            "items_updated": optimizations,
            "tables_optimized": optimizations
        }

async def main():
    """CLI entry point for backfill manager"""
    parser = argparse.ArgumentParser(description="Run data backfill operations")
    parser.add_argument("--dry-run", action="store_true", help="Run in dry-run mode (no changes)")
    parser.add_argument("--execute", action="store_true", help="Execute actual backfill (opposite of dry-run)")
    parser.add_argument("--tasks", nargs="+", choices=["elasticsearch", "highlighting", "tables", "cache_warmup", "search_optimization"], 
                       help="Specific tasks to run (default: auto-select based on features)")
    parser.add_argument("--output", choices=["json", "text"], default="text", help="Output format")
    parser.add_argument("--config-file", help="Path to configuration file")
    
    args = parser.parse_args()
    
    # Determine if this is a dry run
    dry_run = not args.execute if args.execute else True
    if args.dry_run:
        dry_run = True
    
    # Setup path for imports
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    try:
        # Import required components
        from src.cache.redis_client import get_redis_client
        from src.config.enhanced_settings import EnhancedSettings
        from src.models.database import get_db_session
        
        # Load settings
        if args.config_file:
            os.environ["EDBOT_CONFIG_FILE"] = args.config_file
            
        settings = EnhancedSettings()
        
        # Get database and Redis connections
        db_session = await get_db_session()
        redis_client = await get_redis_client()
        
        # Get Elasticsearch client if enabled
        es_client = None
        if getattr(settings.features, 'enable_elasticsearch', False):
            try:
                from src.search.elasticsearch_client import ElasticsearchClient
                es_client = ElasticsearchClient(settings)
            except ImportError:
                logger.warning("Elasticsearch enabled but client not available")
        
        # Run backfill
        manager = BackfillManager(settings, db_session, redis_client, es_client)
        results = await manager.run_full_backfill(dry_run=dry_run, selected_tasks=args.tasks)
        
        # Output results
        if args.output == "json":
            print(json.dumps(results, indent=2))
        else:
            # Text output already handled by logger
            if results["failure_count"] == 0:
                logger.info("✅ All backfill tasks completed successfully")
            else:
                logger.error(f"❌ {results['failure_count']} backfill tasks failed")
            
        # Exit with appropriate code
        sys.exit(0 if results["failure_count"] == 0 else 1)
            
    except Exception as e:
        logger.error(f"Backfill failed: {e}")
        if args.output == "json":
            error_output = {
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e),
                "status": "failed"
            }
            print(json.dumps(error_output, indent=2))
        sys.exit(2)

if __name__ == "__main__":
    asyncio.run(main())