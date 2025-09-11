"""
Medical Synonym Expander for Enhanced Query Processing
Context-aware medical terminology expansion for improved retrieval.
"""

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set, Tuple

from src.models.query_types import QueryType
from src.observability import medical_metrics

logger = logging.getLogger(__name__)


@dataclass
class SynonymExpansion:
    """Result of medical synonym expansion."""
    original_term: str
    expanded_terms: List[str]
    medical_context: str  # "cardiology", "emergency", etc.
    confidence: float
    source_category: str  # "abbreviations", "clinical_conditions", etc.


@dataclass
class ExpandedQuery:
    """Query expanded with medical synonyms."""
    original_query: str
    expanded_terms: List[str]
    synonym_expansions: List[SynonymExpansion]
    query_type_context: str
    expansion_confidence: float


class MedicalSynonymExpander:
    """
    Medical-context-aware synonym expansion for enhanced retrieval.
    Expands medical queries with contextually relevant synonyms.
    """
    
    def __init__(self):
        # Load medical synonyms data
        self.synonyms = self._load_medical_synonyms()
        self.context_map = self._build_context_mapping()
        
        # Medical term patterns for identification
        self.medical_abbrev_pattern = re.compile(r'\b[A-Z]{2,}\b')
        self.dosage_pattern = re.compile(r'\d+\s*(mg|mcg|ml|L|units|IU|mEq)\b', re.IGNORECASE)
        self.vital_pattern = re.compile(r'\d+\s*(mmHg|bpm|breaths/min|%)\b', re.IGNORECASE)
        
        # Query type priority mappings for context-aware expansion
        self.query_type_priorities = {
            QueryType.CONTACT_LOOKUP: ["specialties", "query_type_contexts", "abbreviations"],
            QueryType.FORM_RETRIEVAL: ["query_type_contexts", "procedures", "clinical_conditions"],
            QueryType.PROTOCOL_STEPS: ["procedures", "clinical_conditions", "abbreviations", "specialties"],
            QueryType.CRITERIA_CHECK: ["clinical_conditions", "abbreviations", "units_measurements"],
            QueryType.DOSAGE_LOOKUP: ["medications", "units_measurements", "abbreviations"],
            QueryType.SUMMARY_REQUEST: ["clinical_conditions", "specialties", "procedures"]
        }
        
    def expand_query(self, query: str, query_type: QueryType) -> ExpandedQuery:
        """
        Expand query with contextually relevant medical synonyms.
        
        Args:
            query: Original query string
            query_type: Classified query type for context
            
        Returns:
            ExpandedQuery with synonym expansions and context
        """
        try:
            # Track synonym expansion usage
            try:
                medical_metrics.medical_abbreviation_usage.inc()
            except Exception as e:
                logger.warning(f"Medical metrics tracking failed: {e}")
            
            # Extract medical terms from query
            medical_terms = self._extract_medical_terms(query)
            
            # Perform context-aware expansion
            synonym_expansions = []
            expanded_terms = [query]  # Start with original query
            
            for term in medical_terms:
                expansion = self._expand_medical_term(term, query_type)
                if expansion.expanded_terms:
                    synonym_expansions.append(expansion)
                    expanded_terms.extend(expansion.expanded_terms)
            
            # Add query-type-specific context terms
            context_terms = self._get_query_type_context_terms(query, query_type)
            expanded_terms.extend(context_terms)
            
            # Remove duplicates while preserving order
            unique_expanded = []
            seen = set()
            for term in expanded_terms:
                term_lower = term.lower()
                if term_lower not in seen:
                    unique_expanded.append(term)
                    seen.add(term_lower)
            
            # Calculate expansion confidence
            expansion_confidence = self._calculate_expansion_confidence(
                synonym_expansions, query_type
            )
            
            # Track expansion metrics
            if synonym_expansions:
                try:
                    medical_metrics.medication_extraction.inc()
                except Exception as e:
                    logger.warning(f"Expansion metrics tracking failed: {e}")
            
            result = ExpandedQuery(
                original_query=query,
                expanded_terms=unique_expanded,
                synonym_expansions=synonym_expansions,
                query_type_context=query_type.value,
                expansion_confidence=expansion_confidence
            )
            
            logger.info(f"Expanded query with {len(synonym_expansions)} synonyms, "
                       f"confidence: {expansion_confidence:.2f}")
            
            return result
            
        except Exception as e:
            logger.error(f"Medical synonym expansion failed: {e}")
            
            # Return minimal expansion on failure
            return ExpandedQuery(
                original_query=query,
                expanded_terms=[query],
                synonym_expansions=[],
                query_type_context=query_type.value,
                expansion_confidence=0.5
            )
    
    def get_expansion_patterns(self, query_type: QueryType) -> Dict[str, List[str]]:
        """Get expansion patterns for specific query types."""
        priority_categories = self.query_type_priorities.get(query_type, [])
        patterns = {}
        
        for category in priority_categories:
            if category in self.synonyms:
                patterns[category] = list(self.synonyms[category].keys())
        
        return patterns
    
    def _extract_medical_terms(self, query: str) -> List[str]:
        """Extract potential medical terms from query."""
        medical_terms = []
        query_lower = query.lower()
        
        # Extract medical abbreviations (2+ capital letters)
        abbreviations = self.medical_abbrev_pattern.findall(query)
        medical_terms.extend(abbreviations)
        
        # Extract dosage and measurement patterns
        dosages = self.dosage_pattern.findall(query)
        vitals = self.vital_pattern.findall(query)
        medical_terms.extend(dosages + vitals)
        
        # Extract known medical terms from all categories
        for category_name, category_data in self.synonyms.items():
            if isinstance(category_data, dict):
                for term in category_data.keys():
                    term_lower = term.lower()
                    if term_lower in query_lower:
                        medical_terms.append(term)
                        
                    # Also check for partial matches in longer terms
                    for synonym_list in category_data.values():
                        if isinstance(synonym_list, list):
                            for synonym in synonym_list:
                                if synonym.lower() in query_lower:
                                    medical_terms.append(synonym)
        
        # Extract meaningful words that might be medical
        words = re.findall(r'\b\w{3,}\b', query_lower)
        medical_keywords = [
            'pain', 'treatment', 'dose', 'protocol', 'contact', 'form', 
            'criteria', 'emergency', 'urgent', 'cardiac', 'respiratory',
            'neurological', 'infection', 'medication', 'procedure'
        ]
        
        for word in words:
            if word in medical_keywords and word not in medical_terms:
                medical_terms.append(word)
        
        return list(set(medical_terms))  # Remove duplicates
    
    def _expand_medical_term(
        self, 
        term: str, 
        query_type: QueryType
    ) -> SynonymExpansion:
        """Expand a single medical term with context awareness."""
        term_upper = term.upper()
        term_lower = term.lower()
        
        # Get priority categories for this query type
        priority_categories = self.query_type_priorities.get(query_type, [])
        
        expanded_terms = []
        best_category = "general"
        best_confidence = 0.0
        medical_context = self._get_specialty_context(query_type)
        
        # Search through categories in priority order
        for category in priority_categories:
            if category not in self.synonyms:
                continue
                
            category_data = self.synonyms[category]
            if not isinstance(category_data, dict):
                continue
            
            # Direct key match
            if term_upper in category_data:
                expanded_terms.extend(category_data[term_upper])
                best_category = category
                best_confidence = 0.9
                break
            elif term_lower in category_data:
                expanded_terms.extend(category_data[term_lower])
                best_category = category
                best_confidence = 0.9
                break
            elif term in category_data:
                expanded_terms.extend(category_data[term])
                best_category = category
                best_confidence = 0.9
                break
                
            # Check if term appears in synonyms (reverse lookup)
            for key, synonym_list in category_data.items():
                if isinstance(synonym_list, list):
                    for synonym in synonym_list:
                        if (synonym.lower() == term_lower or 
                            term_lower in synonym.lower().split()):
                            expanded_terms.extend(synonym_list)
                            expanded_terms.append(key)
                            best_category = category
                            best_confidence = 0.7
                            break
                    if best_confidence > 0:
                        break
            
            if best_confidence > 0:
                break
        
        # Remove duplicates and the original term
        unique_expansions = []
        seen = {term_lower, term_upper, term}
        
        for expanded in expanded_terms:
            if expanded.lower() not in seen:
                unique_expansions.append(expanded)
                seen.add(expanded.lower())
        
        return SynonymExpansion(
            original_term=term,
            expanded_terms=unique_expansions,
            medical_context=medical_context,
            confidence=best_confidence,
            source_category=best_category
        )
    
    def _get_query_type_context_terms(
        self, 
        query: str, 
        query_type: QueryType
    ) -> List[str]:
        """Get additional context terms based on query type."""
        context_terms = []
        
        if "query_type_contexts" in self.synonyms:
            contexts = self.synonyms["query_type_contexts"]
            query_type_key = query_type.value.lower().split('_')[0]  # e.g., "contact" from "contact_lookup"
            
            if query_type_key in contexts:
                context_terms.extend(contexts[query_type_key])
        
        # Add specialty-specific terms
        specialty = self._get_specialty_context(query_type)
        if specialty and "specialties" in self.synonyms:
            specialty_data = self.synonyms["specialties"]
            if specialty in specialty_data:
                context_terms.extend(specialty_data[specialty])
        
        return context_terms
    
    def _calculate_expansion_confidence(
        self, 
        expansions: List[SynonymExpansion], 
        query_type: QueryType
    ) -> float:
        """Calculate overall confidence in the expansion."""
        if not expansions:
            return 0.3  # Low confidence for no expansions
        
        # Average individual confidences
        avg_confidence = sum(exp.confidence for exp in expansions) / len(expansions)
        
        # Boost for query-type-appropriate expansions
        type_boost = 0.0
        priority_categories = self.query_type_priorities.get(query_type, [])
        
        for expansion in expansions:
            if expansion.source_category in priority_categories[:2]:  # Top 2 priorities
                type_boost += 0.1
        
        # Boost for multiple expansions (more context)
        quantity_boost = min(0.2, len(expansions) * 0.05)
        
        total_confidence = min(1.0, avg_confidence + type_boost + quantity_boost)
        return total_confidence
    
    def _get_specialty_context(self, query_type: QueryType) -> str:
        """Determine medical specialty context from query type."""
        specialty_mapping = {
            QueryType.CONTACT_LOOKUP: "emergency",
            QueryType.FORM_RETRIEVAL: "emergency", 
            QueryType.PROTOCOL_STEPS: "emergency",
            QueryType.CRITERIA_CHECK: "emergency",
            QueryType.DOSAGE_LOOKUP: "emergency",
            QueryType.SUMMARY_REQUEST: "emergency"
        }
        
        return specialty_mapping.get(query_type, "general")
    
    def _load_medical_synonyms(self) -> Dict:
        """Load medical synonyms from JSON file."""
        try:
            # Get the path relative to this file
            current_dir = Path(__file__).parent
            synonyms_file = current_dir.parent / "data" / "medical_synonyms.json"
            
            with open(synonyms_file, 'r', encoding='utf-8') as f:
                synonyms = json.load(f)
            
            logger.info(f"Loaded medical synonyms with {len(synonyms)} categories")
            return synonyms
            
        except FileNotFoundError:
            logger.error(f"Medical synonyms file not found: {synonyms_file}")
            return self._get_fallback_synonyms()
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in synonyms file: {e}")
            return self._get_fallback_synonyms()
        except Exception as e:
            logger.error(f"Error loading medical synonyms: {e}")
            return self._get_fallback_synonyms()
    
    def _get_fallback_synonyms(self) -> Dict:
        """Provide minimal fallback synonyms if file loading fails."""
        return {
            "abbreviations": {
                "STEMI": ["ST elevation myocardial infarction", "heart attack"],
                "MI": ["myocardial infarction", "heart attack"],
                "CVA": ["stroke", "cerebrovascular accident"],
                "ED": ["emergency department", "emergency room"],
                "IV": ["intravenous"],
                "STAT": ["immediately", "urgent"]
            },
            "clinical_conditions": {
                "sepsis": ["infection", "septic shock"],
                "shock": ["hypotension", "low blood pressure"],
                "cardiac arrest": ["heart stopped", "no pulse"]
            },
            "query_type_contexts": {
                "contact": ["call", "pager", "phone"],
                "form": ["document", "PDF"],
                "protocol": ["procedure", "guideline"],
                "criteria": ["rules", "requirements"],
                "dosage": ["dose", "amount"],
                "summary": ["overview", "management"]
            }
        }
    
    def _build_context_mapping(self) -> Dict[str, List[str]]:
        """Build reverse mapping from contexts to terms."""
        context_mapping = {}
        
        for category_name, category_data in self.synonyms.items():
            if isinstance(category_data, dict):
                for term, synonyms in category_data.items():
                    if isinstance(synonyms, list):
                        for synonym in synonyms:
                            if synonym not in context_mapping:
                                context_mapping[synonym] = []
                            context_mapping[synonym].append(term)
        
        return context_mapping