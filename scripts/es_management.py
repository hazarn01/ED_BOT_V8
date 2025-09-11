#!/usr/bin/env python3
"""
Elasticsearch management utility for ED Bot v8.
Provides CLI commands for managing ES indices, statistics, and operations.
"""

import argparse
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.config.settings import get_settings
from src.search.elasticsearch_client import ElasticsearchClient
from src.search.es_index_manager import ElasticsearchIndexManager
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ESManagementCLI:
    """Command-line interface for Elasticsearch management."""
    
    def __init__(self):
        self.settings = get_settings()
        self.es_client = ElasticsearchClient(self.settings)
        
        if not self.es_client.is_available():
            logger.error("Elasticsearch is not available. Please start ES service first.")
            sys.exit(1)
            
        self.index_manager = ElasticsearchIndexManager(self.es_client, self.settings)
        
    def create_indices(self):
        """Create all Elasticsearch indices."""
        logger.info("Creating Elasticsearch indices...")
        success = self.index_manager.create_indices()
        
        if success:
            print("✅ All indices created successfully")
            self.show_stats()
        else:
            print("❌ Failed to create some indices")
            sys.exit(1)
            
    def delete_indices(self, confirm: bool = False):
        """Delete all Elasticsearch indices."""
        if not confirm:
            print("❌ Must use --confirm flag to delete indices")
            sys.exit(1)
            
        logger.warning("Deleting all Elasticsearch indices...")
        success = self.index_manager.delete_indices(confirm=True)
        
        if success:
            print("✅ All indices deleted successfully")
        else:
            print("❌ Failed to delete indices")
            sys.exit(1)
            
    def show_stats(self):
        """Show index statistics."""
        logger.info("Fetching Elasticsearch index statistics...")
        stats = self.index_manager.get_index_stats()
        
        print("\n" + "="*60)
        print("ELASTICSEARCH INDEX STATISTICS")
        print("="*60)
        
        for logical_name, index_stats in stats.items():
            print(f"\n📊 {logical_name.upper()}")
            print(f"  Index: {index_stats.get('index_name', 'N/A')}")
            
            if 'error' in index_stats:
                print(f"  ❌ Error: {index_stats['error']}")
            elif index_stats.get('exists', True) is False:
                print("  ⚠️  Index does not exist")
            else:
                print(f"  Documents: {index_stats.get('document_count', 0):,}")
                print(f"  Size: {index_stats.get('size_mb', 0):.2f} MB")
                
        # Show cluster health
        health = self.index_manager.verify_indices_health()
        print(f"\n🏥 Cluster Health: {health.get('cluster', 'unknown').upper()}")
        
        if 'error' in health:
            print(f"  ❌ Error: {health['error']}")
        else:
            for logical_name, status in health.items():
                if logical_name != 'cluster':
                    status_emoji = {"green": "✅", "yellow": "⚠️", "red": "❌"}.get(status, "❓")
                    print(f"  {status_emoji} {logical_name}: {status}")
                    
    def optimize_indices(self):
        """Optimize indices for better performance."""
        logger.info("Optimizing Elasticsearch indices...")
        success = self.index_manager.optimize_indices()
        
        if success:
            print("✅ Indices optimized successfully")
            self.show_stats()
        else:
            print("❌ Failed to optimize indices")
            sys.exit(1)
            
    def verify_counts(self):
        """Verify ES/PostgreSQL count matching."""
        from sqlalchemy import create_engine, func, select
        from sqlalchemy.orm import sessionmaker

        from src.models.entities import Document, DocumentChunk, DocumentRegistry
        
        logger.info("Verifying document counts between PostgreSQL and Elasticsearch...")
        
        # Get database counts
        engine = create_engine(self.settings.database_url)
        SessionLocal = sessionmaker(bind=engine)
        
        with SessionLocal() as session:
            db_doc_count = session.scalar(select(func.count(Document.id)))
            db_chunk_count = session.scalar(select(func.count(DocumentChunk.id)))
            db_registry_count = session.scalar(select(func.count(DocumentRegistry.id)))
        
        # Get Elasticsearch counts
        es = self.es_client.get_client()
        index_names = self.index_manager.get_index_names()
        
        try:
            es_doc_count = es.count(index=index_names['documents'])["count"] if es.indices.exists(index=index_names['documents']) else 0
            es_chunk_count = es.count(index=index_names['chunks'])["count"] if es.indices.exists(index=index_names['chunks']) else 0
            es_registry_count = es.count(index=index_names['registry'])["count"] if es.indices.exists(index=index_names['registry']) else 0
        except Exception as e:
            logger.error(f"Failed to get ES counts: {e}")
            print("❌ Failed to retrieve Elasticsearch counts")
            sys.exit(1)
        
        # Calculate match rates
        doc_match_rate = (es_doc_count / db_doc_count * 100) if db_doc_count > 0 else 0
        chunk_match_rate = (es_chunk_count / db_chunk_count * 100) if db_chunk_count > 0 else 0
        registry_match_rate = (es_registry_count / db_registry_count * 100) if db_registry_count > 0 else 0
        
        print("\n" + "="*60)
        print("POSTGRESQL vs ELASTICSEARCH COUNT VERIFICATION")
        print("="*60)
        
        def print_comparison(name, db_count, es_count, match_rate):
            status_emoji = "✅" if match_rate >= 95.0 else "⚠️" if match_rate >= 80.0 else "❌"
            print(f"\n{status_emoji} {name}")
            print(f"  PostgreSQL: {db_count:,}")
            print(f"  Elasticsearch: {es_count:,}")
            print(f"  Match Rate: {match_rate:.1f}%")
            
        print_comparison("Documents", db_doc_count, es_doc_count, doc_match_rate)
        print_comparison("Chunks", db_chunk_count, es_chunk_count, chunk_match_rate)
        print_comparison("Registry", db_registry_count, es_registry_count, registry_match_rate)
        
        overall_issues = sum(1 for rate in [doc_match_rate, chunk_match_rate, registry_match_rate] if rate < 95.0)
        
        if overall_issues == 0:
            print("\n✅ All counts match within acceptable range (≥95%)")
        else:
            print(f"\n⚠️  {overall_issues} index(es) have low match rates")
            print("Consider running: make es-backfill-execute")
            
        return overall_issues == 0


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Elasticsearch management for ED Bot v8")
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Create indices
    subparsers.add_parser('create-indices', help='Create all Elasticsearch indices')
    
    # Delete indices
    delete_parser = subparsers.add_parser('delete-indices', help='Delete all Elasticsearch indices')
    delete_parser.add_argument('--confirm', action='store_true', help='Confirm deletion')
    
    # Show statistics
    subparsers.add_parser('stats', help='Show index statistics')
    
    # Optimize indices
    subparsers.add_parser('optimize', help='Optimize indices for better performance')
    
    # Verify counts
    subparsers.add_parser('verify-counts', help='Verify ES/PostgreSQL count matching')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
        
    try:
        cli = ESManagementCLI()
        
        if args.command == 'create-indices':
            cli.create_indices()
        elif args.command == 'delete-indices':
            cli.delete_indices(confirm=args.confirm)
        elif args.command == 'stats':
            cli.show_stats()
        elif args.command == 'optimize':
            cli.optimize_indices()
        elif args.command == 'verify-counts':
            success = cli.verify_counts()
            sys.exit(0 if success else 1)
        else:
            parser.print_help()
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⏹️  Operation cancelled")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Management operation failed: {e}")
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()