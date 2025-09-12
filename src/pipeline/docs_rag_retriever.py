"""
Document RAG Retrieval System - Fallback retrieval from docs folder
Uses advanced text processing to extract relevant content from PDF documents.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import re
import os
from dataclasses import dataclass
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)

@dataclass
class DocumentMatch:
    content: str
    filename: str
    confidence: float
    match_type: str
    source_section: str = ""

class DocsRAGRetriever:
    """Advanced RAG retrieval from docs folder with medical-aware processing."""
    
    def __init__(self, db: Session, docs_path: str = None):
        self.db = db
        self.docs_path = docs_path or self._find_docs_path()
        
        # Medical document priority mapping
        self.document_priority = {
            'ICH_Management_Protocol': 100,
            'Current_Protocol_ED_EVD_Placement': 95,
            'ED_sepsis_pathway': 90,
            'STEMI_Activation': 90,
            'STEMI': 90,
            'Hypoglycemia_EBP': 85,
            'Anaphylaxis_Guideline': 85,
            'GI_Bleed_Guideline': 80,
            'Pediatric_Asthma_Pathway': 75,
            'RETU_': 70,  # All RETU protocols
            'MSH_ED_Clinical_Guide': 65,
        }
        
        # Critical keywords that boost document relevance
        self.critical_keywords = {
            'icp': ['ICH_Management_Protocol', 'Current_Protocol_ED_EVD_Placement'],
            'ich': ['ICH_Management_Protocol', 'Current_Protocol_ED_EVD_Placement'],
            'intracranial': ['ICH_Management_Protocol', 'Current_Protocol_ED_EVD_Placement'],
            'evd': ['Current_Protocol_ED_EVD_Placement', 'ICH_Management_Protocol'],
            'external ventricular drain': ['Current_Protocol_ED_EVD_Placement'],
            'brain pressure': ['ICH_Management_Protocol', 'Current_Protocol_ED_EVD_Placement'],
            'stemi': ['STEMI_Activation', 'STEMI'],
            'sepsis': ['ED_sepsis_pathway'],
            'hypoglycemia': ['Hypoglycemia_EBP'],
            'glucose': ['Hypoglycemia_EBP'],
            'anaphylaxis': ['Anaphylaxis_Guideline'],
            'asthma': ['Pediatric_Asthma_Pathway', 'RETU_Asthma_Pathway'],
        }
    
    def _find_docs_path(self) -> str:
        """Find docs directory in the project."""
        current_dir = Path(__file__).parent
        for _ in range(5):
            docs_dir = current_dir / "docs"
            if docs_dir.exists():
                return str(docs_dir)
            current_dir = current_dir.parent
        
        # Fallback to relative path
        return "/Users/nimayh/Desktop/NH/V8/edbot-v8-fix-prp-44-comprehensive-code-quality/docs"
    
    def retrieve_from_docs(self, query: str, top_k: int = 3) -> List[DocumentMatch]:
        """
        Retrieve relevant content from docs folder using database and file analysis.
        """
        query_lower = query.lower()
        
        # Step 1: Try database retrieval first (fastest)
        db_matches = self._search_database_content(query, top_k)
        
        # Step 2: If database has good matches, use them
        if db_matches and any(match.confidence > 0.7 for match in db_matches):
            logger.info(f"✅ Found {len(db_matches)} high-confidence database matches")
            return db_matches[:top_k]
        
        # Step 3: Fallback to targeted document search
        targeted_docs = self._identify_target_documents(query_lower)
        file_matches = []
        
        for doc_name in targeted_docs[:5]:  # Limit to top 5 documents
            try:
                match = self._search_specific_document(query, doc_name)
                if match and match.confidence > 0.5:
                    file_matches.append(match)
            except Exception as e:
                logger.warning(f"Failed to search {doc_name}: {e}")
        
        # Combine and rank all matches
        all_matches = db_matches + file_matches
        all_matches.sort(key=lambda x: x.confidence, reverse=True)
        
        return all_matches[:top_k]
    
    def _search_database_content(self, query: str, top_k: int) -> List[DocumentMatch]:
        """Search database for relevant document content."""
        try:
            # Extract key terms for targeted search
            key_terms = self._extract_search_terms(query)
            
            if not key_terms:
                return []
            
            # Build enhanced database query with medical prioritization
            search_conditions = []
            params = {}
            
            for i, term in enumerate(key_terms[:5]):  # Limit terms
                param_name = f"term_{i}"
                search_conditions.append(f"dc.chunk_text ILIKE :{param_name}")
                params[param_name] = f"%{term}%"
            
            # Medical prioritization in SQL
            priority_cases = []
            for doc_pattern, priority in self.document_priority.items():
                priority_cases.append(f"WHEN d.filename ILIKE '%{doc_pattern}%' THEN {priority}")
            
            priority_case_sql = " ".join(priority_cases) if priority_cases else ""
            
            search_query = f"""
                SELECT 
                    dc.chunk_text,
                    d.filename,
                    LENGTH(dc.chunk_text) as content_length,
                    -- Medical document priority scoring
                    (CASE 
                        {priority_case_sql}
                        WHEN d.content_type IN ('protocol', 'guideline', 'criteria') THEN 80
                        WHEN dc.chunk_text ILIKE '%protocol%' THEN 75
                        WHEN dc.chunk_text ILIKE '%guideline%' THEN 70
                        ELSE 50 
                    END) as priority_score,
                    -- Term match scoring
                    (
                        {' + '.join([f"CASE WHEN dc.chunk_text ILIKE :{f'term_{i}'} THEN 1 ELSE 0 END" for i in range(len(key_terms[:5]))])}
                    ) as term_matches
                FROM document_chunks dc
                JOIN documents d ON dc.document_id = d.id
                WHERE ({' OR '.join(search_conditions)})
                AND LENGTH(dc.chunk_text) > 50
                ORDER BY 
                    priority_score DESC,
                    term_matches DESC,
                    content_length DESC
                LIMIT :limit
            """
            
            params["limit"] = top_k * 2  # Get extra results for filtering
            
            results = self.db.execute(text(search_query), params).fetchall()
            
            matches = []
            for result in results:
                content = result[0]
                filename = result[1]
                content_length = result[2]
                priority_score = result[3]
                term_matches = result[4]
                
                # Calculate confidence based on multiple factors
                confidence = self._calculate_content_confidence(
                    query, content, filename, priority_score, term_matches
                )
                
                if confidence > 0.3:  # Only return reasonable matches
                    matches.append(DocumentMatch(
                        content=content,
                        filename=filename,
                        confidence=confidence,
                        match_type="database",
                        source_section=self._extract_section_name(content)
                    ))
            
            logger.info(f"🔍 Database search returned {len(matches)} matches")
            return matches
            
        except Exception as e:
            logger.error(f"Database content search failed: {e}")
            return []
    
    def _identify_target_documents(self, query: str) -> List[str]:
        """Identify which documents are most likely to contain relevant information."""
        candidates = []
        
        # Check critical keywords for document targeting
        for keyword, target_docs in self.critical_keywords.items():
            if keyword in query:
                candidates.extend(target_docs)
        
        # Add general document patterns based on content
        if any(word in query for word in ['protocol', 'guideline', 'procedure']):
            candidates.extend(['MSH_ED_Clinical_Guide', 'Current_Protocol'])
        
        if any(word in query for word in ['retu', 'pathway']):
            candidates.extend(['RETU_'])
        
        if any(word in query for word in ['pediatric', 'child', 'peds']):
            candidates.extend(['Pediatric_', 'MSH_PED_', 'Peds_'])
        
        # Remove duplicates and sort by priority
        unique_candidates = list(set(candidates))
        
        # Sort by document priority
        def get_priority(doc_name):
            for pattern, priority in self.document_priority.items():
                if pattern in doc_name:
                    return priority
            return 0
        
        unique_candidates.sort(key=get_priority, reverse=True)
        
        return unique_candidates
    
    def _search_specific_document(self, query: str, doc_pattern: str) -> Optional[DocumentMatch]:
        """Search for content within a specific document pattern."""
        try:
            # Search database for specific document
            search_query = text("""
                SELECT dc.chunk_text, d.filename
                FROM document_chunks dc
                JOIN documents d ON dc.document_id = d.id
                WHERE d.filename ILIKE :doc_pattern
                AND LENGTH(dc.chunk_text) > 100
                ORDER BY LENGTH(dc.chunk_text) DESC
                LIMIT 5
            """)
            
            results = self.db.execute(search_query, {"doc_pattern": f"%{doc_pattern}%"}).fetchall()
            
            if not results:
                return None
            
            # Find best matching chunk
            best_match = None
            best_confidence = 0.0
            
            for result in results:
                content = result[0]
                filename = result[1]
                
                confidence = self._calculate_text_similarity(query, content)
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_match = DocumentMatch(
                        content=content,
                        filename=filename,
                        confidence=confidence,
                        match_type="document_targeted",
                        source_section=self._extract_section_name(content)
                    )
            
            return best_match
            
        except Exception as e:
            logger.error(f"Specific document search failed for {doc_pattern}: {e}")
            return None
    
    def _extract_search_terms(self, query: str) -> List[str]:
        """Extract meaningful search terms from query."""
        # Remove common stop words but keep medical terms
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'what', 'how', 'when', 'where', 'who', 'why', 'is', 'are'}
        
        # Extract terms
        terms = re.findall(r'\b\w+\b', query.lower())
        meaningful_terms = [term for term in terms 
                          if len(term) > 2 and term not in stop_words]
        
        return meaningful_terms
    
    def _calculate_content_confidence(self, query: str, content: str, filename: str, 
                                    priority_score: int, term_matches: int) -> float:
        """Calculate confidence score for database content match."""
        
        # Base confidence from term matches
        query_terms = self._extract_search_terms(query)
        if not query_terms:
            return 0.0
        
        base_confidence = term_matches / len(query_terms)
        
        # Priority boost
        priority_boost = min(priority_score / 100.0, 0.3)  # Max 30% boost
        
        # Content quality boost
        content_boost = 0.0
        if len(content) > 200:
            content_boost += 0.1
        if 'protocol' in content.lower() or 'guideline' in content.lower():
            content_boost += 0.1
        
        # Filename relevance boost
        filename_boost = 0.0
        for keyword in self._extract_search_terms(query):
            if keyword in filename.lower():
                filename_boost += 0.05
        
        total_confidence = min(base_confidence + priority_boost + content_boost + filename_boost, 0.95)
        
        return max(total_confidence, 0.0)
    
    def _calculate_text_similarity(self, query: str, content: str) -> float:
        """Calculate similarity between query and content text."""
        query_terms = set(self._extract_search_terms(query))
        content_terms = set(self._extract_search_terms(content))
        
        if not query_terms:
            return 0.0
        
        # Jaccard similarity
        intersection = query_terms & content_terms
        union = query_terms | content_terms
        
        jaccard = len(intersection) / len(union) if union else 0.0
        
        # Boost for exact phrase matches
        exact_boost = 0.0
        query_clean = re.sub(r'\W+', ' ', query.lower()).strip()
        content_clean = re.sub(r'\W+', ' ', content.lower()).strip()
        
        if query_clean in content_clean:
            exact_boost = 0.3
        
        return min(jaccard + exact_boost, 0.9)
    
    def _extract_section_name(self, content: str) -> str:
        """Extract section name from content for better attribution."""
        # Look for section headers or key phrases
        content_preview = content[:200]
        
        # Common medical section patterns
        section_patterns = [
            r'(\d+\.\s*[A-Z][^.]*)',  # Numbered sections
            r'([A-Z][A-Z\s]+:)',      # ALL CAPS headers
            r'(\*\*[^*]+\*\*)',       # Bold headers
            r'(Protocol|Guideline|Criteria|Management).*?[:.]',  # Protocol headers
        ]
        
        for pattern in section_patterns:
            matches = re.findall(pattern, content_preview)
            if matches:
                return matches[0].strip(':. ')
        
        return "Protocol Section"
    
    def get_docs_response(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Get a complete response from docs RAG retrieval.
        Returns formatted response ready for API.
        """
        matches = self.retrieve_from_docs(query, top_k=3)
        
        if not matches:
            return None
        
        # Use the best match as primary content
        primary_match = matches[0]
        
        # Format response with medical context
        response = self._format_docs_response(primary_match, matches[1:], query)
        
        # Extract sources
        sources = []
        seen_files = set()
        for match in matches:
            if match.filename not in seen_files:
                display_name = match.filename.replace('.pdf', '').replace('_', ' ').title()
                sources.append({
                    "display_name": display_name,
                    "filename": match.filename,
                    "pdf_path": match.filename
                })
                seen_files.add(match.filename)
        
        return {
            "response": response,
            "sources": sources,
            "confidence": primary_match.confidence,
            "query_type": self._infer_query_type(query),
            "has_real_content": True,
            "docs_rag_retrieval": True,
            "retrieval_method": primary_match.match_type
        }
    
    def _format_docs_response(self, primary_match: DocumentMatch, 
                            supporting_matches: List[DocumentMatch], query: str) -> str:
        """Format docs retrieval response with proper medical formatting."""
        
        query_lower = query.lower()
        
        # Add appropriate medical context headers
        if 'icp' in query_lower or 'ich' in query_lower:
            header = "🧠 **ICP/ICH Management Guidelines**\n\n"
        elif 'evd' in query_lower:
            header = "🔧 **EVD Placement Protocol**\n\n"
        elif 'stemi' in query_lower:
            header = "🚨 **STEMI Protocol**\n\n"
        elif 'sepsis' in query_lower:
            header = "🦠 **Sepsis Management**\n\n"
        else:
            header = "📋 **Clinical Guidelines**\n\n"
        
        # Format primary content
        content = primary_match.content
        if len(content) > 600:
            content = content[:600] + "..."
        
        response_parts = [header]
        
        if primary_match.source_section:
            response_parts.append(f"**{primary_match.source_section}:**\n")
        
        response_parts.append(content)
        
        # Add supporting information if available and high confidence
        if supporting_matches and supporting_matches[0].confidence > 0.6:
            response_parts.append("\n\n**Additional Context:**")
            support_content = supporting_matches[0].content[:300]
            response_parts.append(support_content + "...")
        
        # Add confidence indicator for lower confidence matches
        if primary_match.confidence < 0.7:
            response_parts.append(f"\n\n*Retrieved from documents with {primary_match.confidence:.0%} confidence - Please verify with current protocols*")
        
        return "\n".join(response_parts)
    
    def _infer_query_type(self, query: str) -> str:
        """Infer query type from content."""
        query_lower = query.lower()
        
        if any(word in query_lower for word in ['contact', 'phone', 'pager', 'call']):
            return 'contact'
        elif any(word in query_lower for word in ['form', 'document', 'consent']):
            return 'form'
        elif any(word in query_lower for word in ['protocol', 'procedure', 'steps']):
            return 'protocol'
        elif any(word in query_lower for word in ['criteria', 'score', 'guidelines']):
            return 'criteria'
        elif any(word in query_lower for word in ['dose', 'dosage', 'mg', 'medication']):
            return 'dosage'
        else:
            return 'summary'