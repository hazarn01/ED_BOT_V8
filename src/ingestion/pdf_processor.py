"""Enhanced PDF processor with position tracking for source highlighting (PRP 17)."""

from pathlib import Path
from typing import Dict, List, Optional

import fitz  # PyMuPDF

from src.config import settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


class PDFProcessor:
    """Process PDFs with page and span tracking for source highlighting."""

    def __init__(self):
        self.chunk_size = getattr(settings, 'chunk_size', 500)
        self.overlap = getattr(settings, 'chunk_overlap', 50)

    def extract_with_positions(self, file_path: str) -> List[Dict]:
        """Extract text with position information from PDF."""
        logger.info(f"Extracting PDF with positions: {file_path}")
        
        doc = fitz.open(file_path)
        pages_data = []
        
        for page_num, page in enumerate(doc, start=1):
            # Extract text with positions
            blocks = page.get_text("dict")
            page_text = ""
            text_spans = []
            
            for block in blocks["blocks"]:
                if block["type"] == 0:  # Text block
                    for line in block["lines"]:
                        line_text = ""
                        for span in line["spans"]:
                            span_text = span["text"]
                            span_start = len(page_text)
                            span_end = span_start + len(span_text)
                            
                            text_spans.append({
                                "text": span_text,
                                "page_start": span_start,
                                "page_end": span_end,
                                "bbox": span["bbox"],  # (x0, y0, x1, y1)
                                "font": span["font"],
                                "size": span["size"],
                                "flags": span["flags"],
                                "color": span["color"]
                            })
                            
                            line_text += span_text
                            page_text += span_text
                        page_text += "\n"
                        
            pages_data.append({
                "page_number": page_num,
                "text": page_text,
                "spans": text_spans,
                "page_bbox": page.rect,
                "total_chars": len(page_text),
                "page_width": page.rect.width,
                "page_height": page.rect.height
            })
            
        doc.close()
        
        logger.info(f"Extracted {len(pages_data)} pages with position data")
        return pages_data
        
    def create_chunks_with_positions(
        self,
        pages_data: List[Dict],
        chunk_size: Optional[int] = None,
        overlap: Optional[int] = None
    ) -> List[Dict]:
        """Create chunks preserving position information."""
        chunk_size = chunk_size or self.chunk_size
        overlap = overlap or self.overlap
        
        chunks = []
        document_offset = 0
        chunk_index = 0
        
        for page_data in pages_data:
            page_text = page_data["text"]
            page_num = page_data["page_number"]
            
            # Chunk the page text
            for i in range(0, len(page_text), chunk_size - overlap):
                chunk_text = page_text[i:i + chunk_size]
                
                if len(chunk_text.strip()) < 10:  # Skip very short chunks
                    continue
                
                # Calculate positions
                page_span_start = i
                page_span_end = min(i + chunk_size, len(page_text))
                doc_span_start = document_offset + i
                doc_span_end = document_offset + page_span_end
                
                # Find bounding box for this chunk (approximate)
                chunk_bbox = self._calculate_chunk_bbox(
                    page_data["spans"],
                    page_span_start,
                    page_span_end
                )
                
                # Analyze chunk content for medical categorization
                analysis = self._analyze_chunk_content(chunk_text)
                
                chunks.append({
                    "chunk_index": chunk_index,
                    "text": chunk_text,
                    "page_number": page_num,
                    "page_span_start": page_span_start,
                    "page_span_end": page_span_end,
                    "document_span_start": doc_span_start,
                    "document_span_end": doc_span_end,
                    "bbox": chunk_bbox,
                    "chunk_type": analysis.get("chunk_type", "text"),
                    "medical_category": analysis.get("medical_category"),
                    "urgency_level": analysis.get("urgency_level", "routine"),
                    "contains_contact": analysis.get("contains_contact", False),
                    "contains_dosage": analysis.get("contains_dosage", False),
                    "metadata": {
                        "page_total_chars": page_data["total_chars"],
                        "chunk_method": "sliding_window",
                        "page_width": page_data["page_width"],
                        "page_height": page_data["page_height"]
                    }
                })
                
                chunk_index += 1
                
            document_offset += len(page_text)
            
        logger.info(f"Created {len(chunks)} chunks with position tracking")
        return chunks
        
    def _calculate_chunk_bbox(
        self,
        spans: List[Dict],
        start: int,
        end: int
    ) -> Optional[Dict]:
        """Calculate bounding box for chunk based on character positions."""
        relevant_spans = []
        current_pos = 0
        
        for span in spans:
            span_end = current_pos + len(span["text"])
            if current_pos < end and span_end > start:
                relevant_spans.append(span["bbox"])
            current_pos = span_end
            
        if not relevant_spans:
            return None
            
        # Union of all span bboxes (x0, y0, x1, y1)
        x0 = min(bbox[0] for bbox in relevant_spans)
        y0 = min(bbox[1] for bbox in relevant_spans)
        x1 = max(bbox[2] for bbox in relevant_spans)
        y1 = max(bbox[3] for bbox in relevant_spans)
        
        return {
            "x": x0, 
            "y": y0, 
            "width": x1 - x0, 
            "height": y1 - y0,
            "x1": x1,
            "y1": y1
        }
    
    def _analyze_chunk_content(self, text: str) -> Dict[str, any]:
        """Analyze chunk content for medical context."""
        analysis = {
            "chunk_type": "text",
            "medical_category": None,
            "urgency_level": "routine",
            "contains_contact": False,
            "contains_dosage": False,
        }

        text_lower = text.lower()

        # Detect chunk types based on formatting/content
        if any(word in text_lower for word in ["title", "heading", "protocol", "procedure"]):
            analysis["chunk_type"] = "header"
        elif any(word in text_lower for word in ["table", "list", "step", "1.", "2.", "3."]):
            analysis["chunk_type"] = "list"
        elif "table" in text_lower or "|" in text:
            analysis["chunk_type"] = "table"

        # Detect medical categories
        category_keywords = {
            "cardiology": [
                "heart", "cardiac", "stemi", "mi", "chest pain", 
                "ecg", "ekg", "coronary", "artery", "balloon"
            ],
            "emergency": [
                "emergency", "urgent", "stat", "critical", 
                "resuscitation", "code", "trauma"
            ],
            "pharmacy": [
                "dose", "dosage", "mg", "ml", "medication", 
                "drug", "infusion", "units", "mcg"
            ],
            "neurology": [
                "stroke", "cva", "seizure", "neurologic", 
                "brain", "tpa", "hemorrhage"
            ],
            "respiratory": [
                "respiratory", "copd", "asthma", "pneumonia", 
                "oxygen", "ventilator", "airway"
            ],
        }

        for category, keywords in category_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                analysis["medical_category"] = category
                break

        # Detect urgency level
        if any(word in text_lower for word in ["stat", "emergency", "critical", "urgent", "immediately"]):
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
            or "contact" in text_lower
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

    def process_pdf_for_highlighting(self, file_path: str) -> Dict:
        """Process PDF specifically for highlighting capability."""
        try:
            # Extract with positions
            pages_data = self.extract_with_positions(file_path)
            
            # Create chunks with position tracking
            chunks = self.create_chunks_with_positions(pages_data)
            
            # Extract basic metadata
            path = Path(file_path)
            doc = fitz.open(file_path)
            metadata = {
                "filename": path.name,
                "page_count": doc.page_count,
                "title": doc.metadata.get("title", path.stem),
                "author": doc.metadata.get("author", ""),
                "subject": doc.metadata.get("subject", ""),
                "keywords": doc.metadata.get("keywords", ""),
            }
            doc.close()
            
            # Extract full text for content analysis
            full_text = "\n\n".join([page["text"] for page in pages_data])
            
            return {
                "filename": path.name,
                "content": full_text,
                "chunks": chunks,
                "metadata": metadata,
                "pages_data": pages_data,
                "highlighting_enabled": True
            }
            
        except Exception as e:
            logger.error(f"PDF highlighting processing failed for {file_path}: {e}")
            raise

    def extract_text_from_spans(self, spans: List[Dict], start_char: int, end_char: int) -> str:
        """Extract text from specific character range using span data."""
        text_parts = []
        current_pos = 0
        
        for span in spans:
            span_start = current_pos
            span_end = current_pos + len(span["text"])
            
            # Check if this span overlaps with our range
            if span_start < end_char and span_end > start_char:
                # Calculate the part of the span we want
                extract_start = max(0, start_char - span_start)
                extract_end = min(len(span["text"]), end_char - span_start)
                
                if extract_end > extract_start:
                    text_parts.append(span["text"][extract_start:extract_end])
            
            current_pos = span_end
            
        return "".join(text_parts)