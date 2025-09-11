"""
Enhanced Document Processor - Connects existing unstructured and langextract infrastructure
Following PRP: Fix ED Bot v8 Comprehensive Issues - Phase 3

This processor combines UnstructuredRunner for text extraction with 
LangExtractRunner for entity extraction using the existing infrastructure.
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

from src.ingestion.unstructured_runner import UnstructuredRunner
from src.ingestion.langextract_runner import LangExtractRunner
from src.models.document_models import ParsedDocument
from src.utils.logging import get_logger

logger = get_logger(__name__)


class EnhancedDocumentProcessor:
    """Connects existing extraction infrastructure for comprehensive document processing."""
    
    def __init__(self):
        self.unstructured_runner = UnstructuredRunner()  # Already implemented
        self.langextract_runner = LangExtractRunner()    # Already implemented
        
        logger.info(
            "EnhancedDocumentProcessor initialized",
            extra_fields={
                "unstructured_available": hasattr(self.unstructured_runner, 'parse_document'),
                "langextract_available": self.langextract_runner.enabled
            }
        )
    
    async def process_document(self, file_path: Path) -> ParsedDocument:
        """Extract text and entities using existing runners."""
        
        logger.info(
            "Starting enhanced document processing",
            extra_fields={
                "file_path": str(file_path),
                "file_size": file_path.stat().st_size if file_path.exists() else 0
            }
        )
        
        try:
            # Phase 1: Use existing UnstructuredRunner for text extraction
            parsed_doc = await self.unstructured_runner.parse_document(str(file_path))
            
            # Phase 2: Use existing LangExtractRunner for entity extraction  
            entities = await self.langextract_runner.extract_entities(
                text=parsed_doc.content,
                document_id=parsed_doc.filename
            )
            
            # Phase 3: Enhance chunks with entity information
            enhanced_chunks = await self._enhance_chunks_with_entities(
                parsed_doc.chunks, entities
            )
            parsed_doc.chunks = enhanced_chunks
            
            # Phase 4: Attach extracted entities to document
            # Store entities in the document's tables field as structured data
            # (This is a temporary approach until ParsedDocument is extended)
            entity_summary = {
                "type": "entities", 
                "text": f"Extracted {len(entities)} entities",
                "metadata": {
                    "entities": entities,
                    "entity_types": list(set(e.get('entity_type') for e in entities)),
                    "extraction_timestamp": datetime.utcnow().isoformat()
                }
            }
            
            # Add to tables list (which already supports arbitrary structured data)
            if not parsed_doc.tables:
                parsed_doc.tables = []
            parsed_doc.tables.append(entity_summary)
            
            logger.info(
                "Enhanced document processing completed",
                extra_fields={
                    "filename": parsed_doc.filename,
                    "content_length": len(parsed_doc.content),
                    "chunk_count": len(parsed_doc.chunks),
                    "entity_count": len(entities),
                    "table_count": len(parsed_doc.tables),
                    "page_count": parsed_doc.page_count
                }
            )
            
            return parsed_doc
            
        except Exception as e:
            logger.error(
                f"Enhanced document processing failed: {e}",
                extra_fields={"file_path": str(file_path)}
            )
            raise

    async def _enhance_chunks_with_entities(
        self, chunks: List[Dict[str, Any]], entities: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Enhance chunks with entity information for better retrieval."""
        
        enhanced_chunks = []
        
        for chunk_info in chunks:
            chunk_text = chunk_info.get('text', '')
            
            # Find entities that appear in this chunk
            chunk_entities = []
            for entity in entities:
                evidence_text = entity.get('payload', {}).get('evidence_text', '')
                # Simple overlap check - could be made more sophisticated
                if evidence_text and evidence_text.lower() in chunk_text.lower():
                    chunk_entities.append({
                        'type': entity.get('entity_type'),
                        'payload': entity.get('payload'),
                        'confidence': entity.get('confidence', 0.8)
                    })
            
            # Enhance the chunk with entity information
            enhanced_chunk = chunk_info.copy()
            enhanced_chunk['entities'] = chunk_entities
            enhanced_chunk['entity_count'] = len(chunk_entities)
            
            # Update medical flags based on entities
            entity_types = [e['type'] for e in chunk_entities]
            enhanced_chunk['contains_contact'] = 'contact' in entity_types
            enhanced_chunk['contains_dosage'] = 'dosage' in entity_types
            enhanced_chunk['contains_protocol'] = 'protocol_step' in entity_types
            enhanced_chunk['contains_criteria'] = 'criteria' in entity_types
            enhanced_chunk['contains_timing'] = 'timing' in entity_types
            
            enhanced_chunks.append(enhanced_chunk)
        
        logger.info(
            "Chunks enhanced with entity information",
            extra_fields={
                "chunk_count": len(enhanced_chunks),
                "chunks_with_entities": sum(1 for c in enhanced_chunks if c['entity_count'] > 0)
            }
        )
        
        return enhanced_chunks

    async def get_processing_capabilities(self) -> Dict[str, Any]:
        """Get information about processing capabilities."""
        return {
            "text_extraction": {
                "available": hasattr(self.unstructured_runner, 'parse_document'),
                "engine": "unstructured",
                "features": ["pdf", "docx", "tables", "chunking", "medical_analysis"]
            },
            "entity_extraction": {
                "available": self.langextract_runner.enabled,
                "engine": "langextract",
                "entity_types": ["contact", "dosage", "protocol_step", "criteria", "timing"]
            },
            "supported_formats": [".pdf", ".docx", ".doc", ".txt"],
            "medical_optimized": True
        }