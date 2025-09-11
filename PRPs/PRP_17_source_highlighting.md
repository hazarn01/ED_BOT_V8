# PRP 17: Source Highlighting Pipeline

## Problem Statement
Users need to see exactly where in source documents their answers come from. This requires capturing page numbers and text spans during ingestion, storing them with chunks, and including highlight information in responses for interactive verification.

## Success Criteria
- Page numbers and character spans stored for each chunk
- Response includes `highlighted_sources` with page/span info
- Existing response fields remain unchanged (backward compatible)
- Highlights accurately map to source PDF pages
- Performance impact <100ms per response

## Implementation Approach

### 1. Enhanced Chunk Model
```python
# src/models/entities.py (modifications)
class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    
    # Existing fields...
    
    # New highlighting fields
    page_number = Column(Integer, nullable=True)
    page_span_start = Column(Integer, nullable=True)  # Character offset in page
    page_span_end = Column(Integer, nullable=True)
    document_span_start = Column(Integer, nullable=True)  # Absolute offset in document
    document_span_end = Column(Integer, nullable=True)
    
    # Store bounding box for visual highlights (optional)
    bbox = Column(JSON, nullable=True)  # {"x": 10, "y": 20, "width": 100, "height": 50}
```

### 2. Migration
```sql
-- alembic/versions/xxx_add_highlight_fields.py
def upgrade():
    op.add_column('document_chunks', 
        sa.Column('page_number', sa.Integer(), nullable=True))
    op.add_column('document_chunks',
        sa.Column('page_span_start', sa.Integer(), nullable=True))
    op.add_column('document_chunks',
        sa.Column('page_span_end', sa.Integer(), nullable=True))
    op.add_column('document_chunks',
        sa.Column('document_span_start', sa.Integer(), nullable=True))
    op.add_column('document_chunks',
        sa.Column('document_span_end', sa.Integer(), nullable=True))
    op.add_column('document_chunks',
        sa.Column('bbox', sa.JSON(), nullable=True))
    
    # Index for page-based retrieval
    op.create_index('idx_chunk_page', 'document_chunks', 
                    ['document_id', 'page_number'])
```

### 3. Enhanced Ingestion with Span Tracking
```python
# src/ingestion/pdf_processor.py
from typing import List, Tuple
import fitz  # PyMuPDF for PDF processing

class PDFProcessor:
    """Process PDFs with page and span tracking"""
    
    def extract_with_positions(self, file_path: str) -> List[Dict]:
        """Extract text with position information"""
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
                                "size": span["size"]
                            })
                            
                            line_text += span_text
                            page_text += span_text
                        page_text += "\n"
                        
            pages_data.append({
                "page_number": page_num,
                "text": page_text,
                "spans": text_spans,
                "page_bbox": page.rect,
                "total_chars": len(page_text)
            })
            
        doc.close()
        return pages_data
        
    def create_chunks_with_positions(
        self,
        pages_data: List[Dict],
        chunk_size: int = 500,
        overlap: int = 50
    ) -> List[Dict]:
        """Create chunks preserving position information"""
        chunks = []
        document_offset = 0
        
        for page_data in pages_data:
            page_text = page_data["text"]
            page_num = page_data["page_number"]
            
            # Chunk the page text
            for i in range(0, len(page_text), chunk_size - overlap):
                chunk_text = page_text[i:i + chunk_size]
                
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
                
                chunks.append({
                    "content": chunk_text,
                    "page_number": page_num,
                    "page_span_start": page_span_start,
                    "page_span_end": page_span_end,
                    "document_span_start": doc_span_start,
                    "document_span_end": doc_span_end,
                    "bbox": chunk_bbox,
                    "metadata": {
                        "page_total_chars": page_data["total_chars"],
                        "chunk_method": "sliding_window"
                    }
                })
                
            document_offset += len(page_text)
            
        return chunks
        
    def _calculate_chunk_bbox(
        self,
        spans: List[Dict],
        start: int,
        end: int
    ) -> Dict:
        """Calculate bounding box for chunk"""
        relevant_spans = []
        current_pos = 0
        
        for span in spans:
            span_end = current_pos + len(span["text"])
            if current_pos < end and span_end > start:
                relevant_spans.append(span["bbox"])
            current_pos = span_end
            
        if not relevant_spans:
            return None
            
        # Union of all span bboxes
        x0 = min(bbox[0] for bbox in relevant_spans)
        y0 = min(bbox[1] for bbox in relevant_spans)
        x1 = max(bbox[2] for bbox in relevant_spans)
        y1 = max(bbox[3] for bbox in relevant_spans)
        
        return {"x": x0, "y": y0, "width": x1 - x0, "height": y1 - y0}
```

### 4. Source Highlighter Component
```python
# src/pipeline/source_highlighter.py
from typing import List, Dict, Optional
from dataclasses import dataclass

@dataclass
class HighlightedSource:
    """Source with highlight information"""
    document_id: str
    document_name: str
    page_number: int
    text_snippet: str
    highlight_spans: List[Tuple[int, int]]  # (start, end) positions
    bbox: Optional[Dict] = None
    confidence: float = 1.0
    
class SourceHighlighter:
    """Generate highlight information for retrieved chunks"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.enabled = settings.enable_highlights
        
    def generate_highlights(
        self,
        chunks: List[DocumentChunk],
        query: str,
        response_text: str
    ) -> List[HighlightedSource]:
        """Generate highlight information for response"""
        if not self.enabled:
            return []
            
        highlights = []
        
        for chunk in chunks:
            # Find matching passages in chunk
            matches = self._find_matches(chunk.content, response_text)
            
            if matches:
                # Create highlight with position info
                highlight = HighlightedSource(
                    document_id=str(chunk.document_id),
                    document_name=chunk.document.filename,
                    page_number=chunk.page_number or 0,
                    text_snippet=self._create_snippet(chunk.content, matches),
                    highlight_spans=matches,
                    bbox=chunk.bbox,
                    confidence=self._calculate_confidence(matches, chunk.content)
                )
                highlights.append(highlight)
                
        return highlights
        
    def _find_matches(
        self,
        chunk_text: str,
        response_text: str,
        min_match_length: int = 20
    ) -> List[Tuple[int, int]]:
        """Find matching text spans between chunk and response"""
        matches = []
        
        # Simple approach: find overlapping n-grams
        response_words = response_text.lower().split()
        chunk_lower = chunk_text.lower()
        
        for i in range(len(response_words) - 3):
            # Try different n-gram sizes
            for n in range(10, 3, -1):
                if i + n > len(response_words):
                    continue
                    
                ngram = " ".join(response_words[i:i+n])
                if len(ngram) < min_match_length:
                    continue
                    
                pos = chunk_lower.find(ngram)
                if pos != -1:
                    matches.append((pos, pos + len(ngram)))
                    break
                    
        # Merge overlapping matches
        return self._merge_overlapping_spans(matches)
        
    def _merge_overlapping_spans(
        self,
        spans: List[Tuple[int, int]]
    ) -> List[Tuple[int, int]]:
        """Merge overlapping or adjacent spans"""
        if not spans:
            return []
            
        sorted_spans = sorted(spans)
        merged = [sorted_spans[0]]
        
        for start, end in sorted_spans[1:]:
            last_start, last_end = merged[-1]
            if start <= last_end + 10:  # Allow small gaps
                merged[-1] = (last_start, max(end, last_end))
            else:
                merged.append((start, end))
                
        return merged
        
    def _create_snippet(
        self,
        text: str,
        spans: List[Tuple[int, int]],
        context_chars: int = 50
    ) -> str:
        """Create snippet with context around highlights"""
        if not spans:
            return text[:200] + "..."
            
        # Get bounds with context
        start = max(0, spans[0][0] - context_chars)
        end = min(len(text), spans[-1][1] + context_chars)
        
        snippet = text[start:end]
        
        # Add ellipsis if truncated
        if start > 0:
            snippet = "..." + snippet
        if end < len(text):
            snippet = snippet + "..."
            
        return snippet
        
    def _calculate_confidence(
        self,
        matches: List[Tuple[int, int]],
        text: str
    ) -> float:
        """Calculate confidence based on match coverage"""
        if not matches:
            return 0.0
            
        total_matched = sum(end - start for start, end in matches)
        return min(1.0, total_matched / 100)  # Normalize to max 1.0
```

### 5. Enhanced Response Schema
```python
# src/models/schemas.py (modifications)
from pydantic import BaseModel, Field

class HighlightedSourceSchema(BaseModel):
    """Schema for highlighted source"""
    document_id: str
    document_name: str
    page_number: int
    text_snippet: str
    highlight_spans: List[List[int]]  # JSON-friendly format
    bbox: Optional[Dict] = None
    confidence: float
    
class QueryResponse(BaseModel):
    """Enhanced response with highlights"""
    # Existing fields
    answer: str
    sources: List[str]
    confidence: float
    query_type: str
    
    # New highlight field (optional for backward compatibility)
    highlighted_sources: Optional[List[HighlightedSourceSchema]] = Field(
        default=None,
        description="Detailed source highlights with page/span info"
    )
    
    # Link to viewer
    viewer_url: Optional[str] = Field(
        default=None,
        description="URL to view highlighted sources"
    )
```

### 6. Integration with Router
```python
# src/pipeline/router.py (modifications)
class QueryRouter:
    def __init__(self, ...):
        # ...
        self.highlighter = SourceHighlighter(settings)
        
    async def route_query(self, query: str) -> QueryResponse:
        # Existing retrieval and generation...
        
        # Generate highlights if enabled
        highlighted_sources = None
        viewer_url = None
        
        if self.settings.enable_highlights:
            highlighted_sources = self.highlighter.generate_highlights(
                chunks=retrieved_chunks,
                query=query,
                response_text=answer
            )
            
            # Generate viewer URL if highlights exist
            if highlighted_sources:
                viewer_url = f"/api/v1/viewer?response_id={response_id}"
                
        return QueryResponse(
            answer=answer,
            sources=sources,
            confidence=confidence,
            query_type=query_type.value,
            highlighted_sources=highlighted_sources,
            viewer_url=viewer_url
        )
```

## Testing Strategy
```python
# tests/unit/test_source_highlighter.py
def test_highlight_generation():
    """Test highlight generation from chunks"""
    chunk = DocumentChunk(
        content="The STEMI protocol requires door-to-balloon time under 90 minutes.",
        page_number=5,
        page_span_start=100,
        page_span_end=200
    )
    
    response = "door-to-balloon time under 90 minutes"
    
    highlighter = SourceHighlighter(settings)
    highlights = highlighter.generate_highlights([chunk], "", response)
    
    assert len(highlights) == 1
    assert highlights[0].page_number == 5
    assert "door-to-balloon" in highlights[0].text_snippet
    
def test_span_merging():
    """Test overlapping span merger"""
    spans = [(10, 20), (15, 25), (30, 40)]
    merged = highlighter._merge_overlapping_spans(spans)
    assert merged == [(10, 25), (30, 40)]
```

## Performance Considerations
- Lazy loading of highlight data (only when requested)
- Cache highlight calculations for repeated queries
- Async processing where possible
- Index on page_number for fast page-based retrieval

## Rollback Plan
1. Set `ENABLE_HIGHLIGHTS=false`
2. Response continues without `highlighted_sources` field
3. Existing consumers unaffected
4. Can drop new columns if needed (data in separate columns)