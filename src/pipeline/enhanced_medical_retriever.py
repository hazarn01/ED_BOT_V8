"""
Enhanced Medical RAG Retriever for PRP-41: Universal Curated-Quality Response System
Medical-context-aware semantic search with clinical relevance scoring.
"""

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.models.query_types import QueryType

from .rag_retriever import RAGRetriever

logger = logging.getLogger(__name__)


@dataclass
class MedicalContext:
    """Structured medical context with enhanced metadata."""
    primary_content: str
    supporting_evidence: List[str]
    medical_terminology: Dict[str, str]
    confidence_indicators: List[str]
    source_citations: List[Dict[str, str]]
    clinical_relevance_score: float
    query_type_alignment: float
    medical_certainty_level: str  # "high", "medium", "low"


@dataclass
class EnhancedResult:
    """Enhanced search result with medical context awareness."""
    content: str
    source: Dict[str, str]
    clinical_relevance: float
    medical_certainty: str
    terminology_matches: List[str]
    context_alignment: float
    chunk_metadata: Dict[str, Any]


class EnhancedMedicalRetriever:
    """
    Enhanced retriever that produces medical-context-aware results
    optimized for generating curated-quality responses.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.base_retriever = RAGRetriever(db)
        
        # Medical terminology patterns
        self.medical_abbreviations = self._load_medical_abbreviations()
        self.clinical_indicators = self._load_clinical_indicators()
        self.priority_terms = self._load_priority_terms()
        
    def retrieve_medical_context(
        self, 
        query: str, 
        query_type: QueryType,
        k: int = 5
    ) -> MedicalContext:
        """
        Retrieve medical context optimized for curated-quality response generation.
        
        Args:
            query: User query
            query_type: Classified query type
            k: Number of results to retrieve
            
        Returns:
            Enhanced medical context with clinical relevance scoring
        """
        try:
            # Step 1: Enhanced medical search with clinical relevance
            enhanced_results = self._medical_context_search(query, query_type, k)
            
            # Step 2: Medical terminology extraction and normalization
            terminology = self._extract_medical_terminology(query, enhanced_results)
            
            # Step 3: Clinical relevance assessment
            relevance_score = self._assess_clinical_relevance(query, enhanced_results, query_type)
            
            # Step 4: Confidence indicators extraction
            confidence_indicators = self._extract_confidence_indicators(enhanced_results)
            
            # Step 5: Query type alignment scoring
            alignment_score = self._calculate_query_type_alignment(query, enhanced_results, query_type)
            
            # Step 6: Medical certainty assessment
            certainty_level = self._assess_medical_certainty(enhanced_results, relevance_score)
            
            # Step 7: Multi-document synthesis for comprehensive context
            primary_content, supporting_evidence = self._synthesize_medical_content(
                enhanced_results, query_type, terminology
            )
            
            # Step 8: Source citations with proper display names
            citations = self._format_medical_citations(enhanced_results)
            
            return MedicalContext(
                primary_content=primary_content,
                supporting_evidence=supporting_evidence,
                medical_terminology=terminology,
                confidence_indicators=confidence_indicators,
                source_citations=citations,
                clinical_relevance_score=relevance_score,
                query_type_alignment=alignment_score,
                medical_certainty_level=certainty_level
            )
            
        except Exception as e:
            logger.error(f"Enhanced medical retrieval failed: {e}")
            
            # Fallback to basic retrieval with minimal context
            basic_results, sources = self.base_retriever.retrieve_for_query_type(
                query, query_type.value, k
            )
            
            return MedicalContext(
                primary_content=self._basic_content_synthesis(basic_results),
                supporting_evidence=[],
                medical_terminology={},
                confidence_indicators=["fallback_retrieval"],
                source_citations=[{"display_name": s, "filename": s} for s in sources],
                clinical_relevance_score=0.5,
                query_type_alignment=0.5,
                medical_certainty_level="medium"
            )
    
    def _medical_context_search(
        self, 
        query: str, 
        query_type: QueryType, 
        k: int
    ) -> List[EnhancedResult]:
        """Enhanced search with medical-context awareness."""
        try:
            # Extract medical terms with context
            medical_terms = self._extract_medical_terms_with_context(query)
            
            # Build advanced medical search query
            search_conditions = []
            params = {}
            relevance_components = []
            
            for i, (term, context_weight) in enumerate(medical_terms):
                param_name = f"term_{i}"
                search_conditions.append(f"dc.chunk_text ILIKE :{param_name}")
                params[param_name] = f"%{term}%"
                
                # Medical-context-aware relevance scoring
                relevance_components.append(f"""
                    (CASE WHEN dc.chunk_text ILIKE :{param_name} THEN
                        -- Base term frequency with medical context weighting
                        ((LENGTH(dc.chunk_text) - LENGTH(REPLACE(UPPER(dc.chunk_text), UPPER('{term}'), ''))) 
                         / LENGTH('{term}')) * {context_weight}
                        
                        -- Medical document priority (highest boost)
                        + (CASE 
                            WHEN d.content_type IN ('protocol', 'guideline', 'criteria', 'medication') THEN 200
                            WHEN dr.category IN ('protocol', 'criteria', 'dosage', 'form') THEN 180
                            WHEN d.filename ILIKE '%protocol%' OR d.filename ILIKE '%guideline%' THEN 160
                            WHEN d.filename ILIKE '%clinical%' OR d.filename ILIKE '%medical%' THEN 140
                            ELSE 0 
                        END)
                        
                        -- Query-type-specific medical boosting
                        + {self._get_query_type_medical_boost(query_type, term)}
                        
                        -- Clinical relevance indicators
                        + (CASE 
                            WHEN dc.chunk_text ILIKE '%dose%' OR dc.chunk_text ILIKE '%dosage%' THEN 80
                            WHEN dc.chunk_text ILIKE '%protocol%' OR dc.chunk_text ILIKE '%procedure%' THEN 100
                            WHEN dc.chunk_text ILIKE '%criteria%' OR dc.chunk_text ILIKE '%indication%' THEN 90
                            WHEN dc.chunk_text ILIKE '%contact%' OR dc.chunk_text ILIKE '%pager%' THEN 70
                            WHEN dc.chunk_text ILIKE '%mg%' OR dc.chunk_text ILIKE '%ml%' OR dc.chunk_text ILIKE '%units%' THEN 60
                            WHEN dc.chunk_text ILIKE '%emergency%' OR dc.chunk_text ILIKE '%urgent%' THEN 50
                            ELSE 0
                        END)
                        
                        -- Medical terminology precision boost
                        + (CASE 
                            WHEN '{term.upper()}' IN ('STEMI', 'SEPSIS', 'CARDIAC', 'ARREST', 'PROTOCOL', 'EPINEPHRINE') THEN 120
                            WHEN dc.chunk_text ~* '\\b{re.escape(term)}\\b' THEN 40  -- Exact word match
                            ELSE 0
                        END)
                        
                        -- Penalize non-medical content heavily
                        - (CASE 
                            WHEN d.filename ILIKE '%context_enhancement%' OR d.filename ILIKE '%readme%' THEN 500
                            WHEN d.filename ILIKE '%test%' OR d.filename ILIKE '%example%' THEN 400
                            WHEN d.filename ILIKE '%guide%' OR d.filename ILIKE '%tutorial%' THEN 300
                            WHEN d.content_type = 'general' OR dr.category = 'general' THEN 200
                            ELSE 0
                        END)
                    ELSE 0 END)
                """)
            
            # Combine search conditions
            if medical_terms:
                where_clause = " OR ".join(search_conditions)
                relevance_calc = " + ".join(relevance_components)
            else:
                # Fallback for queries without clear medical terms
                where_clause = "dc.chunk_text ILIKE :general_term"
                params["general_term"] = f"%{query}%"
                relevance_calc = "1.0"
            
            # Execute enhanced search
            search_query = f"""
                SELECT 
                    dc.id,
                    dc.document_id,
                    dc.chunk_text,
                    dc.chunk_index,
                    dc.metadata,
                    d.filename,
                    d.content_type,
                    d.file_type,
                    dr.display_name,
                    dr.category,
                    ({relevance_calc}) as clinical_relevance
                FROM document_chunks dc
                JOIN documents d ON dc.document_id = d.id
                LEFT JOIN document_registry dr ON d.id = dr.document_id
                WHERE ({where_clause})
                AND LENGTH(dc.chunk_text) > 30  -- Filter out very short chunks
                ORDER BY clinical_relevance DESC, LENGTH(dc.chunk_text) DESC
                LIMIT :k
            """
            
            params["k"] = k
            results = self.db.execute(text(search_query), params).fetchall()
            
            # Convert to EnhancedResult objects with medical context
            enhanced_results = []
            for row in results:
                # Analyze medical content for each result
                terminology_matches = self._identify_terminology_matches(row.chunk_text, query)
                context_alignment = self._calculate_context_alignment(row.chunk_text, query_type)
                medical_certainty = self._assess_chunk_medical_certainty(row.chunk_text)
                
                enhanced_result = EnhancedResult(
                    content=row.chunk_text,
                    source={
                        "filename": row.filename,
                        "display_name": row.display_name or self._generate_display_name(row.filename),
                        "content_type": row.content_type,
                        "file_type": row.file_type,
                        "category": row.category
                    },
                    clinical_relevance=float(row.clinical_relevance) if row.clinical_relevance else 0.0,
                    medical_certainty=medical_certainty,
                    terminology_matches=terminology_matches,
                    context_alignment=context_alignment,
                    chunk_metadata=row.metadata or {}
                )
                enhanced_results.append(enhanced_result)
                
            logger.info(f"Enhanced medical search returned {len(enhanced_results)} results")
            return enhanced_results
            
        except Exception as e:
            logger.error(f"Enhanced medical search failed: {e}")
            return []
    
    def _extract_medical_terms_with_context(self, query: str) -> List[Tuple[str, float]]:
        """Extract medical terms with context-aware weighting."""
        terms_with_weights = []
        query_lower = query.lower()
        
        # High-priority medical terms (weight 3.0)
        high_priority = ['stemi', 'sepsis', 'cardiac arrest', 'epinephrine', 'protocol', 'ottawa', 'criteria']
        for term in high_priority:
            if term in query_lower:
                terms_with_weights.append((term, 3.0))
        
        # Medical abbreviations (weight 2.5)
        medical_abbrevs = re.findall(r'\b[A-Z]{2,}\b', query)
        for abbrev in medical_abbrevs:
            if abbrev in self.medical_abbreviations:
                terms_with_weights.append((abbrev, 2.5))
        
        # Standard medical terms (weight 2.0)
        medical_terms = ['dose', 'dosage', 'treatment', 'medication', 'contact', 'form', 'guideline']
        for term in medical_terms:
            if term in query_lower:
                terms_with_weights.append((term, 2.0))
        
        # Extract meaningful words (weight 1.5)
        words = re.findall(r'\b\w{3,}\b', query_lower)
        stop_words = {'what', 'the', 'and', 'for', 'with', 'how', 'show', 'tell', 'give'}
        for word in words:
            if word not in stop_words and not any(word in existing[0] for existing in terms_with_weights):
                terms_with_weights.append((word, 1.5))
        
        # If no terms found, use the full query
        if not terms_with_weights:
            terms_with_weights.append((query.strip(), 1.0))
        
        return terms_with_weights[:5]  # Limit to top 5 terms
    
    def _get_query_type_medical_boost(self, query_type: QueryType, term: str) -> str:
        """Get query-type-specific medical relevance boost."""
        boosts = {
            QueryType.PROTOCOL_STEPS: {
                "high": ["protocol", "procedure", "activation", "steps", "workflow"],
                "boost_value": "150"
            },
            QueryType.DOSAGE_LOOKUP: {
                "high": ["dose", "dosage", "mg", "ml", "units", "medication"],
                "boost_value": "140"
            },
            QueryType.CRITERIA_CHECK: {
                "high": ["criteria", "rules", "score", "threshold", "indication"],
                "boost_value": "130"
            },
            QueryType.CONTACT_LOOKUP: {
                "high": ["contact", "call", "pager", "phone", "on-call"],
                "boost_value": "120"
            },
            QueryType.FORM_RETRIEVAL: {
                "high": ["form", "document", "consent", "template"],
                "boost_value": "110"
            },
            QueryType.SUMMARY_REQUEST: {
                "high": ["summary", "overview", "management", "treatment"],
                "boost_value": "100"
            }
        }
        
        boost_config = boosts.get(query_type, {"high": [], "boost_value": "0"})
        
        if term.lower() in boost_config["high"]:
            return boost_config["boost_value"]
        return "0"
    
    def _extract_medical_terminology(
        self, 
        query: str, 
        results: List[EnhancedResult]
    ) -> Dict[str, str]:
        """Extract and normalize medical terminology."""
        terminology = {}
        
        # Extract from query
        query_terms = re.findall(r'\b[A-Z]{2,}\b', query)
        for term in query_terms:
            if term in self.medical_abbreviations:
                terminology[term] = self.medical_abbreviations[term]
        
        # Extract from results content
        for result in results:
            content_terms = re.findall(r'\b[A-Z]{2,}\b', result.content)
            for term in content_terms:
                if term in self.medical_abbreviations and term not in terminology:
                    terminology[term] = self.medical_abbreviations[term]
        
        return terminology
    
    def _assess_clinical_relevance(
        self, 
        query: str, 
        results: List[EnhancedResult], 
        query_type: QueryType
    ) -> float:
        """Assess overall clinical relevance of retrieved results."""
        if not results:
            return 0.0
        
        # Base score from individual result relevance
        avg_relevance = sum(r.clinical_relevance for r in results) / len(results)
        
        # Boost for medical terminology matches
        terminology_boost = len(results[0].terminology_matches) * 0.1 if results else 0.0
        
        # Query type alignment boost
        alignment_boost = sum(r.context_alignment for r in results) / len(results) * 0.3
        
        # Medical certainty boost
        certainty_boost = len([r for r in results if r.medical_certainty == "high"]) / len(results) * 0.2
        
        total_score = min(1.0, (avg_relevance / 100.0) + terminology_boost + alignment_boost + certainty_boost)
        return total_score
    
    def _extract_confidence_indicators(self, results: List[EnhancedResult]) -> List[str]:
        """Extract confidence indicators from medical content."""
        indicators = []
        
        for result in results:
            content = result.content.lower()
            
            # High confidence indicators
            if any(term in content for term in ["protocol", "guideline", "standard", "recommended"]):
                indicators.append("established_protocol")
            
            if any(term in content for term in ["dose", "mg", "ml", "units"]):
                indicators.append("specific_dosing")
            
            if any(term in content for term in ["contact", "phone", "pager", "call"]):
                indicators.append("verified_contact")
            
            # Medical authority indicators
            if any(term in content for term in ["acls", "aha", "emergency", "clinical"]):
                indicators.append("medical_authority")
            
            # Specificity indicators
            if re.search(r'\d+\s*(mg|ml|units|minutes|hours)', content):
                indicators.append("quantitative_data")
        
        return list(set(indicators))  # Remove duplicates
    
    def _calculate_query_type_alignment(
        self, 
        query: str, 
        results: List[EnhancedResult], 
        query_type: QueryType
    ) -> float:
        """Calculate how well results align with the query type."""
        if not results:
            return 0.0
        
        alignment_scores = []
        for result in results:
            alignment_scores.append(result.context_alignment)
        
        return sum(alignment_scores) / len(alignment_scores) if alignment_scores else 0.0
    
    def _assess_medical_certainty(
        self, 
        results: List[EnhancedResult], 
        relevance_score: float
    ) -> str:
        """Assess the medical certainty level of the retrieved context."""
        if not results:
            return "low"
        
        high_certainty_count = len([r for r in results if r.medical_certainty == "high"])
        high_relevance_count = len([r for r in results if r.clinical_relevance > 100.0])
        
        certainty_ratio = high_certainty_count / len(results)
        relevance_ratio = high_relevance_count / len(results)
        
        if certainty_ratio >= 0.6 and relevance_ratio >= 0.5 and relevance_score >= 0.7:
            return "high"
        elif certainty_ratio >= 0.3 and relevance_score >= 0.5:
            return "medium"
        else:
            return "low"
    
    def _synthesize_medical_content(
        self, 
        results: List[EnhancedResult], 
        query_type: QueryType,
        terminology: Dict[str, str]
    ) -> Tuple[str, List[str]]:
        """Synthesize medical content for comprehensive context."""
        if not results:
            return "", []
        
        # Primary content from highest relevance result
        primary_result = max(results, key=lambda r: r.clinical_relevance)
        primary_content = primary_result.content
        
        # Supporting evidence from other high-relevance results
        supporting_evidence = []
        for result in results[1:4]:  # Take up to 3 supporting chunks
            if result.clinical_relevance > 50.0:  # Only high-relevance supporting content
                supporting_evidence.append(result.content)
        
        return primary_content, supporting_evidence
    
    def _format_medical_citations(self, results: List[EnhancedResult]) -> List[Dict[str, str]]:
        """Format medical citations with proper display names."""
        citations = []
        seen_sources = set()
        
        for result in results:
            source = result.source
            display_name = source.get("display_name", source.get("filename", "Unknown"))
            filename = source.get("filename", "unknown")
            
            if filename not in seen_sources:
                citations.append({
                    "display_name": display_name,
                    "filename": filename,
                    "content_type": source.get("content_type", "unknown"),
                    "category": source.get("category", "unknown")
                })
                seen_sources.add(filename)
        
        return citations
    
    def _identify_terminology_matches(self, content: str, query: str) -> List[str]:
        """Identify medical terminology matches in content."""
        matches = []
        
        # Check for medical abbreviations
        content_terms = re.findall(r'\b[A-Z]{2,}\b', content)
        query_terms = re.findall(r'\b[A-Z]{2,}\b', query)
        
        for term in content_terms:
            if term in self.medical_abbreviations:
                matches.append(term)
        
        for term in query_terms:
            if term in content.upper() and term not in matches:
                matches.append(term)
        
        # Check for clinical indicators
        for indicator in self.clinical_indicators:
            if indicator.lower() in content.lower() and indicator not in matches:
                matches.append(indicator)
        
        return matches
    
    def _calculate_context_alignment(self, content: str, query_type: QueryType) -> float:
        """Calculate how well content aligns with the query type."""
        content_lower = content.lower()
        
        # Query type specific indicators
        type_indicators = {
            QueryType.PROTOCOL_STEPS: ["protocol", "procedure", "step", "activation", "workflow"],
            QueryType.DOSAGE_LOOKUP: ["dose", "dosage", "mg", "ml", "units", "medication"],
            QueryType.CRITERIA_CHECK: ["criteria", "rule", "score", "threshold", "indication"],
            QueryType.CONTACT_LOOKUP: ["contact", "call", "pager", "phone", "on-call"],
            QueryType.FORM_RETRIEVAL: ["form", "document", "consent", "template"],
            QueryType.SUMMARY_REQUEST: ["treatment", "management", "overview", "summary"]
        }
        
        indicators = type_indicators.get(query_type, [])
        matches = sum(1 for indicator in indicators if indicator in content_lower)
        
        return min(1.0, matches / len(indicators) if indicators else 0.5)
    
    def _assess_chunk_medical_certainty(self, content: str) -> str:
        """Assess medical certainty of individual content chunk."""
        content_lower = content.lower()
        
        # High certainty indicators
        high_certainty = [
            "protocol", "guideline", "standard", "recommended", 
            "dose", "mg", "ml", "units", "contact", "pager"
        ]
        
        # Low certainty indicators
        low_certainty = ["may", "might", "possibly", "consider", "suggest"]
        
        high_count = sum(1 for term in high_certainty if term in content_lower)
        low_count = sum(1 for term in low_certainty if term in content_lower)
        
        if high_count >= 2 and low_count == 0:
            return "high"
        elif high_count >= 1 and low_count <= 1:
            return "medium"
        else:
            return "low"
    
    def _generate_display_name(self, filename: str) -> str:
        """Generate display name from filename."""
        if not filename:
            return "Medical Document"
        
        # Remove extension and clean up
        name = filename.replace('.pdf', '').replace('.docx', '').replace('.txt', '')
        name = name.replace('_', ' ').replace('-', ' ')
        
        # Title case with medical context awareness
        name = name.title()
        
        # Fix common medical abbreviations
        name = name.replace('Ed ', 'ED ')
        name = name.replace('Stemi', 'STEMI')
        name = name.replace('Acls', 'ACLS')
        name = name.replace('Bls', 'BLS')
        
        return name
    
    def _basic_content_synthesis(self, results: List[Dict[str, Any]]) -> str:
        """Basic content synthesis for fallback scenarios."""
        if not results:
            return "No relevant medical information found."
        
        # Get content from top result
        return results[0].get("content", "No content available.")
    
    def _load_medical_abbreviations(self) -> Dict[str, str]:
        """Load medical abbreviations for context awareness."""
        return {
            'STEMI': 'ST-elevation myocardial infarction',
            'NSTEMI': 'Non-ST-elevation myocardial infarction',
            'MI': 'Myocardial infarction',
            'CVA': 'Cerebrovascular accident',
            'PE': 'Pulmonary embolism',
            'DVT': 'Deep vein thrombosis',
            'CHF': 'Congestive heart failure',
            'COPD': 'Chronic obstructive pulmonary disease',
            'DKA': 'Diabetic ketoacidosis',
            'ACLS': 'Advanced cardiac life support',
            'BLS': 'Basic life support',
            'IV': 'Intravenous',
            'IM': 'Intramuscular',
            'SQ': 'Subcutaneous',
            'PO': 'Per os (by mouth)',
            'PRN': 'Pro re nata (as needed)',
            'STAT': 'Immediately',
            'DNR': 'Do not resuscitate',
            'ICU': 'Intensive care unit',
            'ED': 'Emergency department',
            'EKG': 'Electrocardiogram',
            'ECG': 'Electrocardiogram'
        }
    
    def _load_clinical_indicators(self) -> List[str]:
        """Load clinical indicators for relevance assessment."""
        return [
            'protocol', 'guideline', 'criteria', 'dose', 'dosage', 'treatment',
            'emergency', 'urgent', 'contact', 'pager', 'phone', 'activation',
            'procedure', 'medication', 'contraindication', 'indication',
            'assessment', 'evaluation', 'management', 'therapeutic'
        ]
    
    def _load_priority_terms(self) -> List[str]:
        """Load priority medical terms for enhanced relevance."""
        return [
            'cardiac arrest', 'myocardial infarction', 'stroke', 'sepsis',
            'anaphylaxis', 'trauma', 'respiratory failure', 'shock',
            'hypoglycemia', 'seizure', 'overdose', 'poisoning'
        ]
