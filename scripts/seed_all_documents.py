#!/usr/bin/env python3
"""
Comprehensive document seeding script for EDBotv8.
Processes all medical documents with enhanced classification and categorization.

This script addresses the current limitation where only 37 out of 337 available
documents are seeded. It implements:
- Comprehensive document discovery and processing
- Enhanced content classification using ContentClassifier
- Bulk processing with progress tracking
- Detailed logging and error handling
- Database verification and validation
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.config.settings import Settings
from src.ingestion.content_classifier import ContentClassifier, ParsedDocument
from src.ingestion.tasks import DocumentProcessor
from src.models.database import get_db_session
from src.models.entities import Document, DocumentChunk, DocumentRegistry
from src.models.query_types import QueryType
from src.utils.logging import get_logger

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = get_logger(__name__)

class ComprehensiveSeeder:
    """Enhanced document seeder with comprehensive processing capabilities."""
    
    def __init__(self, docs_directory: str = "/mnt/d/Dev/EDbotv8/docs"):
        self.docs_directory = Path(docs_directory)
        self.settings = Settings()
        self.processor = DocumentProcessor()
        self.classifier = ContentClassifier()
        
        # Statistics tracking
        self.stats = {
            'total_found': 0,
            'already_processed': 0,
            'newly_processed': 0,
            'failed': 0,
            'by_type': {qt.value: 0 for qt in QueryType},
            'by_extension': {},
            'errors': []
        }
        
        logger.info(f"Initialized ComprehensiveSeeder for directory: {docs_directory}")
    
    async def seed_all_documents(self, force_reprocess: bool = False) -> Dict:
        """
        Main method to seed all documents with comprehensive processing.
        
        Args:
            force_reprocess: If True, reprocess already-seeded documents
            
        Returns:
            Dict with processing statistics
        """
        logger.info("Starting comprehensive document seeding process")
        
        # 1. Discover all documents
        document_files = self._discover_documents()
        self.stats['total_found'] = len(document_files)
        
        logger.info(f"Discovered {len(document_files)} documents for processing")
        
        # 2. Filter already processed documents if not forcing reprocess
        if not force_reprocess:
            document_files = await self._filter_unprocessed(document_files)
            logger.info(f"After filtering, {len(document_files)} documents need processing")
        
        # 3. Process documents with progress tracking
        await self._process_documents_batch(document_files)
        
        # 4. Validate and generate final report
        final_stats = await self._generate_final_report()
        
        logger.info("Comprehensive document seeding completed")
        return final_stats
    
    def _discover_documents(self) -> List[Path]:
        """Discover all processable documents in the docs directory."""
        supported_extensions = {'.pdf', '.docx', '.txt', '.md', '.doc'}
        document_files = []
        
        logger.info(f"Scanning directory: {self.docs_directory}")
        
        # Handle nested directory structures and encoded paths
        for root, dirs, files in os.walk(self.docs_directory):
            for file in files:
                file_path = Path(root) / file
                
                # Skip hidden files and system files
                if file.startswith('.') or file.startswith('~'):
                    continue
                
                # Check extension
                if file_path.suffix.lower() in supported_extensions:
                    document_files.append(file_path)
                    
                    # Track extension statistics
                    ext = file_path.suffix.lower()
                    self.stats['by_extension'][ext] = self.stats['by_extension'].get(ext, 0) + 1
        
        logger.info(f"Found {len(document_files)} documents by extension: {self.stats['by_extension']}")
        return sorted(document_files)
    
    async def _filter_unprocessed(self, document_files: List[Path]) -> List[Path]:
        """Filter out documents that are already processed."""
        unprocessed = []
        processed_filenames = set()
        
        # Get list of already processed documents
        with get_db_session() as session:
            existing_docs = session.query(Document.filename).all()
            processed_filenames = {doc.filename for doc in existing_docs}
        
        logger.info(f"Found {len(processed_filenames)} already processed documents")
        
        for file_path in document_files:
            if file_path.name in processed_filenames:
                self.stats['already_processed'] += 1
                logger.debug(f"Skipping already processed: {file_path.name}")
            else:
                unprocessed.append(file_path)
        
        return unprocessed
    
    async def _process_documents_batch(self, document_files: List[Path]) -> None:
        """Process documents in batches with comprehensive error handling."""
        batch_size = 10  # Process in smaller batches for better error handling
        total_files = len(document_files)
        
        for i in range(0, total_files, batch_size):
            batch = document_files[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (total_files + batch_size - 1) // batch_size
            
            logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} files)")
            
            # Process each file in the batch
            for j, file_path in enumerate(batch):
                file_num = i + j + 1
                logger.info(f"Processing [{file_num}/{total_files}]: {file_path.name}")
                
                try:
                    await self._process_single_document(file_path)
                    self.stats['newly_processed'] += 1
                    
                except Exception as e:
                    self.stats['failed'] += 1
                    error_msg = f"Failed to process {file_path.name}: {str(e)}"
                    self.stats['errors'].append(error_msg)
                    logger.error(error_msg)
            
            # Brief pause between batches to avoid overwhelming the system
            await asyncio.sleep(0.5)
    
    async def _process_single_document(self, file_path: Path) -> None:
        """Process a single document with enhanced classification."""
        # First pass: Use the existing DocumentProcessor
        success = await self.processor.process_document(str(file_path))
        
        if not success:
            raise Exception("DocumentProcessor failed")
        
        # Second pass: Enhance the classification and registry entry
        await self._enhance_document_classification(file_path)
    
    async def _enhance_document_classification(self, file_path: Path) -> None:
        """Enhance document classification using ContentClassifier."""
        with get_db_session() as session:
            # Find the document we just processed
            document = session.query(Document).filter(
                Document.filename == file_path.name
            ).first()
            
            if not document:
                raise Exception(f"Document not found in database: {file_path.name}")
            
            # Create ParsedDocument for classification
            parsed_doc = ParsedDocument(
                filename=document.filename,
                content=document.content or "",
                metadata=document.meta or {}
            )
            
            # Classify using ContentClassifier
            classification = self.classifier.classify_document(parsed_doc)
            
            # Update document with enhanced classification
            document.content_type = self._map_query_type_to_content_type(classification.query_type)
            
            # Update registry entry with enhanced data
            registry = session.query(DocumentRegistry).filter(
                DocumentRegistry.document_id == document.id
            ).first()
            
            if registry:
                registry.query_type = classification.query_type.value
                registry.confidence = classification.confidence
                registry.classification_method = classification.method
                registry.medical_specialty = classification.medical_specialty
                registry.urgency_level = classification.urgency_level
                registry.primary_keywords = classification.primary_keywords
                registry.medical_terms = classification.medical_terms
                registry.abbreviations = classification.abbreviations
                
                # Update metadata with classification evidence
                if not registry.meta:
                    registry.meta = {}
                registry.meta['classification_evidence'] = classification.evidence
            
            session.commit()
            
            # Track statistics by query type
            self.stats['by_type'][classification.query_type.value] += 1
            
            logger.debug(
                f"Enhanced classification for {document.filename}: "
                f"{classification.query_type.value} (confidence: {classification.confidence:.2f})"
            )
    
    def _map_query_type_to_content_type(self, query_type: QueryType) -> str:
        """Map QueryType to content_type for backwards compatibility."""
        mapping = {
            QueryType.FORM_RETRIEVAL: 'form',
            QueryType.PROTOCOL_STEPS: 'protocol', 
            QueryType.CONTACT_LOOKUP: 'contact',
            QueryType.CRITERIA_CHECK: 'criteria',
            QueryType.DOSAGE_LOOKUP: 'dosage',
            QueryType.SUMMARY_REQUEST: 'reference'
        }
        return mapping.get(query_type, 'reference')
    
    async def _generate_final_report(self) -> Dict:
        """Generate final processing report with database validation."""
        # Validate database state
        with get_db_session() as session:
            final_doc_count = session.query(Document).count()
            final_chunk_count = session.query(DocumentChunk).count()
            final_registry_count = session.query(DocumentRegistry).count()
            
            # Get documents by type
            type_distribution = {}
            for query_type in QueryType:
                count = session.query(DocumentRegistry).filter(
                    DocumentRegistry.query_type == query_type.value
                ).count()
                type_distribution[query_type.value] = count
        
        final_stats = {
            'processing_summary': {
                'total_discovered': self.stats['total_found'],
                'already_processed': self.stats['already_processed'],
                'newly_processed': self.stats['newly_processed'],
                'failed_processing': self.stats['failed'],
                'success_rate': f"{((self.stats['newly_processed'] / max(1, self.stats['total_found'] - self.stats['already_processed'])) * 100):.1f}%"
            },
            'database_state': {
                'total_documents': final_doc_count,
                'total_chunks': final_chunk_count,
                'total_registry_entries': final_registry_count
            },
            'document_distribution': {
                'by_query_type': type_distribution,
                'by_file_extension': self.stats['by_extension']
            },
            'errors': self.stats['errors'][:10],  # Limit to first 10 errors
            'timestamp': datetime.now().isoformat()
        }
        
        # Log comprehensive summary
        logger.info("=== COMPREHENSIVE SEEDING REPORT ===")
        logger.info(f"Total documents discovered: {final_stats['processing_summary']['total_discovered']}")
        logger.info(f"Already processed: {final_stats['processing_summary']['already_processed']}")
        logger.info(f"Newly processed: {final_stats['processing_summary']['newly_processed']}")
        logger.info(f"Failed: {final_stats['processing_summary']['failed_processing']}")
        logger.info(f"Success rate: {final_stats['processing_summary']['success_rate']}")
        logger.info(f"Final database state: {final_doc_count} docs, {final_chunk_count} chunks, {final_registry_count} registry entries")
        logger.info("=== Query Type Distribution ===")
        for qtype, count in type_distribution.items():
            logger.info(f"{qtype}: {count} documents")
        
        if self.stats['errors']:
            logger.warning(f"Encountered {len(self.stats['errors'])} errors during processing")
        
        return final_stats
    
    async def cleanup_duplicate_documents(self) -> int:
        """Clean up any duplicate documents that might exist."""
        logger.info("Checking for duplicate documents...")
        
        removed_count = 0
        with get_db_session() as session:
            # Find duplicate filenames
            from sqlalchemy import func
            duplicates = session.query(
                Document.filename,
                func.count(Document.id).label('count')
            ).group_by(Document.filename).having(func.count(Document.id) > 1).all()
            
            for filename, count in duplicates:
                logger.warning(f"Found {count} duplicates of {filename}")
                
                # Keep the newest, remove others
                docs = session.query(Document).filter(
                    Document.filename == filename
                ).order_by(Document.created_at.desc()).all()
                
                for doc in docs[1:]:  # Keep first (newest), remove rest
                    # Remove related chunks and registry entries
                    session.query(DocumentChunk).filter(
                        DocumentChunk.document_id == doc.id
                    ).delete()
                    session.query(DocumentRegistry).filter(
                        DocumentRegistry.document_id == doc.id
                    ).delete()
                    session.delete(doc)
                    removed_count += 1
            
            session.commit()
        
        if removed_count > 0:
            logger.info(f"Removed {removed_count} duplicate documents")
        
        return removed_count


async def main():
    """Main entry point for comprehensive document seeding."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Comprehensive EDBotv8 Document Seeding")
    parser.add_argument(
        '--docs-dir', 
        default='/mnt/d/Dev/EDbotv8/docs',
        help='Directory containing documents to seed'
    )
    parser.add_argument(
        '--force-reprocess',
        action='store_true',
        help='Force reprocessing of already-seeded documents'
    )
    parser.add_argument(
        '--cleanup-duplicates',
        action='store_true', 
        help='Clean up duplicate documents before processing'
    )
    parser.add_argument(
        '--output-report',
        help='Save processing report to JSON file'
    )
    
    args = parser.parse_args()
    
    # Initialize seeder
    seeder = ComprehensiveSeeder(docs_directory=args.docs_dir)
    
    try:
        # Clean up duplicates if requested
        if args.cleanup_duplicates:
            removed = await seeder.cleanup_duplicate_documents()
            logger.info(f"Cleanup completed: {removed} duplicates removed")
        
        # Run comprehensive seeding
        final_stats = await seeder.seed_all_documents(
            force_reprocess=args.force_reprocess
        )
        
        # Save report if requested
        if args.output_report:
            with open(args.output_report, 'w') as f:
                json.dump(final_stats, f, indent=2)
            logger.info(f"Report saved to {args.output_report}")
        
        # Print summary
        print("\n" + "="*50)
        print("COMPREHENSIVE SEEDING COMPLETED")
        print("="*50)
        print(f"Documents processed: {final_stats['processing_summary']['newly_processed']}")
        print(f"Total in database: {final_stats['database_state']['total_documents']}")
        print(f"Success rate: {final_stats['processing_summary']['success_rate']}")
        print("="*50)
        
        return 0
        
    except Exception as e:
        logger.error(f"Comprehensive seeding failed: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)