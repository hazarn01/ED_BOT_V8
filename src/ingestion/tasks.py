import argparse
import asyncio
import hashlib
from pathlib import Path
from typing import List, Optional

from elasticsearch.helpers import bulk
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from src.config import settings
from src.config.settings import get_settings
from src.ingestion.content_classifier import ContentClassifier, ParsedDocument
from src.ingestion.langextract_runner import LangExtractRunner
from src.ingestion.table_extractor import TableExtractor
from src.ingestion.unstructured_runner import UnstructuredRunner
from src.models.entities import (
    Document,
    DocumentChunk,
    DocumentRegistry,
    ExtractedEntity,
    ExtractedTable,
)
from src.search.elasticsearch_client import ElasticsearchClient
from src.search.es_index_manager import ElasticsearchIndexManager
from src.utils.logging import get_logger
from src.utils.observability import metrics, track_latency

logger = get_logger(__name__)


class DocumentProcessor:
    """Process documents through the full ingestion pipeline."""

    def __init__(self, es_client: Optional[ElasticsearchClient] = None):
        self.unstructured = UnstructuredRunner()
        self.langextract = LangExtractRunner()
        self.engine = create_engine(settings.database_url)
        self.SessionLocal = sessionmaker(bind=self.engine)
        
        # Get settings and initialize components
        self.settings = get_settings()
        
        # Initialize table extractor (PRP 19)
        self.table_extractor = TableExtractor(self.settings)
        
        # Initialize content classifier (PRP 32)
        self.content_classifier = ContentClassifier()
        
        # Elasticsearch dual indexing setup
        self.es_client = es_client or (
            ElasticsearchClient(self.settings) if self.settings.search_backend == "hybrid" else None
        )
        self.dual_index = self.es_client and self.es_client.is_available()
        
        if self.dual_index:
            logger.info("Dual indexing enabled (PostgreSQL + Elasticsearch)")
            # Ensure indices exist
            index_manager = ElasticsearchIndexManager(self.es_client, self.settings)
            index_manager.create_indices()
        else:
            logger.info("Single indexing mode (PostgreSQL only)")

    async def process_document(
        self, file_path: str, content_type: Optional[str] = None
    ) -> bool:
        """Process a single document through the pipeline."""
        path = Path(file_path)

        logger.info(
            "Processing document",
            extra_fields={"file_path": str(path), "content_type": content_type},
        )

        # Basic retry-once policy for transient failures
        attempts = 0
        last_error = None
        while attempts < 2:
            try:
                with track_latency("document_processing", {"filename": path.name, "attempt": attempts + 1}):
                    # 1. Check if already processed
                    if await self._is_already_processed(path):
                        logger.info(
                            "Document already processed, skipping",
                            extra_fields={"filename": path.name},
                        )
                        return True

                    # 2. Parse with Unstructured
                    parsed_doc = await self.unstructured.parse_document(str(path))

                    # 3. Extract entities with LangExtract
                    entities = await self.langextract.extract_entities(
                        parsed_doc.content, parsed_doc.filename
                    )

                    # 4. Extract tables if enabled (PRP 19)
                    tables = []
                    if self.table_extractor.enabled:
                        tables = await self.table_extractor.extract_tables(
                            str(path), parsed_doc.metadata.get('file_type', path.suffix.lstrip('.'))
                        )

                    # 5. Store in database (PostgreSQL)
                    document_id = await self._store_document(parsed_doc, entities, content_type, tables)

                    # 6. Update registry
                    await self._update_registry(parsed_doc, content_type)
                    
                    # 7. Dual index to Elasticsearch if enabled
                    if self.dual_index:
                        await self._index_to_elasticsearch(document_id, parsed_doc, entities)

                    logger.info(
                        "Document processing completed",
                        extra_fields={
                            "filename": path.name,
                            "chunk_count": len(parsed_doc.chunks),
                            "entity_count": len(entities),
                            "table_count": len(tables),
                        },
                    )

                    return True
            except Exception as e:
                last_error = e
                attempts += 1
                logger.warning(
                    f"Attempt {attempts} failed for {path.name}: {e}",
                    extra_fields={"filename": path.name, "attempt": attempts},
                )
                metrics.record_error("document_processing_attempt_failed", str(e))
                if attempts < 2:
                    await asyncio.sleep(1.0)

        logger.error(
            f"Document processing failed after retries: {last_error}",
            extra_fields={"file_path": str(path)},
        )
        metrics.record_error("document_processing_failed", str(last_error))
        return False

    async def _is_already_processed(self, path: Path) -> bool:
        """Check if document is already in database."""
        with self.SessionLocal() as session:
            stmt = select(Document).where(Document.filename == path.name)
            result = session.execute(stmt).first()
            return result is not None

    async def _store_document(
        self, parsed_doc, entities: List[dict], content_type: Optional[str], tables: Optional[List[dict]] = None
    ) -> str:
        """Store document and related data in database."""
        with self.SessionLocal() as session:
            try:
                # Create document record
                document = Document(
                    filename=parsed_doc.filename,
                    content_type=content_type or self._infer_content_type(parsed_doc),
                    file_type=Path(parsed_doc.filename).suffix.lstrip("."),
                    content=parsed_doc.content,
                    meta={
                        "title": parsed_doc.metadata.title,
                        "page_count": parsed_doc.page_count,
                        "medical_specialties": parsed_doc.metadata.medical_specialties,
                        "tags": parsed_doc.metadata.tags,
                        "tables": parsed_doc.tables,
                        "parse_warnings": parsed_doc.parse_warnings,
                    },
                    file_hash=self._calculate_content_hash(parsed_doc.content),
                )

                session.add(document)
                session.flush()  # Get the document ID

                # Store chunks
                for chunk_data in parsed_doc.chunks:
                    chunk = DocumentChunk(
                        document_id=document.id,
                        chunk_text=chunk_data["text"],
                        chunk_index=chunk_data["chunk_index"],
                        chunk_type=chunk_data.get("chunk_type"),
                        medical_category=chunk_data.get("medical_category"),
                        urgency_level=chunk_data.get("urgency_level", "routine"),
                        contains_contact=chunk_data.get("contains_contact", False),
                        contains_dosage=chunk_data.get("contains_dosage", False),
                        page_number=chunk_data.get("page_number"),
                        meta=chunk_data.get("metadata", {}),
                    )
                    session.add(chunk)

                # Store extracted entities
                for entity_data in entities:
                    entity = ExtractedEntity(
                        document_id=document.id,
                        entity_type=entity_data["entity_type"],
                        page_no=entity_data.get("page_no"),
                        span=entity_data.get("span"),
                        payload=entity_data["payload"],
                        confidence=entity_data.get("confidence", 0.8),
                        evidence_text=entity_data["payload"].get("evidence_text"),
                    )
                    session.add(entity)

                # Store extracted tables (PRP 19)
                if tables:
                    for table_data in tables:
                        # Generate embedding for table content
                        table_embedding = None
                        # TODO: Add embedding generation when needed
                        # table_embedding = await self._generate_embedding(table_data["content_text"])
                        
                        extracted_table = ExtractedTable(
                            document_id=document.id,
                            page_number=table_data["page_number"],
                            table_index=table_data["table_index"],
                            table_type=table_data.get("table_type"),
                            title=table_data.get("title"),
                            caption=table_data.get("caption"),
                            headers=table_data["headers"],
                            rows=table_data["rows"],
                            units=table_data.get("units"),
                            content_text=table_data["content_text"],
                            content_vector=table_embedding,
                            bbox=table_data.get("bbox"),
                            confidence=table_data.get("confidence", 1.0)
                        )
                        session.add(extracted_table)

                session.commit()

                logger.info(
                    "Document stored in database",
                    extra_fields={
                        "document_id": document.id,
                        "filename": document.filename,
                        "chunks": len(parsed_doc.chunks),
                        "entities": len(entities),
                        "tables": len(tables) if tables else 0,
                    },
                )

                return document.id

            except Exception as e:
                session.rollback()
                logger.error(f"Failed to store document: {e}")
                raise

    async def _index_to_elasticsearch(self, document_id: str, parsed_doc, entities: List[dict]):
        """Index document and related data to Elasticsearch."""
        es = self.es_client.get_client()
        if not es:
            logger.warning("ES client unavailable, skipping ES indexing")
            return

        try:
            # Get the stored document and chunks from database
            with self.SessionLocal() as session:
                stmt = select(Document).where(Document.id == document_id)
                document = session.execute(stmt).scalar_one()
                
                stmt_chunks = select(DocumentChunk).where(DocumentChunk.document_id == document_id)
                chunks = session.execute(stmt_chunks).scalars().all()
                
                stmt_registry = select(DocumentRegistry).where(DocumentRegistry.document_id == document_id)
                registry = session.execute(stmt_registry).scalar_one_or_none()

            # Prepare bulk index operations
            operations = []
            
            # Index document
            doc_id = hashlib.md5(f"{document.id}".encode()).hexdigest()
            doc_source = {
                "id": str(document.id),
                "content": document.content[:10000] if document.content else "",  # Limit for ES
                "content_type": document.content_type,
                "filename": document.filename,
                "title": document.meta.get("title", document.filename),
                "protocol_name": self._extract_protocol_name(document),
                "form_name": self._extract_form_name(document),
                "medical_specialties": document.meta.get("medical_specialties", []),
                "tags": document.meta.get("tags", []),
                "file_type": document.file_type,
                "file_hash": document.file_hash,
                "metadata": document.meta,
                "created_at": document.created_at.isoformat(),
                "updated_at": document.updated_at.isoformat()
            }
            
            operations.append({
                "_index": f"{self.settings.elasticsearch_index_prefix}_documents",
                "_id": doc_id,
                "_source": doc_source
            })
            
            # Index chunks
            for chunk in chunks:
                chunk_id = hashlib.md5(f"{chunk.id}".encode()).hexdigest()
                chunk_source = {
                    "id": str(chunk.id),
                    "document_id": str(document.id),
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
            
            # Index registry entry if exists
            if registry:
                registry_id = hashlib.md5(f"{registry.id}".encode()).hexdigest()
                registry_source = {
                    "id": str(registry.id),
                    "document_id": str(document.id),
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
                
            # Bulk index
            success, failed = bulk(es, operations, raise_on_error=False)
            if failed:
                logger.error(f"Failed to index {len(failed)} items to ES: {failed}")
            else:
                logger.info(f"Indexed {success} items to Elasticsearch for document {document.filename}")
                
        except Exception as e:
            logger.error(f"ES indexing failed for document {document_id}: {e}")
            # Don't fail the entire ingestion if ES fails

    def _extract_protocol_name(self, document: Document) -> Optional[str]:
        """Extract protocol name from document for exact matching."""
        if document.content_type == "protocol":
            # Try to extract from title or filename
            title = document.meta.get("title", "").lower()
            filename = document.filename.lower()
            
            protocol_keywords = ["protocol", "pathway", "algorithm", "guideline"]
            for content in [title, filename]:
                if any(keyword in content for keyword in protocol_keywords):
                    # Clean and return protocol name
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
                    # Clean and return form name
                    name = content.replace(".pdf", "").replace("_", " ").strip()
                    return name
        return None

    async def _update_registry(self, parsed_doc, content_type: Optional[str]):
        """Update document registry for quick lookup with enhanced classification."""
        with self.SessionLocal() as session:
            try:
                # Find the document we just created
                stmt = select(Document).where(Document.filename == parsed_doc.filename)
                document = session.execute(stmt).scalar_one()

                # Use ContentClassifier for enhanced categorization (PRP 32)
                classification_input = ParsedDocument(
                    filename=parsed_doc.filename,
                    content=parsed_doc.content or "",
                    metadata=parsed_doc.metadata.__dict__ if hasattr(parsed_doc.metadata, '__dict__') else {}
                )
                
                classification = self.content_classifier.classify_document(classification_input)

                # Generate traditional keywords (backwards compatibility)
                keywords = self._generate_keywords(parsed_doc)

                # Create enhanced registry entry
                registry_entry = DocumentRegistry(
                    document_id=document.id,
                    keywords=keywords,
                    display_name=self._generate_display_name(parsed_doc),
                    file_path=f"/app/docs/{parsed_doc.filename}",
                    category=content_type or self._infer_content_type(parsed_doc),
                    priority=self._calculate_priority(parsed_doc),
                    quick_access=self._should_be_quick_access(parsed_doc),
                    
                    # Enhanced categorization fields (PRP 32)
                    query_type=classification.query_type.value,
                    confidence=classification.confidence,
                    classification_method=classification.method,
                    medical_specialty=classification.medical_specialty,
                    urgency_level=classification.urgency_level,
                    primary_keywords=classification.primary_keywords,
                    medical_terms=classification.medical_terms,
                    abbreviations=classification.abbreviations,
                    
                    meta={
                        "medical_specialties": parsed_doc.metadata.medical_specialties,
                        "tags": parsed_doc.metadata.tags,
                        "classification_evidence": classification.evidence,  # Store classification reasoning
                    },
                )

                session.add(registry_entry)
                session.commit()

                logger.info(
                    "Enhanced registry updated",
                    extra_fields={
                        "document_id": document.id,
                        "query_type": classification.query_type.value,
                        "confidence": f"{classification.confidence:.2f}",
                        "method": classification.method,
                        "specialty": classification.medical_specialty,
                        "keywords_count": len(keywords),
                    },
                )

            except Exception as e:
                session.rollback()
                logger.error(f"Failed to update enhanced registry: {e}")
                raise

    def _infer_content_type(self, parsed_doc) -> str:
        """Infer content type from document analysis."""
        title_lower = (
            parsed_doc.metadata.title.lower() if parsed_doc.metadata.title else ""
        )
        # content_lower = parsed_doc.content.lower()  # Commented for future use

        # Check for form indicators
        form_indicators = ["form", "consent", "checklist", "template", "agreement"]
        if any(indicator in title_lower for indicator in form_indicators):
            return "form"

        # Check for protocol indicators
        protocol_indicators = [
            "protocol",
            "procedure",
            "algorithm",
            "pathway",
            "guideline",
        ]
        if any(indicator in title_lower for indicator in protocol_indicators):
            return "protocol"

        # Check for contact indicators
        contact_indicators = ["directory", "contact", "phone", "pager", "on-call"]
        if any(indicator in title_lower for indicator in contact_indicators):
            return "contact"

        # Default to reference
        return "reference"

    def _generate_keywords(self, parsed_doc) -> List[str]:
        """Generate keywords for document lookup."""
        keywords = []

        # From title
        if parsed_doc.metadata.title:
            title_words = parsed_doc.metadata.title.lower().split()
            keywords.extend([w for w in title_words if len(w) > 2])

        # From filename
        filename_words = (
            Path(parsed_doc.filename).stem.replace("_", " ").replace("-", " ").split()
        )
        keywords.extend([w.lower() for w in filename_words if len(w) > 2])

        # From medical specialties
        keywords.extend(parsed_doc.metadata.medical_specialties)

        # From tags
        keywords.extend(parsed_doc.metadata.tags)

        # Common medical terms
        content_lower = parsed_doc.content.lower()
        medical_terms = [
            "stemi",
            "mi",
            "stroke",
            "sepsis",
            "trauma",
            "cardiac",
            "respiratory",
            "emergency",
            "protocol",
            "consent",
            "form",
            "medication",
            "dosage",
        ]

        for term in medical_terms:
            if term in content_lower:
                keywords.append(term)

        return list(set(keywords))  # Remove duplicates

    def _generate_display_name(self, parsed_doc) -> str:
        """Generate human-readable display name."""
        if parsed_doc.metadata.title:
            return parsed_doc.metadata.title

        # Clean up filename
        name = Path(parsed_doc.filename).stem
        name = name.replace("_", " ").replace("-", " ")
        return name.title()

    def _calculate_priority(self, parsed_doc) -> int:
        """Calculate document priority for ordering."""
        priority = 0

        # High priority for emergency protocols
        content_lower = parsed_doc.content.lower()
        if any(
            term in content_lower
            for term in ["emergency", "stat", "critical", "urgent"]
        ):
            priority += 10

        # Medium priority for common procedures
        if any(
            term in content_lower for term in ["stemi", "stroke", "trauma", "sepsis"]
        ):
            priority += 5

        # Priority for forms
        if "form" in parsed_doc.metadata.tags:
            priority += 3

        return priority

    def _should_be_quick_access(self, parsed_doc) -> bool:
        """Determine if document should be in quick access."""
        # Common forms and critical protocols
        quick_access_terms = [
            "consent",
            "form",
            "emergency",
            "stat",
            "critical",
            "stemi",
            "stroke",
            "trauma",
            "sepsis",
            "cardiac arrest",
        ]

        content_lower = parsed_doc.content.lower()
        title_lower = (
            parsed_doc.metadata.title.lower() if parsed_doc.metadata.title else ""
        )

        return any(
            term in content_lower or term in title_lower for term in quick_access_terms
        )

    def _calculate_content_hash(self, content: str) -> str:
        """Calculate hash of content for deduplication."""
        import hashlib

        return hashlib.sha256(content.encode()).hexdigest()


async def process_document(file_path: str, content_type: Optional[str] = None) -> bool:
    """Process a single document (public interface)."""
    processor = DocumentProcessor()
    return await processor.process_document(file_path, content_type)


async def process_directory(
    directory_path: str, content_type: Optional[str] = None
) -> int:
    """Process all documents in a directory."""
    processor = DocumentProcessor()
    processed_count = 0

    path = Path(directory_path)
    if not path.exists():
        logger.error(f"Directory not found: {directory_path}")
        return 0

    # Find all document files
    supported_extensions = {".pdf", ".docx", ".txt", ".md"}
    files = []

    for file_path in path.rglob("*"):
        if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
            files.append(file_path)

    logger.info(f"Found {len(files)} documents to process")

    # Process files
    for file_path in files:
        try:
            success = await processor.process_document(str(file_path), content_type)
            if success:
                processed_count += 1
        except Exception as e:
            logger.error(f"Failed to process {file_path}: {e}")

    logger.info(f"Processed {processed_count}/{len(files)} documents successfully")
    return processed_count


async def ingestion_worker(
    source_path: str, content_type: Optional[str] = None, watch: bool = False
) -> None:
    """Main ingestion worker."""
    logger.info(
        "Starting ingestion worker",
        extra_fields={
            "source_path": source_path,
            "content_type": content_type,
            "watch": watch,
        },
    )

    # Process existing files
    if Path(source_path).is_file():
        await process_document(source_path, content_type)
    else:
        await process_directory(source_path, content_type)

    # Watch for new files if requested
    if watch:
        logger.info("Watching for new files...")
        # TODO: Implement file watching
        await asyncio.sleep(1)


def main():
    """CLI entry point for ingestion worker."""
    parser = argparse.ArgumentParser(description="ED Bot v8 Document Ingestion")
    parser.add_argument(
        "command", choices=["run", "process"], help="Command to execute"
    )
    parser.add_argument("--path", required=True, help="Path to document or directory")
    parser.add_argument("--type", help="Content type (form|protocol|contact|reference)")
    parser.add_argument("--watch", action="store_true", help="Watch for new files")
    parser.add_argument(
        "--batch", action="store_true", help="Process directory in batch"
    )

    args = parser.parse_args()

    if args.command == "run":
        asyncio.run(
            ingestion_worker(
                source_path=args.path, content_type=args.type, watch=args.watch
            )
        )
    elif args.command == "process":
        if args.batch:
            result = asyncio.run(process_directory(args.path, args.type))
            print(f"Processed {result} documents")
        else:
            result = asyncio.run(process_document(args.path, args.type))
            print(f"Processing {'succeeded' if result else 'failed'}")


if __name__ == "__main__":
    main()
