import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

try:
    from unstructured.chunking.title import chunk_by_title
    from unstructured.partition.auto import partition

    # from unstructured.staging.base import elements_to_json  # Commented for future use
    UNSTRUCTURED_AVAILABLE = True
except ImportError:
    UNSTRUCTURED_AVAILABLE = False

from src.config import settings
from src.models.document_models import DocumentMetadata, ParsedDocument
from src.utils.logging import get_logger
from src.utils.observability import track_latency

logger = get_logger(__name__)


class UnstructuredRunner:
    """Document parsing using Unstructured library."""

    def __init__(self):
        if not UNSTRUCTURED_AVAILABLE:
            logger.error(
                "Unstructured library not available. Install with: pip install 'unstructured[pdf,ocr]'"
            )
            raise ImportError("Unstructured library required for document parsing")

        self.chunk_size = settings.chunk_size
        self.chunk_overlap = settings.chunk_overlap
        logger.info(
            "UnstructuredRunner initialized",
            extra_fields={
                "chunk_size": self.chunk_size,
                "chunk_overlap": self.chunk_overlap,
            },
        )

    async def parse_document(self, file_path: str) -> ParsedDocument:
        """Parse document using Unstructured with medical-optimized settings."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Document not found: {file_path}")

        logger.info(
            "Starting document parse",
            extra_fields={"file_path": file_path, "file_size": path.stat().st_size},
        )

        try:
            with track_latency("unstructured_parse", {"file_type": path.suffix}):
                # Parse with high-resolution strategy for medical documents
                elements = partition(
                    filename=str(path),
                    strategy="hi_res",
                    infer_table_structure=True,
                    include_page_breaks=True,
                    include_metadata=True,
                    # OCR settings for scanned medical documents
                    ocr_languages=["eng"],
                    # Table extraction is crucial for medical data
                    extract_images_in_pdf=False,  # Focus on text/tables
                    extract_image_block_types=["Image", "Table"],
                )

                # Extract text content and metadata
                full_text = self._extract_text_from_elements(elements)
                metadata = self._extract_document_metadata(elements, path)
                tables = self._extract_tables_from_elements(elements)

                # Create semantic chunks
                chunks = await self._create_chunks(elements)

                # Calculate file hash for deduplication (commented for future use)
                # file_hash = self._calculate_file_hash(file_path)

                parsed_doc = ParsedDocument(
                    filename=path.name,
                    content=full_text,
                    chunks=chunks,
                    metadata=metadata,
                    tables=tables,
                    images=[],  # Not extracting images for now
                    page_count=self._get_page_count(elements),
                    parse_warnings=[],
                )

                logger.info(
                    "Document parsed successfully",
                    extra_fields={
                        "filename": path.name,
                        "content_length": len(full_text),
                        "chunk_count": len(chunks),
                        "table_count": len(tables),
                        "page_count": parsed_doc.page_count,
                    },
                )

                return parsed_doc

        except Exception as e:
            logger.error(
                f"Document parsing failed: {e}", extra_fields={"file_path": file_path}
            )
            raise

    def _extract_text_from_elements(self, elements) -> str:
        """Extract clean text from parsed elements."""
        text_parts = []
        for element in elements:
            if hasattr(element, "text") and element.text:
                text_parts.append(element.text.strip())

        return "\n\n".join(text_parts)

    def _extract_document_metadata(self, elements, path: Path) -> DocumentMetadata:
        """Extract metadata from document elements."""
        metadata = DocumentMetadata()

        # Try to extract title from first heading or filename
        for element in elements[:5]:  # Check first few elements
            if hasattr(element, "category") and element.category == "Title":
                metadata.title = element.text
                break

        if not metadata.title:
            metadata.title = path.stem.replace("_", " ").title()

        # Extract any date references
        file_stats = path.stat()
        metadata.effective_date = datetime.fromtimestamp(file_stats.st_mtime)

        # Medical specialties detection
        text_content = self._extract_text_from_elements(elements).lower()
        specialties = self._detect_medical_specialties(text_content)
        metadata.medical_specialties = specialties

        # Tags from content analysis
        tags = self._extract_content_tags(text_content)
        metadata.tags = tags

        return metadata

    def _extract_tables_from_elements(self, elements) -> List[Dict[str, Any]]:
        """Extract structured tables from elements."""
        tables = []

        for element in elements:
            if hasattr(element, "category") and element.category == "Table":
                table_data = {
                    "text": element.text if hasattr(element, "text") else "",
                    "metadata": element.metadata.to_dict()
                    if hasattr(element, "metadata")
                    else {},
                }

                # Try to parse table structure if available
                if hasattr(element, "metadata") and element.metadata:
                    if hasattr(element.metadata, "table_as_cells"):
                        table_data["cells"] = element.metadata.table_as_cells

                tables.append(table_data)

        return tables

    async def _create_chunks(self, elements) -> List[Dict[str, Any]]:
        """Create semantic chunks from elements."""
        try:
            # Use Unstructured's chunking
            chunks = chunk_by_title(
                elements,
                max_characters=self.chunk_size,
                new_after_n_chars=self.chunk_size - self.chunk_overlap,
                combine_text_under_n_chars=50,
            )

            chunk_data = []
            for i, chunk in enumerate(chunks):
                chunk_text = chunk.text if hasattr(chunk, "text") else str(chunk)

                # Extract metadata from chunk
                metadata = {}
                if hasattr(chunk, "metadata") and chunk.metadata:
                    chunk_metadata = chunk.metadata.to_dict()
                    metadata.update(chunk_metadata)

                # Analyze chunk content
                analysis = self._analyze_chunk_content(chunk_text)

                chunk_info = {
                    "chunk_index": i,
                    "text": chunk_text,
                    "chunk_type": getattr(chunk, "category", "text"),
                    "medical_category": analysis.get("medical_category"),
                    "urgency_level": analysis.get("urgency_level", "routine"),
                    "contains_contact": analysis.get("contains_contact", False),
                    "contains_dosage": analysis.get("contains_dosage", False),
                    "page_number": metadata.get("page_number"),
                    "metadata": metadata,
                }

                chunk_data.append(chunk_info)

            return chunk_data

        except Exception as e:
            logger.error(f"Chunking failed: {e}")
            # Fallback: simple text splitting
            return self._fallback_chunking(elements)

    def _analyze_chunk_content(self, text: str) -> Dict[str, Any]:
        """Analyze chunk content for medical context."""
        analysis = {
            "medical_category": None,
            "urgency_level": "routine",
            "contains_contact": False,
            "contains_dosage": False,
        }

        text_lower = text.lower()

        # Detect medical categories
        category_keywords = {
            "cardiology": [
                "heart",
                "cardiac",
                "stemi",
                "mi",
                "chest pain",
                "ecg",
                "ekg",
            ],
            "emergency": ["emergency", "urgent", "stat", "critical", "resuscitation"],
            "pharmacy": [
                "dose",
                "dosage",
                "mg",
                "ml",
                "medication",
                "drug",
                "infusion",
            ],
            "neurology": ["stroke", "cva", "seizure", "neurologic", "brain"],
            "trauma": ["trauma", "injury", "fracture", "bleeding", "wound"],
            "respiratory": ["respiratory", "copd", "asthma", "pneumonia", "oxygen"],
        }

        for category, keywords in category_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                analysis["medical_category"] = category
                break

        # Detect urgency level
        if any(
            word in text_lower
            for word in ["stat", "emergency", "critical", "urgent", "immediately"]
        ):
            analysis["urgency_level"] = "urgent"
        elif any(word in text_lower for word in ["priority", "asap", "prompt"]):
            analysis["urgency_level"] = "priority"

        # Detect contact information
        import re

        phone_pattern = r"\b(?:\(?\d{3}\)?[\s.-]?)?\d{3}[\s.-]?\d{4}\b"
        if (
            re.search(phone_pattern, text)
            or "pager" in text_lower
            or "on-call" in text_lower
        ):
            analysis["contains_contact"] = True

        # Detect dosage information
        dosage_patterns = [
            r"\d+\s*mg\b",
            r"\d+\s*ml\b",
            r"\d+\s*units?\b",
            r"\d+\s*mcg\b",
            r"\d+\s*g\b",
            r"\d+\s*L\b",
            r"\d+\s*cc\b",
        ]
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in dosage_patterns):
            analysis["contains_dosage"] = True

        return analysis

    def _detect_medical_specialties(self, text: str) -> List[str]:
        """Detect medical specialties from text content."""
        specialties = []

        specialty_indicators = {
            "cardiology": ["cardiology", "cardiac", "heart", "stemi", "mi", "coronary"],
            "emergency_medicine": [
                "emergency",
                "ed ",
                "emergency department",
                "trauma",
            ],
            "pharmacy": ["pharmacy", "medication", "drug", "dosage", "pharmaceutical"],
            "neurology": ["neurology", "stroke", "seizure", "neurologic", "cva"],
            "respiratory": ["pulmonary", "respiratory", "lung", "copd", "asthma"],
            "critical_care": ["icu", "critical care", "intensive care", "ventilator"],
        }

        for specialty, indicators in specialty_indicators.items():
            if any(indicator in text for indicator in indicators):
                specialties.append(specialty)

        return list(set(specialties))

    def _extract_content_tags(self, text: str) -> List[str]:
        """Extract content tags from text."""
        tags = []

        # Common medical document types
        tag_indicators = {
            "protocol": ["protocol", "procedure", "algorithm", "pathway"],
            "form": ["form", "consent", "checklist", "template"],
            "guideline": ["guideline", "recommendation", "criteria", "standard"],
            "policy": ["policy", "rule", "regulation", "requirement"],
            "contact": ["contact", "phone", "pager", "on-call", "directory"],
            "medication": ["medication", "drug", "dose", "prescription", "pharmacy"],
        }

        for tag, indicators in tag_indicators.items():
            if any(indicator in text for indicator in indicators):
                tags.append(tag)

        return list(set(tags))

    def _get_page_count(self, elements) -> int:
        """Get page count from elements."""
        max_page = 0
        for element in elements:
            if hasattr(element, "metadata") and element.metadata:
                page_num = getattr(element.metadata, "page_number", 0)
                if isinstance(page_num, int) and page_num > max_page:
                    max_page = page_num

        return max(max_page, 1)  # At least 1 page

    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA-256 hash of file for deduplication."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()

    def _fallback_chunking(self, elements) -> List[Dict[str, Any]]:
        """Fallback chunking if Unstructured chunking fails."""
        logger.warning("Using fallback text chunking")

        full_text = self._extract_text_from_elements(elements)
        chunks = []

        # Simple character-based chunking
        start = 0
        chunk_index = 0

        while start < len(full_text):
            end = min(start + self.chunk_size, len(full_text))
            chunk_text = full_text[start:end]

            chunks.append(
                {
                    "chunk_index": chunk_index,
                    "text": chunk_text,
                    "chunk_type": "text",
                    "medical_category": None,
                    "urgency_level": "routine",
                    "contains_contact": False,
                    "contains_dosage": False,
                    "page_number": None,
                    "metadata": {},
                }
            )

            start = end - self.chunk_overlap
            chunk_index += 1

        return chunks
