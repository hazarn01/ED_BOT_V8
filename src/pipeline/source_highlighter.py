"""Source highlighting component for generating highlight information from retrieved chunks (PRP 17)."""

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from src.config.settings import Settings
from src.models.entities import DocumentChunk
from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class HighlightedSource:
    """Source with highlight information."""
    document_id: str
    document_name: str
    page_number: int
    text_snippet: str
    highlight_spans: List[Tuple[int, int]]  # (start, end) positions
    bbox: Optional[Dict] = None
    confidence: float = 1.0


class SourceHighlighter:
    """Generate highlight information for retrieved chunks."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.enabled = getattr(settings, 'enable_highlights', False)
        
    def generate_highlights(
        self,
        chunks: List[DocumentChunk],
        query: str,
        response_text: str
    ) -> List[HighlightedSource]:
        """Generate highlight information for response."""
        if not self.enabled:
            return []
            
        highlights = []
        
        logger.info(f"Generating highlights for {len(chunks)} chunks")
        
        for chunk in chunks:
            try:
                # Find matching passages in chunk
                matches = self._find_matches(chunk.chunk_text, response_text)
                
                if matches:
                    # Create highlight with position info
                    highlight = HighlightedSource(
                        document_id=str(chunk.document_id),
                        document_name=chunk.document.filename,
                        page_number=chunk.page_number or 0,
                        text_snippet=self._create_snippet(chunk.chunk_text, matches),
                        highlight_spans=matches,
                        bbox=chunk.bbox,
                        confidence=self._calculate_confidence(matches, chunk.chunk_text)
                    )
                    highlights.append(highlight)
                    
            except Exception as e:
                logger.error(f"Failed to generate highlight for chunk {chunk.id}: {e}")
                continue
                
        logger.info(f"Generated {len(highlights)} highlights")
        return highlights
        
    def _find_matches(
        self,
        chunk_text: str,
        response_text: str,
        min_match_length: int = 15
    ) -> List[Tuple[int, int]]:
        """Find matching text spans between chunk and response."""
        matches = []
        
        # Clean texts for comparison
        chunk_clean = self._clean_text(chunk_text)
        response_clean = self._clean_text(response_text)
        
        response_words = response_clean.split()
        chunk_lower = chunk_clean
        
        # Try different n-gram sizes (from longer to shorter)
        for i in range(len(response_words) - 2):
            # Try different n-gram sizes
            for n in range(min(15, len(response_words) - i), 3, -1):
                if i + n > len(response_words):
                    continue
                    
                ngram = " ".join(response_words[i:i+n])
                if len(ngram) < min_match_length:
                    continue
                    
                # Look for this n-gram in the chunk
                pos = chunk_lower.find(ngram)
                if pos != -1:
                    # Map back to original chunk positions
                    original_start, original_end = self._map_to_original_positions(
                        chunk_text, chunk_clean, pos, pos + len(ngram)
                    )
                    
                    if original_start != -1:
                        matches.append((original_start, original_end))
                        break
                        
        # Merge overlapping matches
        return self._merge_overlapping_spans(matches)
    
    def _clean_text(self, text: str) -> str:
        """Clean text for matching (normalize spaces, remove special chars)."""
        # Replace multiple whitespace with single space
        cleaned = re.sub(r'\s+', ' ', text)
        # Remove special characters but keep medical terms
        cleaned = re.sub(r'[^\w\s\-\.]', ' ', cleaned)
        # Convert to lowercase for matching
        return cleaned.lower().strip()
    
    def _map_to_original_positions(
        self,
        original_text: str,
        clean_text: str, 
        clean_start: int,
        clean_end: int
    ) -> Tuple[int, int]:
        """Map positions from cleaned text back to original text."""
        try:
            # Simple approach: find the text in original
            clean_substring = clean_text[clean_start:clean_end]
            
            # Look for similar pattern in original text
            # This is approximate but should work for most cases
            original_lower = original_text.lower()
            
            # Try to find the substring with some flexibility
            for start_offset in range(max(0, clean_start - 10), min(len(original_lower), clean_start + 10)):
                for end_offset in range(max(clean_end - 10, start_offset + len(clean_substring) - 10), 
                                     min(len(original_lower) + 1, clean_end + 10)):
                    candidate = self._clean_text(original_text[start_offset:end_offset])
                    if candidate == clean_substring:
                        return start_offset, end_offset
            
            # Fallback: proportional mapping
            ratio = len(original_text) / len(clean_text) if clean_text else 1
            orig_start = int(clean_start * ratio)
            orig_end = int(clean_end * ratio)
            
            # Ensure bounds
            orig_start = max(0, min(orig_start, len(original_text) - 1))
            orig_end = max(orig_start + 1, min(orig_end, len(original_text)))
            
            return orig_start, orig_end
            
        except Exception as e:
            logger.warning(f"Failed to map positions: {e}")
            return -1, -1
        
    def _merge_overlapping_spans(
        self,
        spans: List[Tuple[int, int]]
    ) -> List[Tuple[int, int]]:
        """Merge overlapping or adjacent spans."""
        if not spans:
            return []
            
        sorted_spans = sorted(spans)
        merged = [sorted_spans[0]]
        
        for start, end in sorted_spans[1:]:
            last_start, last_end = merged[-1]
            if start <= last_end + 20:  # Allow small gaps (20 chars)
                merged[-1] = (last_start, max(end, last_end))
            else:
                merged.append((start, end))
                
        return merged
        
    def _create_snippet(
        self,
        text: str,
        spans: List[Tuple[int, int]],
        context_chars: int = 100
    ) -> str:
        """Create snippet with context around highlights."""
        if not spans:
            return text[:300] + "..." if len(text) > 300 else text
            
        # Get bounds with context
        start = max(0, spans[0][0] - context_chars)
        end = min(len(text), spans[-1][1] + context_chars)
        
        # Try to break at word boundaries
        if start > 0:
            space_pos = text.find(' ', start)
            if space_pos != -1 and space_pos - start < 20:
                start = space_pos + 1
                
        if end < len(text):
            space_pos = text.rfind(' ', start, end)
            if space_pos != -1 and end - space_pos < 20:
                end = space_pos
        
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
        """Calculate confidence based on match coverage."""
        if not matches:
            return 0.0
            
        total_matched = sum(end - start for start, end in matches)
        text_length = len(text)
        
        if text_length == 0:
            return 0.0
        
        # Base confidence on coverage
        coverage = total_matched / text_length
        
        # Boost confidence for multiple matches
        match_boost = min(0.3, len(matches) * 0.1)
        
        # Final confidence (capped at 1.0)
        confidence = min(1.0, coverage * 2 + match_boost)
        
        return round(confidence, 2)
        
    def get_highlights_for_documents(
        self,
        document_ids: List[str],
        query: str,
        response_text: str
    ) -> Dict[str, List[HighlightedSource]]:
        """Get highlights grouped by document ID."""
        
        highlights_by_doc = {}
        
        # This would need database access - simplified for now
        # In practice, this would query the database for chunks by document IDs
        # and generate highlights for each
        
        return highlights_by_doc
        
    def enable_highlights(self):
        """Enable highlighting for this session."""
        self.enabled = True
        
    def disable_highlights(self):
        """Disable highlighting for this session."""
        self.enabled = False