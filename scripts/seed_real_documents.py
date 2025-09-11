#!/usr/bin/env python3
"""
Enhanced real document seeding script for PRP-32.
Processes all medical documents from /docs through the complete ingestion pipeline
with enhanced categorization, progress tracking, and resumable processing.
"""

import argparse
import asyncio
import json
import time
from pathlib import Path
from typing import Dict, List, Optional

from src.config.settings import get_settings
from src.ingestion.tasks import DocumentProcessor
from src.models.database import get_db_session
from src.models.entities import Document, DocumentChunk, DocumentRegistry
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ProgressTracker:
    """Track document processing progress with persistence."""
    
    def __init__(self, progress_file: Path = Path("seeding_progress.json")):
        self.progress_file = progress_file
        self.processed_files = self.load_progress()
        self.stats = {
            'total': 0,
            'processed': 0,
            'successful': 0,
            'failed': 0,
            'skipped': 0,
            'start_time': time.time()
        }
    
    def load_progress(self) -> Dict[str, bool]:
        """Load processing progress from file."""
        if self.progress_file.exists():
            try:
                with open(self.progress_file, 'r') as f:
                    data = json.load(f)
                    return data.get('processed_files', {})
            except Exception as e:
                logger.warning(f"Could not load progress file: {e}")
                return {}
        return {}
    
    def save_progress(self):
        """Save current progress to file."""
        try:
            progress_data = {
                'processed_files': self.processed_files,
                'stats': self.stats,
                'last_updated': time.time()
            }
            with open(self.progress_file, 'w') as f:
                json.dump(progress_data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save progress: {e}")
    
    def mark_processed(self, file_path: str, success: bool):
        """Mark a file as processed."""
        self.processed_files[file_path] = success
        self.stats['processed'] += 1
        if success:
            self.stats['successful'] += 1
        else:
            self.stats['failed'] += 1
        self.save_progress()
    
    def is_processed(self, file_path: str) -> bool:
        """Check if file was already processed successfully."""
        return self.processed_files.get(file_path, False)
    
    def get_stats(self) -> Dict:
        """Get current processing statistics."""
        elapsed = time.time() - self.stats['start_time']
        return {
            **self.stats,
            'elapsed_minutes': elapsed / 60,
            'docs_per_minute': self.stats['processed'] / (elapsed / 60) if elapsed > 0 else 0
        }


class EnhancedDocumentSeeder:
    """Enhanced document seeder with comprehensive processing."""
    
    def __init__(self, batch_size: int = 10, force_reprocess: bool = False):
        self.processor = DocumentProcessor()
        self.batch_size = batch_size
        self.force_reprocess = force_reprocess
        self.settings = get_settings()
        
        logger.info(
            "Enhanced document seeder initialized",
            extra_fields={
                'batch_size': batch_size,
                'force_reprocess': force_reprocess
            }
        )
    
    async def seed_all_documents(self, docs_path: Path) -> Dict[str, int]:
        """Process all documents from the docs directory."""
        progress = ProgressTracker()
        failures_csv = Path("seeding_failures.csv")
        # Initialize CSV header
        try:
            with open(failures_csv, 'w', encoding='utf-8') as f:
                f.write("filename,error_type,error_message\n")
        except Exception:
            pass
        
        # Find all documents to process
        all_files = list(docs_path.glob("*.pdf"))
        all_files.extend(docs_path.glob("*.docx"))
        all_files.extend(docs_path.glob("*.md"))
        all_files.extend(docs_path.glob("*.txt"))
        
        # Filter out already processed files (unless force reprocess)
        if self.force_reprocess:
            remaining_files = all_files
            logger.info("Force reprocessing all documents")
        else:
            remaining_files = [f for f in all_files if not progress.is_processed(str(f))]
        
        progress.stats['total'] = len(all_files)
        progress.stats['skipped'] = len(all_files) - len(remaining_files)
        
        logger.info(
            "Document processing overview",
            extra_fields={
                'total_documents': len(all_files),
                'remaining_to_process': len(remaining_files),
                'already_processed': progress.stats['skipped']
            }
        )
        
        if not remaining_files:
            logger.info("All documents already processed successfully!")
            return progress.get_stats()
        
        # Process in batches to avoid overwhelming the system
        for i in range(0, len(remaining_files), self.batch_size):
            batch = remaining_files[i:i + self.batch_size]
            batch_num = i // self.batch_size + 1
            total_batches = (len(remaining_files) + self.batch_size - 1) // self.batch_size
            
            logger.info(
                f"Processing batch {batch_num}/{total_batches}",
                extra_fields={
                    'batch_size': len(batch),
                    'files': [f.name for f in batch]
                }
            )
            
            # Process batch with error handling
            await self._process_batch(batch, progress, failures_csv)
            
            # Brief pause between batches to prevent overwhelming system
            if i + self.batch_size < len(remaining_files):
                await asyncio.sleep(2)
            
            # Log progress
            stats = progress.get_stats()
            logger.info(
                f"Batch {batch_num} completed",
                extra_fields={
                    'processed': stats['processed'],
                    'successful': stats['successful'],
                    'failed': stats['failed'],
                    'rate_docs_per_min': f"{stats['docs_per_minute']:.1f}"
                }
            )
        
        # Final validation
        final_stats = await self._validate_seeded_documents(progress)
        
        logger.info(
            "Real document seeding completed!",
            extra_fields=final_stats
        )
        
        return final_stats
    
    async def _process_batch(self, file_batch: List[Path], progress: ProgressTracker, failures_csv: Path):
        """Process a batch of files with comprehensive error handling."""
        for file_path in file_batch:
            try:
                # Infer content type from filename patterns
                content_type = self._infer_content_type_from_filename(file_path)
                
                # Process the document through full pipeline
                start_time = time.time()
                success = await self.processor.process_document(
                    file_path=str(file_path),
                    content_type=content_type
                )
                processing_time = time.time() - start_time
                
                # Update progress
                progress.mark_processed(str(file_path), success)
                
                if success:
                    logger.info(
                        f"✅ {file_path.name}",
                        extra_fields={
                            'content_type': content_type,
                            'processing_time': f"{processing_time:.1f}s"
                        }
                    )
                else:
                    logger.warning(f"❌ {file_path.name} -> Processing failed")
                    
            except Exception as e:
                logger.error(
                    f"❌ {file_path.name} -> ERROR: {str(e)}",
                    extra_fields={'error_type': type(e).__name__}
                )
                progress.mark_processed(str(file_path), False)
                try:
                    with open(failures_csv, 'a', encoding='utf-8') as f:
                        safe_msg = str(e).replace('\n', ' ').replace('\r', ' ')
                        f.write(f"{file_path.name},{type(e).__name__},{safe_msg}\n")
                except Exception:
                    pass
    
    def _infer_content_type_from_filename(self, file_path: Path) -> Optional[str]:
        """Smart content type inference based on filename patterns."""
        filename_lower = file_path.name.lower()
        
        # FORM indicators (highest priority for exact matches)
        form_patterns = [
            'consent', 'form', 'checklist', 'template', 'agreement',
            'admission', 'discharge', 'transfusion', 'ama', 'autopsy'
        ]
        if any(term in filename_lower for term in form_patterns):
            return 'form'
        
        # PROTOCOL indicators
        protocol_patterns = [
            'protocol', 'pathway', 'guideline', 'algorithm',
            'stemi', 'sepsis', 'stroke', 'trauma', 'activation',
            'procedure', 'management', 'treatment'
        ]
        if any(term in filename_lower for term in protocol_patterns):
            return 'protocol'
            
        # CONTACT indicators
        contact_patterns = [
            'on-call', 'oncall', 'directory', 'contact', 'coverage',
            'who', 'call', 'pager', 'phone'
        ]
        if any(term in filename_lower for term in contact_patterns):
            return 'contact'
            
        # CRITERIA indicators
        criteria_patterns = [
            'criteria', 'rules', 'score', 'ottawa', 'wells', 'centor',
            'nexus', 'perc', 'pecarn', 'indication', 'threshold'
        ]
        if any(term in filename_lower for term in criteria_patterns):
            return 'criteria'
            
        # DOSAGE indicators
        dosage_patterns = [
            'dosage', 'dose', 'dosing', 'medication', 'drug',
            'pharmacy', 'administration', 'mg', 'ml'
        ]
        if any(term in filename_lower for term in dosage_patterns):
            return 'dosage'
            
        # SUMMARY indicators (default for guides, manuals, etc.)
        summary_patterns = [
            'guide', 'manual', 'handbook', 'overview', 'summary',
            'reference', 'information', 'policy', 'standard'
        ]
        if any(term in filename_lower for term in summary_patterns):
            return 'summary'
        
        # Default to None - let content-based classification handle it
        return None
    
    async def _validate_seeded_documents(self, progress: ProgressTracker) -> Dict[str, int]:
        """Validate that seeded documents are properly categorized."""
        stats = progress.get_stats()
        
        try:
            with get_db_session() as session:
                # Count documents by query type
                query_type_counts = {}
                registries = session.query(DocumentRegistry).all()
                
                for registry in registries:
                    query_type = registry.query_type or 'unknown'
                    query_type_counts[query_type] = query_type_counts.get(query_type, 0) + 1
                
                # Count total documents and chunks
                total_documents = session.query(Document).count()
                total_chunks = session.query(DocumentChunk).count()
                total_registries = session.query(DocumentRegistry).count()
                
                validation_stats = {
                    **stats,
                    'database_documents': total_documents,
                    'database_chunks': total_chunks,
                    'database_registries': total_registries,
                    'query_type_distribution': query_type_counts
                }
                
                logger.info(
                    "Document validation completed",
                    extra_fields=validation_stats
                )
                
                return validation_stats
                
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            return stats


async def main():
    """Main function with command line argument handling."""
    parser = argparse.ArgumentParser(description='Enhanced real document seeding')
    parser.add_argument('--docs-path', type=str, 
                       default='/mnt/d/Dev/EDbotv8/docs',
                       help='Path to documents directory')
    parser.add_argument('--batch-size', type=int, default=10,
                       help='Number of documents to process per batch')
    parser.add_argument('--force', action='store_true',
                       help='Force reprocessing of all documents')
    parser.add_argument('--validate-only', action='store_true',
                       help='Only run validation, no processing')
    
    args = parser.parse_args()
    
    docs_path = Path(args.docs_path)
    if not docs_path.exists():
        logger.error(f"Documents path does not exist: {docs_path}")
        return
    
    logger.info(
        "Starting enhanced document seeding",
        extra_fields={
            'docs_path': str(docs_path),
            'batch_size': args.batch_size,
            'force_reprocess': args.force
        }
    )
    
    seeder = EnhancedDocumentSeeder(
        batch_size=args.batch_size,
        force_reprocess=args.force
    )
    
    if args.validate_only:
        progress = ProgressTracker()
        await seeder._validate_seeded_documents(progress)
    else:
        final_stats = await seeder.seed_all_documents(docs_path)
        
        # Print final summary
        print("\n" + "="*50)
        print("ENHANCED DOCUMENT SEEDING COMPLETE")
        print("="*50)
        print(f"Total documents found: {final_stats['total']}")
        print(f"Successfully processed: {final_stats['successful']}")
        print(f"Failed: {final_stats['failed']}")
        print(f"Already processed (skipped): {final_stats['skipped']}")
        print(f"Processing time: {final_stats['elapsed_minutes']:.1f} minutes")
        print(f"Rate: {final_stats['docs_per_minute']:.1f} docs/minute")
        
        if 'query_type_distribution' in final_stats:
            print("\nQuery Type Distribution:")
            for qtype, count in final_stats['query_type_distribution'].items():
                print(f"  {qtype}: {count} documents")
        
        print("\n✅ Real medical documents are now available for query processing!")


if __name__ == "__main__":
    asyncio.run(main())