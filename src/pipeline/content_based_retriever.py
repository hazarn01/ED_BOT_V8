"""
Content-Based Retriever - Always returns ACTUAL document content, never templates
PRP-48: Fix retrieval to use real database content
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy import text, and_, or_
from sqlalchemy.orm import Session
import re

logger = logging.getLogger(__name__)

class ContentBasedRetriever:
    """Retriever that ALWAYS returns actual document content from database."""
    
    def __init__(self, db: Session):
        self.db = db
        logger.info("✅ ContentBasedRetriever initialized - will return REAL content only")
    
    def get_medical_response(self, query: str) -> Dict[str, Any]:
        """Get medical response using ACTUAL document content."""
        query_lower = query.lower()
        
        # Step 1: Identify query type and key terms
        query_type = self._identify_query_type(query_lower)
        key_terms = self._extract_key_terms(query)
        
        logger.info(f"🔍 Query: '{query}' | Type: {query_type} | Terms: {key_terms}")
        
        # Step 2: Find the most relevant document(s)
        documents = self._find_relevant_documents(key_terms, query_type)
        
        if not documents:
            logger.warning(f"⚠️ No documents found for: {query}")
            return self._no_content_response(query)
        
        # Step 3: Extract ACTUAL content from documents
        content, sources = self._extract_real_content(documents, key_terms)
        
        if not content:
            logger.warning(f"⚠️ No content extracted for: {query}")
            return self._no_content_response(query)
        
        # Step 4: Format response with REAL content
        response = self._format_with_real_content(content, query_type, query)
        
        return {
            "response": response,
            "sources": sources,
            "confidence": self._calculate_confidence(documents, key_terms),
            "query_type": query_type,
            "has_real_content": True,
            "retrieval_method": "content_based"
        }
    
    def _identify_query_type(self, query_lower: str) -> str:
        """Identify the type of query."""
        if any(word in query_lower for word in ['contact', 'on call', 'phone', 'pager']):
            return 'contact'
        elif any(word in query_lower for word in ['form', 'consent', 'document']):
            return 'form'
        elif any(word in query_lower for word in ['protocol', 'activation', 'procedure']):
            return 'protocol'
        elif any(word in query_lower for word in ['criteria', 'threshold', 'score']):
            return 'criteria'
        elif any(word in query_lower for word in ['dose', 'dosing', 'dosage', 'mg', 'mcg']):
            return 'dosage'
        elif any(word in query_lower for word in ['pathway', 'retu']):
            return 'pathway'
        else:
            return 'summary'
    
    def _extract_key_terms(self, query: str) -> List[str]:
        """Extract key medical terms from query."""
        # Remove common words
        stop_words = {'the', 'is', 'what', 'show', 'me', 'for', 'in', 'of', 'and', 'to', 'a'}
        words = query.lower().split()
        key_terms = [w for w in words if w not in stop_words and len(w) > 2]
        
        # Add special medical terms
        if 'levophed' in query.lower():
            key_terms.extend(['norepinephrine', 'infusion'])
        if 'epi' in query.lower() or 'epinephrine' in query.lower():
            key_terms.extend(['epinephrine', 'anaphylaxis'])
        if 'stemi' in query.lower():
            key_terms.extend(['stemi', 'activation', 'cath'])
        if 'sepsis' in query.lower():
            key_terms.extend(['sepsis', 'lactate'])
        
        return list(set(key_terms))  # Remove duplicates
    
    def _find_relevant_documents(self, key_terms: List[str], query_type: str) -> List[Dict]:
        """Find the most relevant documents using smart matching."""
        
        # Build search conditions
        conditions = []
        params = {}
        
        # Priority 1: Filename matching
        for i, term in enumerate(key_terms[:3]):  # Top 3 terms
            conditions.append(f"(d.filename ILIKE :fname_{i})")
            params[f'fname_{i}'] = f'%{term}%'
        
        # Priority 2: Content matching
        for i, term in enumerate(key_terms[:5]):  # Top 5 terms
            conditions.append(f"(dc.chunk_text ILIKE :cterm_{i})")
            params[f'cterm_{i}'] = f'%{term}%'
        
        # Build the query with relevance scoring
        # Fix for PostgreSQL: Use subquery with ROW_NUMBER() to handle DISTINCT + ORDER BY
        search_query = f"""
            SELECT 
                d.id,
                d.filename,
                d.content_type,
                dc.chunk_text,
                dc.chunk_index,
                relevance_score
            FROM (
                SELECT DISTINCT ON (d.id, dc.id)
                    d.id,
                    d.filename,
                    d.content_type,
                    dc.chunk_text,
                    dc.chunk_index,
                    -- Calculate relevance score
                    (
                        -- Filename matches are highest priority
                        (CASE WHEN d.filename ILIKE :primary_term THEN 100 ELSE 0 END) +
                        -- Content type match
                        (CASE WHEN d.content_type = :query_type THEN 50 ELSE 0 END) +
                        -- Term frequency in content
                        (
                            SELECT COUNT(*)
                            FROM unnest(string_to_array(lower(dc.chunk_text), ' ')) as word
                            WHERE word = ANY(:key_terms_array)
                        ) * 10 +
                        -- Chunk length bonus (longer = more comprehensive)
                        (LENGTH(dc.chunk_text) / 100)
                    ) as relevance_score,
                    LENGTH(dc.chunk_text) as chunk_length
                FROM documents d
                JOIN document_chunks dc ON d.id = dc.document_id
                WHERE ({' OR '.join(conditions)})
                AND LENGTH(dc.chunk_text) > 50
                ORDER BY d.id, dc.id, relevance_score DESC, LENGTH(dc.chunk_text) DESC
            ) ranked_results
            ORDER BY relevance_score DESC, chunk_length DESC
            LIMIT 5
        """
        
        params['primary_term'] = f'%{key_terms[0]}%' if key_terms else '%'
        params['query_type'] = query_type
        params['key_terms_array'] = key_terms
        
        try:
            results = self.db.execute(text(search_query), params).fetchall()
            
            documents = []
            for row in results:
                documents.append({
                    'id': row[0],
                    'filename': row[1],
                    'content_type': row[2],
                    'chunk_text': row[3],
                    'chunk_index': row[4],
                    'relevance_score': row[5]
                })
            
            logger.info(f"📚 Found {len(documents)} relevant documents")
            if documents:
                logger.info(f"   Top match: {documents[0]['filename']} (score: {documents[0]['relevance_score']})")
            
            return documents
            
        except Exception as e:
            logger.error(f"❌ Search failed: {e}")
            return []
    
    def _extract_real_content(self, documents: List[Dict], key_terms: List[str]) -> Tuple[str, List[Dict]]:
        """Extract ACTUAL content from documents, not templates."""
        
        if not documents:
            return "", []
        
        # Use the top document's content
        primary_doc = documents[0]
        content = primary_doc['chunk_text']
        
        # If content is too short, get more chunks from same document
        if len(content) < 200:
            additional_query = text("""
                SELECT chunk_text
                FROM document_chunks
                WHERE document_id = :doc_id
                AND chunk_index != :current_index
                ORDER BY LENGTH(chunk_text) DESC
                LIMIT 2
            """)
            
            additional = self.db.execute(
                additional_query,
                {'doc_id': primary_doc['id'], 'current_index': primary_doc['chunk_index']}
            ).fetchall()
            
            for chunk in additional:
                content += "\n\n" + chunk[0]
        
        # Build sources
        sources = []
        seen_files = set()
        for doc in documents[:3]:  # Top 3 sources
            if doc['filename'] not in seen_files:
                sources.append({
                    'filename': doc['filename'],
                    'display_name': self._format_display_name(doc['filename']),
                    'content_type': doc['content_type']
                })
                seen_files.add(doc['filename'])
        
        return content, sources
    
    def _format_with_real_content(self, content: str, query_type: str, query: str) -> str:
        """Format response using ACTUAL content, not templates."""
        
        # Extract key information based on query type
        if query_type == 'dosage':
            return self._format_dosage_content(content, query)
        elif query_type == 'protocol':
            return self._format_protocol_content(content, query)
        elif query_type == 'criteria':
            return self._format_criteria_content(content, query)
        elif query_type == 'form':
            return self._format_form_content(content, query)
        elif query_type == 'pathway':
            return self._format_pathway_content(content, query)
        else:
            return self._format_summary_content(content, query)
    
    def _format_dosage_content(self, content: str, query: str) -> str:
        """Format dosage information from REAL content."""
        response = "💊 **Medication Dosing Information**\n\n"
        
        # Extract dosing information using patterns
        dose_patterns = [
            r'(\d+\.?\d*)\s*(mg|mcg|g|mL|units?)',
            r'(\d+\.?\d*)\s*(mg|mcg)/kg',
            r'(\d+\.?\d*)-(\d+\.?\d*)\s*(mg|mcg|g|mL)',
        ]
        
        doses_found = []
        for pattern in dose_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            doses_found.extend(matches)
        
        if doses_found:
            response += "**Dosing Details:**\n"
            for dose in doses_found[:5]:  # Show up to 5 doses
                if isinstance(dose, tuple):
                    dose_str = ' '.join(str(d) for d in dose)
                else:
                    dose_str = str(dose)
                response += f"• {dose_str}\n"
            response += "\n"
        
        # Add the actual content
        response += "**Full Information:**\n"
        response += content[:800]  # First 800 chars of actual content
        if len(content) > 800:
            response += "..."
        
        return response
    
    def _format_protocol_content(self, content: str, query: str) -> str:
        """Format protocol information from REAL content."""
        query_lower = query.lower()
        
        # Title based on query
        if 'stemi' in query_lower:
            response = "🚨 **STEMI Activation Protocol**\n\n"
        elif 'sepsis' in query_lower:
            response = "🦠 **Sepsis Protocol**\n\n"
        elif 'anaphylaxis' in query_lower:
            response = "⚠️ **Anaphylaxis Protocol**\n\n"
        else:
            response = "📋 **Medical Protocol**\n\n"
        
        # Extract key elements from content
        if 'contact' in content.lower() or 'phone' in content.lower() or 'pager' in content.lower():
            # Extract contact info
            phone_pattern = r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
            extension_pattern = r'x\d{4,5}'
            
            phones = re.findall(phone_pattern, content)
            extensions = re.findall(extension_pattern, content, re.IGNORECASE)
            
            if phones or extensions:
                response += "**📞 Contacts:**\n"
                for phone in phones[:3]:
                    response += f"• {phone}\n"
                for ext in extensions[:3]:
                    response += f"• Extension: {ext}\n"
                response += "\n"
        
        # Add timing if present
        if 'minute' in content.lower() or 'hour' in content.lower():
            response += "**⏱️ Timing Requirements:**\n"
            time_lines = [line for line in content.split('\n') if 'minute' in line.lower() or 'hour' in line.lower()]
            for line in time_lines[:3]:
                response += f"• {line.strip()}\n"
            response += "\n"
        
        # Add the actual content
        response += "**Protocol Details:**\n"
        response += content[:600]
        if len(content) > 600:
            response += "..."
        
        return response
    
    def _format_criteria_content(self, content: str, query: str) -> str:
        """Format criteria information from REAL content."""
        response = "📊 **Clinical Criteria**\n\n"
        
        # Look for numerical thresholds
        threshold_pattern = r'([<>=]+)\s*(\d+\.?\d*)\s*(mg/dL|mmol/L|mg/L|%)?'
        thresholds = re.findall(threshold_pattern, content)
        
        if thresholds:
            response += "**Key Thresholds:**\n"
            for threshold in thresholds[:5]:
                response += f"• {' '.join(threshold)}\n"
            response += "\n"
        
        # Add actual content
        response += "**Full Criteria:**\n"
        response += content[:600]
        if len(content) > 600:
            response += "..."
        
        return response
    
    def _format_form_content(self, content: str, query: str) -> str:
        """Format form information from REAL content."""
        response = "📄 **Medical Form Information**\n\n"
        
        # Add actual content - forms should show what's in the document
        response += "**Document Content:**\n"
        response += content[:800]
        if len(content) > 800:
            response += "..."
        
        return response
    
    def _format_pathway_content(self, content: str, query: str) -> str:
        """Format pathway information from REAL content."""
        response = "🛤️ **Clinical Pathway**\n\n"
        
        # Add the actual pathway content
        response += "**Pathway Details:**\n"
        response += content[:700]
        if len(content) > 700:
            response += "..."
        
        return response
    
    def _format_summary_content(self, content: str, query: str) -> str:
        """Format summary from REAL content."""
        response = "📋 **Medical Information**\n\n"
        
        # Just return the actual content
        response += content[:800]
        if len(content) > 800:
            response += "..."
        
        return response
    
    def _format_display_name(self, filename: str) -> str:
        """Format filename for display."""
        # Remove .pdf extension
        name = filename.replace('.pdf', '').replace('.PDF', '')
        # Replace underscores with spaces
        name = name.replace('_', ' ')
        # Remove path components
        if '\\' in name:
            name = name.split('\\')[-1]
        if '/' in name:
            name = name.split('/')[-1]
        return name
    
    def _calculate_confidence(self, documents: List[Dict], key_terms: List[str]) -> float:
        """Calculate confidence based on retrieval quality."""
        if not documents:
            return 0.0
        
        # Check relevance score
        top_score = documents[0].get('relevance_score', 0)
        
        # Check term coverage
        top_content = documents[0].get('chunk_text', '').lower()
        terms_found = sum(1 for term in key_terms if term.lower() in top_content)
        term_coverage = terms_found / len(key_terms) if key_terms else 0
        
        # Calculate confidence
        if top_score > 200:
            base_confidence = 0.9
        elif top_score > 100:
            base_confidence = 0.7
        elif top_score > 50:
            base_confidence = 0.5
        else:
            base_confidence = 0.3
        
        # Adjust by term coverage
        confidence = base_confidence * (0.5 + 0.5 * term_coverage)
        
        return min(0.95, confidence)  # Cap at 0.95
    
    def _no_content_response(self, query: str) -> Dict[str, Any]:
        """Response when no content is found."""
        return {
            "response": f"No relevant medical information found for: '{query}'. Please try rephrasing your query or check if the document exists in the system.",
            "sources": [],
            "confidence": 0.0,
            "query_type": "unknown",
            "has_real_content": False,
            "retrieval_method": "content_based"
        }